"""Replace low-quality opinion text with clean Westlaw opinion text.

For opinions where we have a Westlaw .doc download and the current text came
from CourtListener (NW, NW2d), replaces text_content with the Westlaw
opinion body. Preserves YAML frontmatter from the existing record.

Opinions sourced from ndcourts.gov (source_reporter='ND') are NOT replaced —
the court's own text is authoritative for 1997+ opinions. Westlaw downloads
for those should be used as a reference to identify specific corrections.

Usage:
    python -m ndcourts_mcp.merge_westlaw_text [--db PATH] [--dry-run] [--batch NAME]
"""

import argparse
import re
from pathlib import Path

from .db import DEFAULT_DB_PATH, get_connection, log_provenance
from .ingest_westlaw import _doc_to_text, _parse_westlaw_doc

# Westlaw editorial preamble detection. "Syllabus by the Court", "Synopsis"
# (which often contains the court's published statement of facts in older
# opinions), and "Attorneys and Law Firms" are all court-published or
# court-adjacent content intentionally included by the full-bound-text
# extractor. Only "West Headnotes" is unambiguously Westlaw editorial.
_EDITORIAL_STARTS = re.compile(
    r"^(West Headnotes)\b",
    re.IGNORECASE,
)
_BRACKETED_NUMS = re.compile(r"\[\d+\]")


def _extract_frontmatter(text: str) -> tuple[str, str]:
    """Split text into YAML frontmatter and body. Returns (frontmatter, body)."""
    m = re.match(r"(---\n[\s\S]*?\n---\n*)", text)
    if m:
        return m.group(1), text[m.end():]
    return "", text


def _extract_star_pages(text: str) -> set[str]:
    """Extract star pagination markers like *293 from text."""
    return set(re.findall(r"\*\d+", text))


def _validate_westlaw_text(wl_text: str, db_text_body: str, case_name: str) -> list[str]:
    """Validate Westlaw text before replacement. Returns list of warnings (empty = OK)."""
    warnings = []

    # Reject if the text starts with Westlaw editorial sections that the
    # parser failed to strip. Court-published "Syllabus by the Court" and
    # "Attorneys and Law Firms" are allowed as starting markers.
    first_200 = wl_text[:200]
    if _EDITORIAL_STARTS.search(first_200):
        warnings.append("REJECT: Westlaw text starts with editorial section")
        return warnings

    if len(_BRACKETED_NUMS.findall(wl_text[:500])) >= 3:
        warnings.append("REJECT: Westlaw text has bracketed headnote references in opening")
        return warnings

    # Length sanity check
    if len(wl_text) < len(db_text_body) * 0.3 and len(db_text_body) > 500:
        warnings.append(
            f"REJECT: Westlaw text suspiciously short ({len(wl_text)} vs {len(db_text_body)} chars)"
        )
        return warnings

    # Star pagination cross-check (informational, not blocking)
    wl_stars = _extract_star_pages(wl_text)
    db_stars = _extract_star_pages(db_text_body)
    if db_stars and not wl_stars:
        warnings.append(f"INFO: DB has star pagination ({len(db_stars)} markers) but Westlaw does not")
    elif db_stars and wl_stars:
        missing = db_stars - wl_stars
        extra = wl_stars - db_stars
        if missing:
            warnings.append(f"INFO: Star pages in DB but not Westlaw: {sorted(missing)[:5]}")
        if extra:
            warnings.append(f"INFO: Star pages in Westlaw but not DB: {sorted(extra)[:5]}")

    return warnings


def process_all(
    db_path: Path = DEFAULT_DB_PATH,
    dry_run: bool = True,
    batch_name: str = "westlaw-text-merge",
    include_westlaw: bool = False,
    only_ids: list[int] | None = None,
) -> None:
    """Replace text for opinions with Westlaw sources.

    When include_westlaw is True, rows already at source_reporter='westlaw'
    are also considered. Use this after parser changes to re-extract — the
    merge writes a changelog row only when the new text differs in length
    from the current DB body.
    """
    conn = get_connection(db_path)

    # Find opinions with a westlaw .doc archived where text_content has not yet
    # been replaced. Skip 'ND' (ndcourts.gov is authoritative for 1997+) and
    # by default 'westlaw' (already merged — re-running would create no-op
    # changelog rows). Pass --include-westlaw to override after parser fixes.
    skip_filter = "AND o.source_reporter NOT IN ('ND')" if include_westlaw \
        else "AND o.source_reporter NOT IN ('ND', 'westlaw')"
    id_filter = ""
    params: tuple = ()
    if only_ids:
        placeholders = ",".join("?" * len(only_ids))
        id_filter = f"AND o.id IN ({placeholders})"
        params = tuple(only_ids)
    rows = conn.execute(f"""
        SELECT os.opinion_id, os.source_path,
               o.case_name, o.date_filed, o.source_reporter, o.text_content,
               qs.overall_score
        FROM opinion_sources os
        JOIN opinions o ON o.id = os.opinion_id
        LEFT JOIN quality_scores qs ON qs.opinion_id = o.id
        WHERE os.source_reporter = 'westlaw'
          {skip_filter}
          {id_filter}
        ORDER BY qs.overall_score ASC
    """, params).fetchall()

    if not rows:
        print("No eligible opinions with Westlaw sources found.")
        return

    nd_skipped = conn.execute("""
        SELECT COUNT(*) FROM opinion_sources os
        JOIN opinions o ON o.id = os.opinion_id
        WHERE os.source_reporter = 'westlaw' AND o.source_reporter = 'ND'
    """).fetchone()[0]

    print(f"Eligible for text replacement: {len(rows)}")
    if nd_skipped:
        print(f"Skipped (ndcourts.gov source, reference only): {nd_skipped}")
    print()

    replaced = 0
    rejected = 0
    errors = 0

    for row in rows:
        oid = row["opinion_id"]
        source_path = Path(row["source_path"])
        case_name = row["case_name"]
        date = row["date_filed"]
        score = row["overall_score"]

        score_str = f"{score:.0f}" if score is not None else "?"
        print(f"{case_name} ({date}) [score={score_str}]")

        # Load and parse Westlaw doc
        if not source_path.exists():
            print(f"  SKIP: source file not found: {source_path}")
            errors += 1
            continue

        try:
            wl_raw = _doc_to_text(source_path)
            parsed = _parse_westlaw_doc(wl_raw)
        except Exception as e:
            print(f"  ERROR: {e}")
            errors += 1
            continue

        # Prefer full bound entry (syllabus + attorneys + opinion + in-pub
        # rehearing) over body-only extraction. The bound entry is the
        # authoritative published form; the body-only extraction loses the
        # court's own syllabus and any pre-opinion published content.
        wl_text = parsed.get("full_bound_text") if parsed else None
        if not wl_text:
            wl_text = parsed.get("opinion_text") if parsed else None
        if not wl_text:
            print(f"  SKIP: could not parse opinion text from Westlaw doc")
            errors += 1
            continue

        # Split existing text into frontmatter + body
        frontmatter, db_body = _extract_frontmatter(row["text_content"])

        # Validate
        warnings = _validate_westlaw_text(wl_text, db_body, case_name)
        for w in warnings:
            print(f"  {w}")

        if any(w.startswith("REJECT") for w in warnings):
            rejected += 1
            continue

        # Build new text: preserve frontmatter, replace body
        new_text = frontmatter + wl_text

        old_len = len(row["text_content"])
        new_len = len(new_text)

        # Idempotency: skip if text is unchanged (re-runs after parser tweaks
        # should be no-ops where the parser output didn't move).
        if new_text == row["text_content"]:
            print(f"  SKIP: text unchanged ({old_len} chars)")
            continue

        if dry_run:
            print(f"  WOULD REPLACE: {old_len} → {new_len} chars")
        else:
            old_reporter = row["source_reporter"]
            conn.execute(
                "UPDATE opinions SET text_content = ?, source_reporter = 'westlaw', source_path = ? WHERE id = ?",
                (new_text, str(source_path), oid),
            )
            conn.execute(
                "UPDATE opinion_sources SET is_primary = 0 WHERE opinion_id = ?",
                (oid,),
            )
            conn.execute(
                "UPDATE opinion_sources SET is_primary = 1 "
                "WHERE opinion_id = ? AND source_reporter = 'westlaw'",
                (oid,),
            )
            conn.execute(
                "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) "
                "VALUES (?, ?, 'text_content', ?, ?)",
                (batch_name, oid, f"[{old_len} chars from {old_reporter}]",
                 f"[{new_len} chars from westlaw]"),
            )
            conn.execute(
                "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) "
                "VALUES (?, ?, 'source_reporter', ?, 'westlaw')",
                (batch_name, oid, old_reporter),
            )
            print(f"  REPLACED: {old_len} → {new_len} chars")

        replaced += 1

    if not dry_run:
        conn.commit()
        log_provenance(conn, "merge_westlaw_text", rows_affected=replaced,
                       notes=f"replaced={replaced}, rejected={rejected}, errors={errors}")

    conn.close()

    print(f"\n{'DRY RUN — ' if dry_run else ''}Summary:")
    print(f"  Replaced: {replaced}")
    print(f"  Rejected: {rejected}")
    print(f"  Errors: {errors}")

    if not dry_run and replaced > 0:
        print(f"\nRun quality_scan --rescan to update scores.")


def errors_report(db_path: Path, output: Path) -> None:
    """Generate a markdown triage report of all opinions where the merge
    would currently fail. Sub-classifies the failure modes so a human can
    decide whether to (a) fix the parser, (b) delete the bad westlaw link,
    or (c) accept the current state."""
    conn = get_connection(db_path)

    rows = conn.execute("""
        SELECT os.opinion_id, os.source_path,
               o.case_name, o.date_filed, o.source_reporter, o.text_content,
               qs.overall_score
        FROM opinion_sources os
        JOIN opinions o ON o.id = os.opinion_id
        LEFT JOIN quality_scores qs ON qs.opinion_id = o.id
        WHERE os.source_reporter = 'westlaw'
          AND o.source_reporter NOT IN ('ND', 'westlaw')
        ORDER BY qs.overall_score ASC
    """).fetchall()

    cite_lookup = {}
    for opinion_id in {r["opinion_id"] for r in rows}:
        cites = conn.execute(
            "SELECT citation FROM citations WHERE opinion_id = ? ORDER BY is_primary DESC, id",
            (opinion_id,),
        ).fetchall()
        cite_lookup[opinion_id] = [c["citation"] for c in cites]

    conn.close()

    categories: dict[str, list[dict]] = {
        "missing-opinion-header (modern Westlaw format)": [],
        "missing-opinion-header (no Attorneys section either)": [],
        "missing-all-citations-footer": [],
        "empty-opinion-body": [],
        "parse-returned-none": [],
        "westlaw-text-too-short": [],
        "file-missing": [],
        "other-error": [],
    }

    for r in rows:
        sp = Path(r["source_path"])
        entry = {
            "opinion_id": r["opinion_id"],
            "case_name": r["case_name"],
            "date_filed": r["date_filed"],
            "source_reporter": r["source_reporter"],
            "quality_score": r["overall_score"],
            "citations": cite_lookup.get(r["opinion_id"], []),
            "source_path": str(sp),
            "db_text_len": len(r["text_content"] or ""),
        }

        if not sp.exists():
            categories["file-missing"].append(entry)
            continue

        try:
            raw = _doc_to_text(sp)
        except Exception as e:
            entry["error"] = str(e)
            categories["other-error"].append(entry)
            continue

        entry["doc_len"] = len(raw)

        try:
            parsed = _parse_westlaw_doc(raw)
        except Exception as e:
            entry["error"] = str(e)
            categories["other-error"].append(entry)
            continue

        if parsed is None:
            categories["parse-returned-none"].append(entry)
            continue

        opinion_text = parsed.get("opinion_text") or ""
        if opinion_text:
            # Replace would have succeeded but length-rejected
            wl_len = len(opinion_text)
            entry["wl_text_len"] = wl_len
            entry["wl_pct_of_db"] = round(100 * wl_len / max(entry["db_text_len"], 1), 1)
            entry["wl_head"] = opinion_text[:400]
            entry["db_head"] = (r["text_content"] or "")[:400]
            categories["westlaw-text-too-short"].append(entry)
            continue

        # opinion_text is empty — diagnose why
        has_opinion_header = "\nOpinion\n" in raw or raw.startswith("Opinion\n")
        has_attorneys = "Attorneys and Law Firms" in raw
        has_all_cites = "All Citations" in raw[-2000:]

        if has_opinion_header and has_all_cites:
            categories["empty-opinion-body"].append(entry)
        elif not has_opinion_header and has_attorneys:
            # Find the author line after "Attorneys and Law Firms" for the report
            author_line = _find_modern_author_line(raw)
            entry["modern_author_line"] = author_line
            categories["missing-opinion-header (modern Westlaw format)"].append(entry)
        elif not has_opinion_header and not has_attorneys:
            categories["missing-opinion-header (no Attorneys section either)"].append(entry)
        elif not has_all_cites:
            categories["missing-all-citations-footer"].append(entry)
        else:
            categories["other-error"].append(entry)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w") as f:
        f.write(_render_report(categories))

    print(f"Report written to {output}")
    print()
    print("Summary:")
    total = sum(len(v) for v in categories.values())
    for name, items in categories.items():
        if items:
            print(f"  {len(items):>4}  {name}")
    print(f"  {total:>4}  TOTAL")


def _find_modern_author_line(raw: str) -> str | None:
    """For modern Westlaw exports without an 'Opinion' header, find the
    author/judge line that begins the opinion (e.g., 'ERICKSTAD, Judge.')."""
    lines = raw.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "Attorneys and Law Firms":
            for j in range(i + 1, min(i + 30, len(lines))):
                cand = lines[j].strip()
                if re.match(r"^[A-Z][A-Z'\-]+(?:\s+[A-Z][A-Z'\-]+)?,\s*(?:C\.\s*J|J|Judge|Justice|Chief\s+Justice)\.", cand):
                    return cand
    return None


def _render_report(categories: dict[str, list[dict]]) -> str:
    out = ["# Westlaw merge residuals — triage report", ""]
    out.append("Generated by `python -m ndcourts_mcp.merge_westlaw_text --errors-report`.")
    out.append("Each entry below is an opinion that has a `westlaw` row in `opinion_sources` but failed to merge into `text_content`.")
    out.append("")
    out.append("## Summary")
    out.append("")
    out.append("| Category | Count |")
    out.append("|---|---:|")
    total = 0
    for name, items in categories.items():
        if items:
            out.append(f"| {name} | {len(items)} |")
            total += len(items)
    out.append(f"| **Total** | **{total}** |")
    out.append("")

    for name, items in categories.items():
        if not items:
            continue
        out.append(f"## {name} ({len(items)})")
        out.append("")
        for e in items:
            cite = e["citations"][0] if e["citations"] else "(no citation)"
            score = f"{e['quality_score']:.0f}" if e.get("quality_score") is not None else "?"
            out.append(f"### {e['case_name']} — {cite} ({e['date_filed']})")
            out.append("")
            out.append(f"- opinion_id: {e['opinion_id']}, source_reporter: `{e['source_reporter']}`, quality_score: {score}")
            out.append(f"- westlaw doc: `{e['source_path']}`")
            if "doc_len" in e:
                out.append(f"- doc length: {e['doc_len']:,} chars; DB text length: {e['db_text_len']:,} chars")
            else:
                out.append(f"- DB text length: {e['db_text_len']:,} chars")
            if "modern_author_line" in e and e["modern_author_line"]:
                out.append(f"- detected author line (modern format): `{e['modern_author_line']}`")
            if "wl_pct_of_db" in e:
                out.append(f"- westlaw text length: {e['wl_text_len']:,} chars ({e['wl_pct_of_db']}% of DB)")
                out.append("")
                out.append("DB head:")
                out.append("```")
                out.append(e["db_head"])
                out.append("```")
                out.append("")
                out.append("Westlaw head:")
                out.append("```")
                out.append(e["wl_head"])
                out.append("```")
            if "error" in e:
                out.append(f"- error: `{e['error']}`")
            out.append("")
    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replace opinion text with clean Westlaw text"
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Show what would change (default)")
    parser.add_argument("--apply", action="store_true",
                        help="Actually replace text")
    parser.add_argument("--batch", default="westlaw-text-merge",
                        help="Changelog batch name")
    parser.add_argument("--errors-report", type=Path, metavar="PATH",
                        help="Write a markdown triage report of opinions where the merge would fail, then exit")
    parser.add_argument("--include-westlaw", action="store_true",
                        help="Also re-process rows already at source_reporter='westlaw'. Use after parser fixes.")
    parser.add_argument("--ids", type=str, default=None,
                        help="Comma-separated list of opinion IDs to limit processing to.")
    args = parser.parse_args()
    if args.errors_report:
        errors_report(args.db, args.errors_report)
        return
    only_ids = [int(x) for x in args.ids.split(",")] if args.ids else None
    process_all(args.db, dry_run=not args.apply, batch_name=args.batch,
                include_westlaw=args.include_westlaw, only_ids=only_ids)


if __name__ == "__main__":
    main()

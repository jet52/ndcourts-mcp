"""Strip Westlaw editorial content from the Synopsis section of westlaw-sourced opinions.

The bound-volume Westlaw .doc files used in this corpus place two distinct
kinds of content under the "Synopsis" header:

  1. A standardized Westlaw case-report stub (court of origin, parties, action
     description, disposition). This is Westlaw editorial work — not part of
     the court's published opinion.

  2. In a minority of older bound entries (~11%), the stub is followed by the
     court's published narrative statement of facts ("This is an action to..."
     or "The defendant was convicted of..."). That narrative *is* part of the
     court's public opinion as it appeared in the bound N.D. Reports volume.

Modern (post-~1980) Synopsis sections may also contain a Westlaw editorial
holding summary ("The Supreme Court, J., held that..."). That is Westlaw
editorial work.

This module strips the editorial stub and any holding summary while preserving
the court-authored narrative when present. If nothing court-authored remains,
the entire Synopsis section is dropped.

Usage:
    python -m ndcourts_mcp.strip_westlaw_synopsis --dry-run
    python -m ndcourts_mcp.strip_westlaw_synopsis --apply
"""

import argparse
import re
from pathlib import Path

from .db import DEFAULT_DB_PATH, get_connection, log_provenance


# Court-of-origin opener — first line of the Westlaw editorial stub.
_STUB_OPENER = re.compile(
    r"^(Appeal|Application|An\s+original|Original\s+\w+|Petition|Proceedings?|"
    r"Certified\s+question|Certiorari|Mandamus|Motion|"
    r"Action|Habeas\s+corpus|Writ\s+of|Specific\s+performance|Suit|"
    r"Prohibition|Quo\s+warranto|Injunction|Replevin|Foreclosure|"
    r"Garnishment|Contest|Contempt|Ejectment|Forfeiture|"
    r"Bastardy|Disbarment|Disciplinary|Disciplinary\s+action|"
    r"Divorce|Adoption|Guardianship|Probate|"
    r"Ex\s+parte|In\s+(?:re|the\s+Matter)|"
    r"On\s+(?:Appeal|Petition|Reargument|Rehearing|Motion|Original))\b",
    re.IGNORECASE,
)

# Lines to skip when scanning for the stub opener — e.g., a dissent-in-passing
# note that Westlaw sometimes places before the procedural opener.
_PRE_STUB_SKIP = re.compile(
    r"^[A-Z][A-Z. ,'\-]+,?\s*(?:C\.?\s*J\.|J\.|Judge|Justice|"
    r"District\s+Judge),?\s+(?:dissenting|concurring|"
    r"dissenting\s+in\s+part|concurring\s+in\s+part|"
    r"absent|disqualified|not\s+participating)\.?\s*$",
    re.IGNORECASE,
)

# Disposition line — ends the Westlaw editorial stub. Either on its own line
# or embedded at the end of the action-description line (e.g., "Affirmed.",
# "Reversed and remanded.").
# Disposition verbs that appear in Westlaw editorial stub closing lines.
# Match a line that begins with one of these verbs (or a compound like
# "Writ denied", "Petition for rehearing granted") followed by any tail of
# qualifying phrases ("and judgment entered", "with directions to reinstate",
# "on rehearing", etc.). The line must end after at most ~120 chars — court
# narrative paragraphs are much longer.
_DISP_VERBS = (
    r"(?:Affirmed|Reversed|Modified|Vacated|Remanded|Dismissed|Denied|Granted|"
    r"Sustained|Overruled|Stricken|Quashed|Issued|Refused|Rendered|Annulled|"
    r"Allowed|Awarded|Disallowed|Withdrawn|Set\s+aside|Ordered|Discharged|"
    r"Adopted|Revoked|Canceled|Cancelled|"
    r"against\s+\S+|for\s+\S+|in\s+accordance\s+with\s+opinion)"
)
_DISP_PREFIXES = (
    r"(?:Writ|Application|Petition|Petition\s+for\s+rehearing|Mandamus|"
    r"Habeas\s+corpus|Order|Conviction|Judgment|Rehearing|Reargument|"
    r"New\s+trial|Motion)\s+"
)
_DISPOSITION_LINE = re.compile(
    rf"^\s*(?:{_DISP_PREFIXES})?{_DISP_VERBS}"
    rf"(?:[,;]?\s+[A-Za-z][^.]{{0,400}})?\.?\s*$",
    re.IGNORECASE,
)
# Same pattern as a trailing match (disposition at end of a non-empty line).
# Period is optional — bound-volume Westlaw sometimes omits the period.
_DISPOSITION_TRAIL = re.compile(
    rf"(?:^|[\s.;])(?:{_DISP_PREFIXES})?{_DISP_VERBS}"
    rf"(?:[,;]?\s+[A-Za-z][^.]{{0,400}})?\.?\s*$",
    re.IGNORECASE,
)

# Westlaw editorial holding-summary opener: "The Supreme Court, [Justice], held that..."
_HOLDING_SUMMARY = re.compile(
    r"\bThe\s+Supreme\s+Court[\s,].*?\bheld\s+that\b",
    re.IGNORECASE | re.DOTALL,
)


def strip_synopsis_editorial(text: str) -> tuple[str, bool, str]:
    """Strip Westlaw editorial Synopsis content from `text`. Preserve any
    court-authored narrative that follows the editorial stub.

    Returns (new_text, modified, action) where action is one of:
        "no-synopsis"    — text has no Synopsis section
        "kept-narrative" — stub removed, court narrative preserved
        "dropped-all"    — entire Synopsis section removed (no court narrative)
        "no-stub-found"  — Synopsis present but no recognizable stub; left alone
    """
    syn_marker = "Synopsis\n"
    syn_pos = text.find(syn_marker)
    if syn_pos < 0:
        return text, False, "no-synopsis"

    body_start = syn_pos + len(syn_marker)

    # Find end of Synopsis section — the next major section header.
    end_candidates = [
        text.find("\nAttorneys and Law Firms", body_start),
        text.find("\nSyllabus by the Court", body_start),
        text.find("\nSyllabus\n", body_start),
        text.find("\nOpinion\n", body_start),
        text.find("\n**", body_start),  # star-pagination next-section marker
    ]
    end_candidates = [c for c in end_candidates if c > 0]
    if not end_candidates:
        return text, False, "no-stub-found"
    end_pos = min(end_candidates) + 1  # +1 to keep the leading newline with the next section

    synopsis_body = text[body_start:end_pos]
    lines = synopsis_body.splitlines(keepends=True)

    # Find where the editorial stub ends. Algorithm:
    #   1. Skip leading blank lines.
    #   2. The first non-blank line should match _STUB_OPENER. If not, bail
    #      (no recognizable stub — leave the Synopsis alone).
    #   3. Scan forward up to 15 lines for a disposition line OR a line ending
    #      with a disposition. That line is the last line of the stub.
    #   4. Also strip any "The Supreme Court, J., held that..." holding summary
    #      that appears before or after the stub disposition.

    i = 0
    # Skip leading blank lines and dissent-note lines that Westlaw sometimes
    # places before the procedural opener.
    while i < len(lines) and (not lines[i].strip()
                              or _PRE_STUB_SKIP.match(lines[i].strip())):
        i += 1

    if i >= len(lines):
        return text, False, "no-stub-found"

    # Two paths:
    #   A) First non-blank, non-dissent line matches a known procedural opener
    #      (Appeal from, Application by, Mandamus by, etc.). Scan up to 15
    #      lines for a disposition — the confident path. If the opener matches
    #      but no disposition is found in the entire Synopsis section, drop
    #      the entire section: Westlaw labeled this content "Synopsis", which
    #      is presumptively editorial when no court narrative is detectable.
    #   B) Opener doesn't match. Scan only the first 6 lines for a disposition.
    #      Court narrative paragraphs don't open with a disposition in the
    #      first few lines, so this catches narrative-style stubs with low
    #      false-positive risk. If no disposition found, leave alone.
    has_opener = _STUB_OPENER.match(lines[i].strip()) is not None
    scan_limit = 15 if has_opener else 6

    stub_end = i  # exclusive end of stub
    found_disposition = False
    for k in range(i, min(i + scan_limit, len(lines))):
        line = lines[k].rstrip()
        if _DISPOSITION_LINE.match(line.strip()):
            stub_end = k + 1
            found_disposition = True
            break
        elif _DISPOSITION_TRAIL.search(line):
            stub_end = k + 1
            found_disposition = True
            break

    if not found_disposition:
        if has_opener:
            # Confident this is a Westlaw editorial stub (procedural opener
            # matched) but no disposition line found. Drop the entire
            # Synopsis section as editorial-only content.
            new_text = text[:syn_pos] + text[end_pos:]
            return new_text, True, "dropped-all"
        # No opener and no disposition — could be court narrative. Leave alone.
        return text, False, "no-stub-found"

    # Now also strip a holding-summary block if it appears within the remaining
    # Synopsis content. Anchored to "The Supreme Court[...] held that"; runs
    # until the next disposition line.
    post_stub_lines = lines[stub_end:]
    remaining_joined = "".join(post_stub_lines)
    m = _HOLDING_SUMMARY.search(remaining_joined)
    if m:
        # Strip from the start of the holding-summary line to the next disposition.
        hs_start_in_joined = m.start()
        # Find which line the match starts on
        running = 0
        hs_start_line = stub_end
        for idx, ln in enumerate(post_stub_lines):
            if running + len(ln) > hs_start_in_joined:
                hs_start_line = stub_end + idx
                break
            running += len(ln)
        # Search forward for a disposition line
        hs_end_line = len(lines)
        for k in range(hs_start_line, min(hs_start_line + 40, len(lines))):
            line = lines[k].rstrip()
            if _DISPOSITION_LINE.match(line.strip()) or _DISPOSITION_TRAIL.search(line):
                hs_end_line = k + 1
                break
        # Splice out the holding-summary block
        lines = lines[:hs_start_line] + lines[hs_end_line:]

    # Reassemble. Drop leading blank lines after the stub.
    remaining = lines[stub_end:] if not m else lines[stub_end:]
    while remaining and not remaining[0].strip():
        remaining = remaining[1:]
    # Drop trailing blank lines too
    while remaining and not remaining[-1].strip():
        remaining = remaining[:-1]

    remaining_text = "".join(remaining)

    # If nothing meaningful is left (< 60 chars of non-whitespace), drop the
    # entire Synopsis section including the header.
    if len(remaining_text.strip()) < 60:
        new_text = text[:syn_pos] + text[end_pos:]
        return new_text, True, "dropped-all"

    # Keep the Synopsis header + court narrative
    new_synopsis = "Synopsis\n" + remaining_text
    if not new_synopsis.endswith("\n"):
        new_synopsis += "\n"
    new_text = text[:syn_pos] + new_synopsis + text[end_pos:]
    return new_text, True, "kept-narrative"


def process_all(db_path: Path = DEFAULT_DB_PATH, dry_run: bool = True,
                batch_name: str = "strip-westlaw-synopsis") -> None:
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT id, case_name, date_filed, text_content
        FROM opinions
        WHERE source_reporter = 'westlaw'
          AND text_content LIKE '%Synopsis%'
        ORDER BY id
    """).fetchall()

    stats = {"no-synopsis": 0, "kept-narrative": 0,
             "dropped-all": 0, "no-stub-found": 0}
    samples = {"kept-narrative": [], "no-stub-found": []}
    changes: list[tuple[int, str, str, int, int]] = []

    for oid, cn, df, txt in rows:
        new_txt, modified, action = strip_synopsis_editorial(txt)
        stats[action] += 1
        if modified:
            changes.append((oid, cn, df, len(txt), len(new_txt)))
        if action in samples and len(samples[action]) < 5:
            samples[action].append((oid, cn, df, len(txt), len(new_txt)))

    total_changed = stats["kept-narrative"] + stats["dropped-all"]
    print(f"Westlaw-sourced rows with 'Synopsis' marker: {len(rows)}")
    print(f"  dropped entire Synopsis section: {stats['dropped-all']}")
    print(f"  kept court narrative (stripped editorial): {stats['kept-narrative']}")
    print(f"  no recognizable stub — left unchanged: {stats['no-stub-found']}")
    print(f"  total modifications: {total_changed}")
    print()

    if samples["kept-narrative"]:
        print("Samples of kept-narrative (stub stripped, court text preserved):")
        for oid, cn, df, before, after in samples["kept-narrative"]:
            print(f"  oid={oid:5d}  {df}  {cn[:50]:50s}  {before} -> {after} chars (-{before-after})")
        print()

    if samples["no-stub-found"]:
        print("Samples of no-stub-found (left unchanged for human review):")
        for oid, cn, df, before, after in samples["no-stub-found"]:
            print(f"  oid={oid:5d}  {df}  {cn[:50]:50s}  {before} chars")
        print()

    if dry_run:
        print("Dry run — no DB changes. Use --apply to commit.")
        return

    cur = conn.cursor()
    for oid, cn, df, _, _ in changes:
        new_txt, _, _ = strip_synopsis_editorial(
            cur.execute("SELECT text_content FROM opinions WHERE id=?", (oid,)).fetchone()[0]
        )
        cur.execute("UPDATE opinions SET text_content = ? WHERE id = ?", (new_txt, oid))
        cur.execute(
            "INSERT INTO changelog (opinion_id, batch, field, old_value, new_value) "
            "VALUES (?, ?, 'text_content', ?, ?)",
            (oid, batch_name,
             f"[{len(_)} chars before strip]",
             f"[{len(new_txt)} chars after strip]"),
        )
    log_provenance(conn, "strip_westlaw_synopsis", rows_affected=len(changes),
                   notes=f"batch={batch_name}; dropped={stats['dropped-all']}, "
                         f"kept-narrative={stats['kept-narrative']}")
    conn.commit()
    print(f"Applied {len(changes)} updates as batch '{batch_name}'.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--apply", action="store_true",
                        help="Actually apply changes (default is dry-run)")
    parser.add_argument("--batch", default="strip-westlaw-synopsis-2026-05-13")
    args = parser.parse_args()
    process_all(args.db, dry_run=not args.apply, batch_name=args.batch)


if __name__ == "__main__":
    main()

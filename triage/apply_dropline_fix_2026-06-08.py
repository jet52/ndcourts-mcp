#!/usr/bin/env python3
"""Apply the dropped-cross-reference-line fix to statutes.db (TODO PL-1).

Isolation: compare section text parsed from OLD-code re-extraction vs NEW-code
(TOC-filter-fixed) re-extraction of the same cached PDFs. A fix section has
old != new. We apply ONLY sections that are ALL of:
  (1) exactly ONE `### § <sec>.` header corpus-wide  — not entangled with the
      separate body-line-as-header phantom-duplicate bug (TODO PL-2), which
      otherwise makes "which text is this section" order-dependent;
  (2) strictly additive — new == old with whole lines inserted only (so we only
      restore dropped lines, never delete or modify); and
  (3) DB == old — the DB holds the pre-fix text, so replacing with new is exactly
      the restoration.
Text is taken from each section's CANONICAL chapter file (chapter prefixes the
section number), never a phantom occurrence in another chapter.

    python triage/apply_dropline_fix_2026-06-08.py --old /tmp/ndcc_old \
        --new /tmp/ndcc_fixed [--db statutes.db] [--apply]
"""
import argparse
import difflib
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ndcourts_mcp import corpus  # noqa: E402
from ndcourts_mcp.ingest_statutes import parse_chapter  # noqa: E402

BATCH = "ndcc-dropline-fix-2026-06-08"
AUTHORITY = ("re-extraction of official ndlegis.gov cencode PDFs with TOC-filter "
             "dropped-line fix in scrape_nd_code.py; restores cross-reference "
             "lines wrongly skipped as TOC entries (see TODO PL-1)")


def parse_tree(root: Path):
    """Return (canonical_text, header_count): canonical_text[sec] is the body
    from the section's own chapter file; header_count[sec] counts headers across
    ALL files (phantom duplicates included)."""
    canonical: dict[str, str] = {}
    header_count: dict[str, int] = defaultdict(int)
    for md in sorted(root.rglob("chapter-*.md")):
        _, _, cnum, _, secs = parse_chapter(md.read_text())
        for s in secs:
            sec = s["sec_num"]
            header_count[sec] += 1
            if cnum and sec.startswith(cnum + "-"):
                canonical.setdefault(sec, s["text"].strip())
    return canonical, header_count


def strictly_additive(o: str, n: str) -> bool:
    sm = difflib.SequenceMatcher(None, o.split("\n"), n.split("\n"), autojunk=False)
    return all(tag not in ("replace", "delete") for tag, *_ in sm.get_opcodes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True, type=Path)
    ap.add_argument("--new", required=True, type=Path)
    ap.add_argument("--db", default=None)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    old, _ = parse_tree(args.old)
    new, hdr = parse_tree(args.new)
    db_path = Path(args.db) if args.db else corpus.resolve_corpus_db_path("ndcc")
    conn = corpus.get_corpus_connection(db_path, must_exist=True)
    rows = conn.execute(
        """SELECT p.id, pv.id, p.citation, p.heading, pv.text_content
             FROM provisions p JOIN provision_versions pv ON pv.id = p.current_version_id
            WHERE p.corpus = 'ndcc'""").fetchall()
    dbinfo = {c.replace("N.D.C.C. § ", "").strip(): (pid, vid, h, (t or "").strip())
              for pid, vid, c, h, t in rows}

    fix = [k for k in new if old.get(k, "") != new[k]]
    safe, held_dup, held_other = [], [], []
    for k in fix:
        pid, vid, heading, dbtxt = dbinfo.get(k, (None, None, None, None))
        if hdr.get(k, 0) != 1:
            held_dup.append(k)
        elif pid and strictly_additive(old[k], new[k]) and dbtxt == old[k]:
            safe.append((k, pid, vid, heading, dbtxt, new[k]))
        else:
            held_other.append(k)

    print(f"fix candidates (old!=new): {len(fix)}")
    print(f"  SAFE (unique header, additive, DB==old): {len(safe)}")
    print(f"  HELD bug-#2 phantom-dup header:          {len(held_dup)}")
    print(f"  HELD other (already-fixed/DB-diff):      {len(held_other)} -> {sorted(held_other)}")

    if not args.apply:
        print("\nDry run. Re-run with --apply to write.")
        return

    for k, pid, vid, heading, dbtxt, newtxt in safe:
        citation = f"N.D.C.C. § {k}"
        conn.execute(
            "INSERT INTO provisions_fts(provisions_fts, rowid, citation, heading, text_content) "
            "VALUES('delete', ?, ?, ?, ?)", (vid, citation, heading or "", dbtxt))
        conn.execute("UPDATE provision_versions SET text_content=? WHERE id=?", (newtxt, vid))
        corpus.index_version_fts(conn, vid, citation, heading, newtxt)
        conn.execute(
            """INSERT INTO changelog (batch, provision_id, version_id, field,
                                      old_value, new_value, authority)
               VALUES (?,?,?,?,?,?,?)""",
            (BATCH, pid, vid, "text_content",
             f"[dropped cross-ref line(s); {len(dbtxt)} chars]",
             f"[restored; {len(newtxt)} chars]", AUTHORITY))
    conn.execute(
        "INSERT INTO provenance (operation, command, source_paths, rows_affected, notes) "
        "VALUES (?,?,?,?,?)",
        ("apply_dropline_fix", BATCH, f"{args.old} vs {args.new}", len(safe),
         f"restored dropped cross-reference lines in {len(safe)} sections (TOC-filter fix)"))
    conn.commit()
    print(f"\nAPPLIED: {len(safe)} sections updated, batch {BATCH}.")


if __name__ == "__main__":
    main()

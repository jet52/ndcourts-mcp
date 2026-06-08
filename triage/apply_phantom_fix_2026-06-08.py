#!/usr/bin/env python3
"""Apply bug-#2 (phantom-duplicate-header) corrections to statutes.db (TODO PL-2).

After fixing both extraction bugs in scrape_nd_code.py, the re-extracted tree
(`--reextract`, default /tmp/ndcc_v2) has ZERO phantom-duplicate headers and is a
faithful, complete extraction of the official ndlegis.gov cencode PDFs. The
2026-06-07 DB build was corrupted for sections where a body cross-reference was
mis-parsed as a section header (fragmenting the section, the phantom winning at
INSERT-OR-IGNORE). For every ndcc section whose DB heading or text differs from
the clean re-extraction, replace heading + text_content with the re-extraction's,
re-index FTS, and log a changelog row.

Spot-verified that the re-extraction is the coherent/correct text and the DB is
the garbled/bloated one for the divergent sections (both v2-longer and v2-shorter).

    python triage/apply_phantom_fix_2026-06-08.py [--reextract /tmp/ndcc_v2]
        [--db statutes.db] [--apply] [--show N]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ndcourts_mcp import corpus  # noqa: E402
from ndcourts_mcp.ingest_statutes import parse_chapter  # noqa: E402

BATCH = "ndcc-phantom-header-fix-2026-06-08"
AUTHORITY = ("clean re-extraction of official ndlegis.gov cencode PDFs after fixing "
             "the phantom-duplicate-header bug (body cross-reference mis-parsed as a "
             "section header) in scrape_nd_code.py; 0 phantom dups corpus-wide (TODO PL-2)")


def reextract(root: Path):
    """sec_num -> (heading, text). v2 has no duplicates, so this is unambiguous."""
    out = {}
    for md in sorted(root.rglob("chapter-*.md")):
        _, _, _, _, secs = parse_chapter(md.read_text())
        for s in secs:
            out.setdefault(s["sec_num"], (s["heading"], s["text"].strip()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reextract", type=Path, default=Path("/tmp/ndcc_v2"))
    ap.add_argument("--db", default=None)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--show", type=int, default=10)
    args = ap.parse_args()

    new = reextract(args.reextract)
    db_path = Path(args.db) if args.db else corpus.resolve_corpus_db_path("ndcc")
    conn = corpus.get_corpus_connection(db_path, must_exist=True)
    rows = conn.execute(
        """SELECT p.id, pv.id, p.citation, p.heading, pv.text_content
             FROM provisions p JOIN provision_versions pv ON pv.id = p.current_version_id
            WHERE p.corpus = 'ndcc'""").fetchall()

    changed = []
    only_db = 0
    for pid, vid, citation, db_head, db_text in rows:
        sec = citation.replace("N.D.C.C. § ", "").strip()
        if sec not in new:
            only_db += 1
            continue
        nh, nt = new[sec]
        if (db_text or "").strip() != nt or (db_head or "") != (nh or ""):
            changed.append((sec, pid, vid, citation, db_head, db_text or "", nh, nt))
    only_new = [s for s in new if f"N.D.C.C. § {s}" not in
                {r[2] for r in rows}]

    text_diffs = sum(1 for c in changed if (c[5] or "").strip() != c[7])
    head_diffs = sum(1 for c in changed if (c[4] or "") != (c[6] or ""))
    print(f"DB ndcc sections: {len(rows)}   re-extracted: {len(new)}")
    print(f"sections to update: {len(changed)}  (text diffs {text_diffs}, heading diffs {head_diffs})")
    print(f"only-in-DB (not in re-extract): {only_db}   only-in-re-extract: {len(only_new)} {only_new[:6]}")
    print(f"\n--- sample (first {args.show}) ---")
    for sec, pid, vid, cit, dh, dt, nh, nt in changed[:args.show]:
        print(f"§ {sec}: DB len={len(dt)} -> new len={len(nt)} | head: {dh!r} -> {nh!r}")

    if not args.apply:
        print(f"\nDry run. {len(changed)} sections would be updated. Re-run with --apply.")
        return

    for sec, pid, vid, cit, dh, dt, nh, nt in changed:
        conn.execute(
            "INSERT INTO provisions_fts(provisions_fts, rowid, citation, heading, text_content) "
            "VALUES('delete', ?, ?, ?, ?)", (vid, cit, dh or "", dt))
        conn.execute("UPDATE provision_versions SET text_content=? WHERE id=?", (nt, vid))
        if (dh or "") != (nh or ""):
            conn.execute("UPDATE provisions SET heading=? WHERE id=?", (nh, pid))
        corpus.index_version_fts(conn, vid, cit, nh, nt)
        conn.execute(
            """INSERT INTO changelog (batch, provision_id, version_id, field,
                                      old_value, new_value, authority)
               VALUES (?,?,?,?,?,?,?)""",
            (BATCH, pid, vid, "heading+text_content",
             f"[corrupted by phantom header; head={dh!r}; {len(dt)} chars]",
             f"[clean re-extraction; head={nh!r}; {len(nt)} chars]", AUTHORITY))
    conn.execute(
        "INSERT INTO provenance (operation, command, source_paths, rows_affected, notes) "
        "VALUES (?,?,?,?,?)",
        ("apply_phantom_fix", BATCH, str(args.reextract), len(changed),
         f"corrected {len(changed)} sections fragmented by phantom-duplicate-header bug"))
    conn.commit()
    print(f"\nAPPLIED: {len(changed)} sections updated, batch {BATCH}.")


if __name__ == "__main__":
    main()

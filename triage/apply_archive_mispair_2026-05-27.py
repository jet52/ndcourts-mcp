#!/usr/bin/env python3
"""Detach 3 wrong-paired archive HTMLs surfaced by the neutral-cite-tightened
fix_archive_pairings (2026-05-27). Each is an EXTRA archive whose title neutral
cite belongs to a different opinion; the rightful owner already holds the file,
so the correct action is a plain detach (not the tool's "swap", whose swap_path
for Everett is itself a shared-table-page parallel contaminant).

Verified by docket + archive <title> + rightful-owner already-has-it:
  os 30641: 20070083.htm (=State v. Skarsgard 2007 ND 174) off 14837 (2007 ND 159);
            rightful owner 18608 (dk 20070083) already has it.
  os 30824: 20070369.htm (=State v. Torkelsen 2008 ND 137) off 15021 (2008 ND 141);
            rightful owner 18656 (dk 20070369) already has it.
  os 37026: 20090135.htm (=Matter of Hanenberg 2010 ND 8) off 15508 (Everett 2010 ND 4);
            rightful owner 15331 (dk 20090135) already has it. (This bad linkage was
            INTRODUCED by the old parallel-tolerant fix-archive-pairings-2026-05-04.)

Run with --apply to commit; default dry-run.
"""
import argparse
import sys

sys.path.insert(0, "/Users/jerod/code/ndcourts-mcp")
from ndcourts_mcp import db

BATCH = "fix-archive-mispair-2026-05-27"

# (os_id, source_path, off_oid, rightful_oid)
DETACHES = [
    (30641, "archive/2007/20070083.htm", 14837, 18608),
    (30824, "archive/2008/20070369.htm", 15021, 18656),
    (37026, "archive/2010/20090135.htm", 15508, 15331),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    conn = db.get_connection()

    ok = True
    for os_id, path, off, owner in DETACHES:
        r = conn.execute("SELECT opinion_id, source_path FROM opinion_sources WHERE id=?", (os_id,)).fetchone()
        if not r or r[0] != off or r[1] != path:
            print(f"  MISMATCH os {os_id}: expected ({off},{path!r}) got {r}"); ok = False
            continue
        # confirm rightful owner still holds the file (so detach loses nothing)
        held = conn.execute(
            "SELECT 1 FROM opinion_sources WHERE opinion_id=? AND source_path=?", (owner, path)
        ).fetchone()
        if not held:
            print(f"  ABORT: rightful owner {owner} does NOT hold {path}; refusing to detach"); ok = False
    if not ok:
        print("Pre-flight failed; no changes.")
        return 1

    for os_id, path, off, owner in DETACHES:
        print(f"detach os {os_id}: {path}  off oid {off}  (rightful owner {owner} retains it)")
        if args.apply:
            conn.execute("DELETE FROM opinion_sources WHERE id=?", (os_id,))
            conn.execute(
                "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) VALUES (?,?,?,?,?)",
                (BATCH, off, "opinion_sources.del",
                 f"row {os_id} {path} (wrong; belongs to oid {owner}, which already holds it)", None),
            )
    if args.apply:
        conn.commit()
        print("\nAPPLIED + committed.")
    else:
        print("\nDRY-RUN. Re-run with --apply.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Move the wrong-paired court-archive off Ellis to its true owner Reimers.

Surfaced by the 2026-05-27 multi-source diff audit (Ellis westlaw->court-archive
sim 0.004). court-archive/465/900333.htm is *Reimers Seed Co. v. Stedman* (N.D.
Court of Appeals, docket 900333CA) — wrongly attached to the Ellis disciplinary
order (oid 10796) via the shared 465 N.W.2d 175 parallel. Reimers (oid 20480)
exists, is correctly labeled COA, but lacks any court-archive source. fix_archive
_pairings didn't catch this because it only scans source_reporter='archive', not
'court-archive'.

Fix (all changelog-revertible):
  - move opinion_sources row 40567 (court-archive/465/900333.htm) 10796 -> 20480
  - backfill Reimers docket_number (currently NULL) = 'Civil No. 900333CA'
    (authoritative: stated in the archive opinion body)

Ellis keeps its correct NW2d/465/175.md + westlaw .doc (both verified Ellis).
Run with --apply to commit; default dry-run.
"""
import argparse
import sys

sys.path.insert(0, "/Users/jerod/code/ndcourts-mcp")
from ndcourts_mcp import db

BATCH = "fix-ellis-reimers-archive-2026-05-27"
OS_ID = 40567
PATH = "court-archive/465/900333.htm"
FROM_OID = 10796
TO_OID = 20480
NEW_DOCKET = "Civil No. 900333CA"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    conn = db.get_connection()

    r = conn.execute("SELECT opinion_id, source_path FROM opinion_sources WHERE id=?", (OS_ID,)).fetchone()
    if not r or r[0] != FROM_OID or r[1] != PATH:
        print(f"ABORT: os {OS_ID} expected ({FROM_OID},{PATH!r}) got {r}")
        return 1
    rd = conn.execute("SELECT case_name, court, docket_number FROM opinions WHERE id=?", (TO_OID,)).fetchone()
    if not rd or "Reimers" not in (rd[0] or ""):
        print(f"ABORT: target {TO_OID} is not Reimers: {rd}")
        return 1
    print(f"move os {OS_ID}: {PATH}  oid {FROM_OID} -> {TO_OID} ({rd[0]})")
    print(f"backfill docket on {TO_OID}: {rd[2]!r} -> {NEW_DOCKET!r}")

    if args.apply:
        conn.execute("UPDATE opinion_sources SET opinion_id=? WHERE id=?", (TO_OID, OS_ID))
        conn.execute(
            "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) VALUES (?,?,?,?,?)",
            (BATCH, FROM_OID, "opinion_sources.del",
             f"row {OS_ID} {PATH} (Reimers COA opinion; wrong on Ellis — moved to oid {TO_OID})", None))
        conn.execute(
            "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) VALUES (?,?,?,?,?)",
            (BATCH, TO_OID, "opinion_sources.court-archive", None,
             f"row {OS_ID} {PATH} (moved from oid {FROM_OID}; 465 N.W.2d 175 parallel collision)"))
        if rd[2] is None:
            conn.execute("UPDATE opinions SET docket_number=? WHERE id=?", (NEW_DOCKET, TO_OID))
            conn.execute(
                "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) VALUES (?,?,?,?,?)",
                (BATCH, TO_OID, "docket_number", None, NEW_DOCKET))
        conn.commit()
        print("\nAPPLIED + committed.")
    else:
        print("\nDRY-RUN. Re-run with --apply.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

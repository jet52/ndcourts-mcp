#!/usr/bin/env python3
"""Fix wrong-paired sources/cites surfaced by the 2026-05-27 multisource diff audit.

Three independent wrong-pairings (all changelog-revertible):

1. Johnson v. State name-collision (oid 14179 = 2005 ND 19, docket 20040252)
   accumulated the parallel cites AND NW2d source files of two OTHER Johnson
   opinions. Move them to their rightful owners and drop the duplicate archives:
     - cite '692 N.W.2d 784' + NW2d/692/784.md  -> oid 18544 (2005 ND 8, dk 20040203)
     - cite '709 N.W.2d 21'  + NW2d/709/21_4.md -> oid 18521 (2005 ND 197, dk 20050168)
     - archive 20040203.htm, archive 20050168.htm (dups; already on owners) -> delete
   Owners verified to currently LACK these cites/NW2d sources; they already hold
   their own ND markdown + archive.

2. State v. Delaney (oid 15515 = 2010 ND 52, dk 20090283) has Hoffner's per-docket
   archive 20090357.htm wrongly attached. Both share 789 N.W.2d 731 (Table) -- a
   summary-opinion table page (verified against the bound NW2d page image) -- so the
   shared cite is CORRECT and stays; only the per-docket archive is wrong. Hoffner
   (oid 20504) already holds 20090357.htm as its primary. -> delete the dup off Delaney.

3. King v. Stark County (oid 4746) NW/271/771.md is HTML/CSS junk from a failed CL
   scrape; the Westlaw .doc is the correct primary. -> detach the corrupt NW row.

Operate strictly by opinion_sources.id / citations.id (captured 2026-05-27) so the
script is unambiguous. Run with --apply to commit; default is dry-run.
"""
import argparse
import sys

sys.path.insert(0, "/Users/jerod/code/ndcourts-mcp")
from ndcourts_mcp import db

BATCH = "fix-diffaudit-pairings-2026-05-27"

# (citation_id, citation_text, from_oid, to_oid)
CITE_MOVES = [
    (23296, "692 N.W.2d 784", 14179, 18544),
    (23730, "709 N.W.2d 21", 14179, 18521),
]
# (source_id, source_path, from_oid, to_oid)
SOURCE_MOVES = [
    (14196, "NW2d/692/784.md", 14179, 18544),
    (14415, "NW2d/709/21_4.md", 14179, 18521),
]
# (source_id, source_path, oid, reason)
SOURCE_DELETES = [
    (29987, "archive/2005/20040203.htm", 14179, "dup; already on oid 18544"),
    (30214, "archive/2005/20050168.htm", 14179, "dup; already on oid 18521"),
    (23407, "archive/2010/20090357.htm", 15515, "Hoffner dk 20090357; already primary on oid 20504"),
    (4746, "NW/271/771.md", 4746, "corrupt CL scrape (HTML/CSS junk); westlaw .doc is primary"),
]


def log(conn, oid, field, old, new):
    conn.execute(
        "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) VALUES (?,?,?,?,?)",
        (BATCH, oid, field, old, new),
    )


def verify(conn):
    """Confirm the captured ids still hold the expected rows before mutating."""
    ok = True
    for cid, text, frm, _to in CITE_MOVES:
        r = conn.execute("SELECT opinion_id, citation FROM citations WHERE id=?", (cid,)).fetchone()
        if not r or r[0] != frm or r[1] != text:
            print(f"  MISMATCH cite id={cid}: expected ({frm},{text!r}) got {r}")
            ok = False
    for sid, path, frm, _to in SOURCE_MOVES:
        r = conn.execute("SELECT opinion_id, source_path FROM opinion_sources WHERE id=?", (sid,)).fetchone()
        if not r or r[0] != frm or r[1] != path:
            print(f"  MISMATCH source id={sid}: expected ({frm},{path!r}) got {r}")
            ok = False
    for sid, path, oid, _why in SOURCE_DELETES:
        r = conn.execute("SELECT opinion_id, source_path FROM opinion_sources WHERE id=?", (sid,)).fetchone()
        if not r or r[0] != oid or r[1] != path:
            print(f"  MISMATCH delete id={sid}: expected ({oid},{path!r}) got {r}")
            ok = False
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = db.get_connection()
    print("Pre-flight verification of captured row ids ...")
    if not verify(conn):
        print("ABORT: row ids no longer match expected state. Investigate before applying.")
        return 1
    print("  all ids match.\n")

    for cid, text, frm, to in CITE_MOVES:
        print(f"cite move: '{text}'  oid {frm} -> {to}")
        if args.apply:
            conn.execute("UPDATE citations SET opinion_id=? WHERE id=?", (to, cid))
            log(conn, frm, "citations.stray", f"'{text}' (belongs to oid {to})", f"moved to oid {to}")
            log(conn, to, "citations.add", None, f"'{text}' (moved from oid {frm}; name-collision)")

    for sid, path, frm, to in SOURCE_MOVES:
        print(f"source move: {path}  oid {frm} -> {to}")
        if args.apply:
            conn.execute("UPDATE opinion_sources SET opinion_id=? WHERE id=?", (to, sid))
            log(conn, frm, "opinion_sources.NW2d", f"row {sid} -> oid {frm}", f"row {sid} -> oid {to}")
            log(conn, to, "opinion_sources.NW2d", None, f"row {sid} {path} (moved from oid {frm})")

    for sid, path, oid, why in SOURCE_DELETES:
        print(f"source delete: {path}  off oid {oid}  ({why})")
        if args.apply:
            conn.execute("DELETE FROM opinion_sources WHERE id=?", (sid,))
            log(conn, oid, "opinion_sources.del", f"row {sid} {path} ({why})", None)

    if args.apply:
        conn.commit()
        print("\nAPPLIED + committed.")
    else:
        print("\nDRY-RUN (no changes). Re-run with --apply.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

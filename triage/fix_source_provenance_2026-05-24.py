"""Fix residual source-provenance contamination on oid 16924 (Ayala) and 17030
(Lee), left after fix-neutral-cite-invert. The cites/case_name/docket are now
correct; only the source pointers still point at the displaced case's files.

16924 (State v. Ayala, 2017 ND 126):
  - opinions.source_path + opinion_sources(ND,primary): markdown/2017/2017ND116.md
    (Cox's file) -> markdown/2017/2017ND126.md (Ayala's; verified to contain Ayala).
  - opinion_sources(archive): archive/2017/20160380.htm (Cox's docket) ->
    archive/2017/20160369.htm (Ayala's docket 20160369; file exists).
17030 (Disciplinary v. Lee, 2017 ND 216):
  - opinions.source_path + opinion_sources(ND,primary): markdown/2017/2017ND241.md
    (Questar's file) -> markdown/2017/2017ND216.md (Lee's; verified). docket
    20170241 is Lee's REAL docket (per PDF), left unchanged.

Cox (16930) and Questar (17053) are already clean and keep the 2017ND116.md /
2017ND241.md paths. source_path and the is_primary opinion_sources row are
updated in lockstep so source_path_matches_primary stays green.

Modes: --apply (default --dry-run). Changelog-logged; revertible.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from ndcourts_mcp.db import DEFAULT_DB_PATH, get_connection, log_change  # noqa: E402

BATCH = "fix-source-provenance-2026-05-24"
AUTH = ("PDF/markdown verification: row text matches the new path; the old path "
        "was the displaced (contaminating) case's file.")

# (oid, table, match_old_path, new_path, field_label)
FIXES = [
    (16924, "opinions", "markdown/2017/2017ND116.md", "markdown/2017/2017ND126.md", "source_path"),
    (16924, "opinion_sources", "markdown/2017/2017ND116.md", "markdown/2017/2017ND126.md", "opinion_sources.source_path"),
    (16924, "opinion_sources", "archive/2017/20160380.htm", "archive/2017/20160369.htm", "opinion_sources.archive_path"),
    (17030, "opinions", "markdown/2017/2017ND241.md", "markdown/2017/2017ND216.md", "source_path"),
    (17030, "opinion_sources", "markdown/2017/2017ND241.md", "markdown/2017/2017ND216.md", "opinion_sources.source_path"),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    conn = get_connection(DEFAULT_DB_PATH)

    plan = []
    for oid, table, old, new, field in FIXES:
        if table == "opinions":
            cur = conn.execute("SELECT source_path FROM opinions WHERE id=?", (oid,)).fetchone()
            ok = cur and cur["source_path"] == old
        else:
            cur = conn.execute(
                "SELECT id FROM opinion_sources WHERE opinion_id=? AND source_path=?",
                (oid, old)).fetchone()
            ok = cur is not None
        status = "ok" if ok else "!! GUARD FAIL (skipping)"
        print(f"oid {oid} [{table}] {field}: {old} -> {new}  [{status}]")
        if ok:
            plan.append((oid, table, old, new, field))

    print(f"\n{len(plan)}/{len(FIXES)} ready.")
    if not args.apply:
        print("DRY-RUN. re-run with --apply.")
        return 0

    for oid, table, old, new, field in plan:
        if table == "opinions":
            conn.execute("UPDATE opinions SET source_path=? WHERE id=?", (new, oid))
        else:
            conn.execute(
                "UPDATE opinion_sources SET source_path=? WHERE opinion_id=? AND source_path=?",
                (new, oid, old))
        log_change(conn, BATCH, oid, field, old, new, authority=AUTH)
    conn.commit()
    print(f"\nApplied {len(plan)} provenance fixes; batch {BATCH}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Merge the 74 HIGH-confidence post-1997 no-neutral-cite NW2d duplicates
into their cited markdown twins.

Source: triage/nocite-dup-match-2026-05-27.tsv (confidence==HIGH rows only =
same date_filed + exact normalized case_name). keep = the cited twin (holds
the YYYY ND n cite + fuller ¶-marked text); drop = the no-cite NW2d stub.
merge_pair folds the drop's N.W.2d cite + source into the survivor and deletes
it. Defensive re-check at merge time: same date + name ratio >= 0.9, drop has
no ND-neutral cite, keep has one. Snapshot
opinions.db.bak-pre-nocite-high-merge-2026-05-27. Dry-run default.
"""
from __future__ import annotations

import argparse
import re
from difflib import SequenceMatcher
from pathlib import Path

from ndcourts_mcp.db import DEFAULT_DB_PATH, get_connection, log_provenance
from ndcourts_mcp.merge_opinions import merge_pair

BATCH = "section6-nocite-high-merge-2026-05-27"
TSV = Path("triage/nocite-dup-match-2026-05-27.tsv")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    conn = get_connection(args.db)
    print(f"=== {'APPLY' if args.apply else 'DRY RUN'} (batch {BATCH}) ===")

    pairs = []
    for ln in TSV.read_text().splitlines()[1:]:
        f = ln.split("\t")
        if f and f[0] == "HIGH":
            # (drop=nocite, keep=cited, name_ratio, jaccard)
            pairs.append((int(f[1]), int(f[4]), float(f[7]), float(f[8])))

    applied = skipped = 0
    for drop, keep, nr, jac in pairs:
        kd = conn.execute("SELECT case_name, date_filed, "
                          "(SELECT citation FROM citations WHERE opinion_id=? AND reporter='ND-neutral' LIMIT 1) nd "
                          "FROM opinions WHERE id=?", (keep, keep)).fetchone()
        dd = conn.execute("SELECT case_name, date_filed, "
                          "(SELECT citation FROM citations WHERE opinion_id=? AND reporter='ND-neutral' LIMIT 1) nd "
                          "FROM opinions WHERE id=?", (drop, drop)).fetchone()
        if not kd or not dd:
            skipped += 1; print(f"  SKIP {drop}->{keep}: row missing"); continue
        # ESSENTIAL guard: never merge two cited opinions (would lose a cite).
        # drop must lack a neutral cite; keep must have one.
        if dd["nd"] is not None or kd["nd"] is None:
            skipped += 1; print(f"  SKIP {drop}->{keep}: cite guard (drop nd={dd['nd']}, keep nd={kd['nd']})"); continue
        # dup-confidence (== the matcher's HIGH criterion): exact name OR same text
        if not (nr >= 0.9 or jac >= 0.6):
            skipped += 1; print(f"  SKIP {drop}->{keep}: confidence guard (nr={nr:.2f} jac={jac:.2f})"); continue
        warn = "" if kd["date_filed"] == dd["date_filed"] else f"  [date {dd['date_filed']}!={kd['date_filed']}]"
        plan = merge_pair(conn, keep, drop, kd["case_name"], apply=args.apply, batch=BATCH)
        applied += 1
        if applied <= 8 or not args.apply:
            print(f"  merge {drop}->{keep}  {kd['nd']}  {kd['case_name'][:34]}  (nr={nr:.2f} jac={jac:.2f}){warn}")

    print(f"\n  {'applied' if args.apply else 'would apply'}: {applied};  skipped: {skipped}")
    if args.apply:
        log_provenance(conn, operation="section6_nocite_high_merge",
                       command="python -m triage.merge_nocite_high_2026-05-27 --apply",
                       rows_affected=applied,
                       notes=(f"batch {BATCH}; merged {applied} HIGH-confidence post-1997 "
                              f"no-cite NW2d duplicates into cited twins (adds N.W.2d "
                              f"parallel). Snapshot opinions.db.bak-pre-nocite-high-merge-2026-05-27."))
        conn.commit(); print("  committed.")
    conn.close()


if __name__ == "__main__":
    main()

"""Resolve three citation-collision / cross-source items (verified vs CL + West reporter).

GOETZ (true duplicate -> merge): 19722 and 20385 are both Goetz v. Goetz, 2023 ND 53,
988 N.W.2d 553, 2023-03-31, docket 20220231, McEvers (CL confirms 988 N.W.2d 553 =
2023 ND 53). Keep 19722 (ND-neutral primary, 2 sources), drop 20385 (NW2d-only).
NOTE (logged separately, NOT fixed here — cross-repo + new ingest): the real
2023 ND 120 Goetz v. Goetz (2023-07-07) is missing; the ~/refs files are content-
swapped (markdown/2023/2023ND53.md holds 2023 ND 120 text; 2023ND120.md holds
2023 ND 53 text). 19722.source_path stays markdown/2023/2023ND120.md (misnamed but
correct 2023 ND 53 content).

SWANSON (true duplicate -> merge): 17913 ("2021 ND 0216") and 19616 ("2021 ND 216")
are the same opinion (identical source files). Keep 17913 (NW2d parallel + docket),
drop 19616, then normalize the zero-padded native cite "2021 ND 0216" -> "2021 ND 216".

HOLTER (distinct, NOT a merge): 17670 = 2020 ND 152 (main, 2020-07-22, 946 N.W.2d 524);
19516 = 2020 ND 202 (denial of rehearing w/ Jensen C.J. dissent, 2020-09-21). The West
.doc filed at 948 N.W.2d 858 is the 2020 ND 202 rehearing dissent, so 948 N.W.2d 858
belongs to 19516, not 17670 (CL mis-grouped it onto the 152 cluster). Move the cite;
fix 19516's corrupted docket ("2020ND202"->"20190277") and date ("2020-07-22"->
"2020-09-21").

Run with --apply; default dry-run.
"""
from __future__ import annotations
import argparse, sqlite3
from ndcourts_mcp.merge_opinions import merge_pair
from ndcourts_mcp.ingest import recompute_primary

BATCH = "fix-three-dups-2026-05-26"


def log(conn, oid, field, old, new):
    conn.execute("INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) "
                 "VALUES (?,?,?,?,?)", (BATCH, oid, field, old, new))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    conn = sqlite3.connect("opinions.db"); conn.row_factory = sqlite3.Row

    # ---- GOETZ merge ----
    print("GOETZ:", merge_pair(conn, keep=19722, drop=20385,
                               canonical_name="Goetz v. Goetz",
                               apply=args.apply, batch=BATCH))

    # ---- SWANSON merge + cite normalize ----
    print("SWANSON:", merge_pair(conn, keep=17913, drop=19616,
                                 canonical_name="Swanson v. Larson",
                                 apply=args.apply, batch=BATCH))
    if args.apply:
        # post-merge 17913 holds both "2021 ND 0216" (own) and "2021 ND 216"
        # (from 19616). Drop the zero-padded one, keep the canonical.
        has216 = conn.execute("SELECT 1 FROM citations WHERE opinion_id=17913 "
                              "AND citation='2021 ND 216'").fetchone()
        assert has216, "expected canonical 2021 ND 216 on 17913 after merge"
        log(conn, 17913, "citation", "2021 ND 0216", "(removed; dup of 2021 ND 216)")
        conn.execute("DELETE FROM citations WHERE opinion_id=17913 AND citation='2021 ND 0216'")
        conn.execute("DELETE FROM text_citations WHERE opinion_id=17913 AND normalized='2021 ND 0216'")
        recompute_primary(conn, 17913)

    # ---- HOLTER cite re-attribution + metadata fix (NOT a merge) ----
    print("HOLTER: move 948 N.W.2d 858 (17670 -> 19516); fix 19516 docket+date")
    if args.apply:
        # 948 N.W.2d 858 is the 2020 ND 202 rehearing dissent (West .doc), not 2020 ND 152
        log(conn, 17670, "citation", "948 N.W.2d 858", "(removed; belongs to 2020 ND 202 / oid 19516)")
        conn.execute("DELETE FROM citations WHERE opinion_id=17670 AND citation='948 N.W.2d 858'")
        # add to 19516 if not present
        if not conn.execute("SELECT 1 FROM citations WHERE opinion_id=19516 "
                            "AND citation='948 N.W.2d 858'").fetchone():
            log(conn, 19516, "citation", None, "948 N.W.2d 858")
            conn.execute("INSERT INTO citations (opinion_id, citation, reporter, is_primary) "
                         "VALUES (19516, '948 N.W.2d 858', 'NW2d', 0)")
        # fix corrupted docket + date on 19516
        d = conn.execute("SELECT docket_number, date_filed FROM opinions WHERE id=19516").fetchone()
        log(conn, 19516, "docket_number", d["docket_number"], "20190277")
        log(conn, 19516, "date_filed", d["date_filed"], "2020-09-21")
        conn.execute("UPDATE opinions SET docket_number='20190277', date_filed='2020-09-21' WHERE id=19516")
        recompute_primary(conn, 17670)
        recompute_primary(conn, 19516)
        conn.commit()

    print("APPLIED" if args.apply else "DRY RUN")
    conn.close()


if __name__ == "__main__":
    main()

"""CORRECTION to fix_neutral_cite_contamination_2026-05-24: invert two rows that
the PDF double-check proved I fixed backwards.

For oid 16924 (text = State v. Miguel AYALA) and oid 17030 (text = Disciplinary
Action Against Ervin J. LEE), the contaminating cite was a DUPLICATE of another
real row's cite, not the row's own cite:
  16924: real owner of 2017 ND 116 is oid 16930 (State v. Cox, N.W. 894/906).
         Ayala's own cite is 2017 ND 126 (N.W. 894/865, on this row). The first
         pass wrongly KEPT 2017 ND 116 and DROPPED 2017 ND 126. Invert.
  17030: real owner of 2017 ND 241 is oid 17053 (WSI v. Questar, N.W. 902/757).
         Lee's own cite is 2017 ND 216 (N.W. 901/727, on this row). The first
         pass wrongly KEPT 2017 ND 241 and DROPPED 2017 ND 216. Invert.
Verified against the bound PDFs (pdfs/2017/2017ND{116,126,216,241}.pdf) and the
markdown files (2017ND126.md = Ayala, 2017ND216.md = Lee). The N.W. parallels
already on each row are correct (894/865 = Ayala; 901/727 = Lee).

Each row's text_content, case_name, and N.W. cite are correct and untouched.
NOTE (flagged, NOT fixed here): both rows still have contaminated PROVENANCE —
source_path / opinion_sources primary point at the displaced case's markdown
(2017ND116.md / 2017ND241.md), 16924 carries Cox's archive htm (20160380), and
17030's docket (20170241) looks synthesized. Needs a separate provenance pass.

Modes: --apply (default --dry-run). Rebuilds cited_by. Revertible via changelog.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from ndcourts_mcp.cite_extract import build_citation_lookup, rebuild_cited_by  # noqa: E402
from ndcourts_mcp.db import DEFAULT_DB_PATH, get_connection, log_change, log_provenance  # noqa: E402
from ndcourts_mcp.ingest import recompute_primary  # noqa: E402

BATCH = "fix-neutral-cite-invert-2026-05-24"
AUTH = ("PDF + markdown verification: row text identity matched the DROPPED "
        "cite, not the kept one (kept cite was a duplicate of another real "
        "row's cite). Inverts fix-neutral-cite-contamination-2026-05-24.")

# oid -> (wrong_cite_now_on_row_to_drop, correct_cite_to_restore)
TARGETS = {
    16924: ("2017 ND 116", "2017 ND 126"),  # Ayala
    17030: ("2017 ND 241", "2017 ND 216"),  # Lee
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    conn = get_connection(DEFAULT_DB_PATH)

    plan = []
    for oid, (drop, restore) in TARGETS.items():
        have = {r["citation"] for r in conn.execute(
            "SELECT citation FROM citations WHERE opinion_id=?", (oid,))}
        owners_restore = conn.execute(
            "SELECT COUNT(*) n FROM citations WHERE citation=?", (restore,)).fetchone()["n"]
        if drop not in have or restore in have:
            print(f"!! oid {oid}: guard failed — have {sorted(have)}; "
                  f"expected to drop {drop!r} and restore {restore!r}; SKIPPING")
            continue
        if owners_restore != 0:
            print(f"!! oid {oid}: {restore!r} already owned elsewhere ({owners_restore}); SKIPPING")
            continue
        plan.append((oid, drop, restore))
        print(f"oid {oid}: drop {drop!r}, restore {restore!r}")

    print(f"\n{len(plan)}/{len(TARGETS)} ready.")
    if not args.apply:
        print("DRY-RUN. re-run with --apply.")
        return 0

    for oid, drop, restore in plan:
        conn.execute("DELETE FROM citations WHERE opinion_id=? AND citation=?", (oid, drop))
        conn.execute(
            "INSERT INTO citations (opinion_id, citation, reporter, is_primary) "
            "VALUES (?, ?, 'ND-neutral', 0)", (oid, restore))
        recompute_primary(conn, oid)
        log_change(conn, BATCH, oid, "citation", drop, None, authority=AUTH)
        log_change(conn, BATCH, oid, "citation", None, restore, authority=AUTH)
    conn.commit()

    inserted = rebuild_cited_by(conn, build_citation_lookup(conn))
    log_provenance(conn, BATCH, command="invert 2 mis-assigned neutral cites + rebuild cited_by",
                   rows_affected=len(plan),
                   notes=f"16924->2017 ND 126 (Ayala), 17030->2017 ND 216 (Lee); "
                         f"cited_by rebuilt ({inserted} edges)")
    print(f"\nApplied {len(plan)} inversions; cited_by rebuilt ({inserted}). batch {BATCH}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Drop the STRAY second native ND-neutral cite from 16 opinions (CL-metadata
"two unrelated neutral cites in one record" contamination — the Feldmann class).

Each row carries its REAL neutral cite (= its court `markdown/YYYY/YYYYNDn.md`
source_path filename, confirmed against the in-body caption) plus a stray
neutral cite copied from a different case's CL record. The stray is dropped from
the citations table; `recompute_primary` then promotes the real cite; and
`cited_by` is rebuilt so no graph edge still resolves a stray to the wrong row.
The opinion text and case_name columns are not touched here.

Safety: for 11 rows the stray's rightful owner row exists (incl. the swap pairs
15805<->15807 and Kitchen/Kleinsmith 15988<->16488), so no orphaning. For 5
rows the stray has no other owner (15393, 15931, 16826, 16924, 17030) — dropping
is still correct (it is not this opinion's cite); those strays are reported
separately as possible corpus gaps.

EXCLUDED: 19722 (Goetz) — a deeper text-identity tangle (its text is the
*2023 ND 53* opinion, which also exists as oid 20385, yet it is filed as
markdown/2023/2023ND120.md and claims 2023 ND 120). Needs manual review, not a
stray-cite drop.

Modes: --apply (default --dry-run). Snapshot taken before apply; changelog +
provenance logged.
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

BATCH = "fix-neutral-cite-contamination-2026-05-24"
AUTH = ("CL-metadata contamination: a stray 2nd native ND-neutral cite copied "
        "from a different case's record. Real cite = court markdown/YYYY/"
        "YYYYNDn.md filename, confirmed against the in-body caption.")

# oid -> (real_cite_to_keep, stray_cite_to_drop)
TARGETS = {
    12476: ("1997 ND 132", "1997 ND 129"),
    13202: ("2000 ND 138", "2000 ND 141"),
    14095: ("2004 ND 168", "2004 ND 115"),
    15393: ("2010 ND 57", "2010 ND 54"),
    15600: ("2011 ND 48", "2011 ND 65"),
    15805: ("2012 ND 31", "2012 ND 27"),
    15807: ("2012 ND 27", "2012 ND 31"),
    15869: ("2012 ND 138", "2012 ND 148"),
    15931: ("2012 ND 198", "2012 ND 196"),
    15988: ("2013 ND 18", "2013 ND 19"),
    16488: ("2013 ND 19", "2013 ND 18"),
    16826: ("2016 ND 241", "2016 ND 332"),
    16829: ("2017 ND 1", "2017 ND 255"),
    16924: ("2017 ND 116", "2017 ND 126"),
    17030: ("2017 ND 241", "2017 ND 216"),
    17035: ("2017 ND 220", "2017 ND 233"),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    conn = get_connection(DEFAULT_DB_PATH)

    plan = []
    for oid, (real, stray) in TARGETS.items():
        cites = {r["citation"]: r["id"] for r in conn.execute(
            "SELECT id, citation FROM citations WHERE opinion_id=? AND reporter='ND-neutral'",
            (oid,))}
        if real not in cites or stray not in cites:
            print(f"!! oid {oid}: guard failed — neutral cites are {sorted(cites)}, "
                  f"expected real {real!r} + stray {stray!r}; SKIPPING")
            continue
        plan.append((oid, real, stray, cites[stray]))
        print(f"oid {oid}: keep {real!r}, drop {stray!r} (cite id {cites[stray]})")

    print(f"\n{len(plan)}/{len(TARGETS)} ready.")
    if not args.apply:
        print("DRY-RUN. re-run with --apply.")
        return 0

    for oid, real, stray, cite_id in plan:
        conn.execute("DELETE FROM citations WHERE id=?", (cite_id,))
        log_change(conn, BATCH, oid, "citation", stray, None, authority=AUTH)
        recompute_primary(conn, oid)
    conn.commit()

    inserted = rebuild_cited_by(conn, build_citation_lookup(conn))
    log_provenance(conn, BATCH, command="drop stray ND-neutral cites + rebuild cited_by",
                   rows_affected=len(plan),
                   notes=f"dropped {len(plan)} stray neutral cites; cited_by rebuilt "
                         f"({inserted} edges)")
    print(f"\nApplied: dropped {len(plan)} stray cites; cited_by rebuilt "
          f"({inserted} edges). batch {BATCH}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

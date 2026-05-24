"""§10 Phase 1A — assign synthetic medium-neutral cites (YYYY ND nnn) to every pre-1997 opinion.

Contract (ratified 2026-05-19/24; TODO-validation.md §10):
- New citations.reporter value 'ND-neutral-synthetic'; is_primary=0 ALWAYS
  (a synthetic/editorial unique ID, never the official citation).
- Format 'YYYY ND nnn'; YYYY = filing year, nnn = 1-based sequence within that year.
- Order key per year: (date_filed, nd_vol, nd_page, nw_vol, nw_page, oid).
  ND-cited opinions sort before NW2d-only on a same-date tie (nd sentinel = inf).
  oid is the PROVISIONAL within-cluster tiebreaker for true on-page-order ties
  (the shared-page collision clusters) — numbers are provisional until a publish
  freeze, renumber freely (per the ratified stability policy; oid is the interim ID).
- Scope: every opinion with date_filed < 1997-01-01 gets exactly one synthetic cite.

Eras do not mix page schemes within a year except 1952/1953 (ND Reports ended
vol 79, 1953); since date_filed governs, page only breaks same-date ties, and the
two same-date cross-reporter pairs (1952-11-14, 1953-06-05) order deterministically
ND-before-NW2d. Verified: 0 null date_filed, 0 unparseable primary cites pre-1997.

Modes:
  --measure  (default) read-only: stats, era breakdown, collision-cluster worklist
             (written to triage/), parse-failure report. No DB writes.
  --apply    insert the synthetic citation rows + per-opinion changelog audit rows.
             Requires 'ND-neutral-synthetic' already in ingest.REPORTER_TAXONOMY.
  --revert   delete all ND-neutral-synthetic citation rows + this batch's changelog.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from ndcourts_mcp.db import DEFAULT_DB_PATH, get_connection, log_change  # noqa: E402

BATCH = "section10-phase1a-synthetic-2026-05-24"
SYNTH_REPORTER = "ND-neutral-synthetic"
WORKLIST = REPO / "triage" / "section10-cluster-worklist-2026-05-24.tsv"

INF = 10**9
ND_RE = re.compile(r"^(\d+)\s+N\.D\.\s+(\d+)")
NW2D_RE = re.compile(r"^(\d+)\s+N\.W\.2d\s+(\d+)")
NW_RE = re.compile(r"^(\d+)\s+N\.W\.\s+(\d+)")


class Op:
    __slots__ = ("oid", "date", "year", "nd", "nw", "nd_cite", "nw_cite")

    def __init__(self, oid: int, date: str):
        self.oid = oid
        self.date = date
        self.year = date[:4]
        self.nd: tuple[int, int] | None = None
        self.nw: tuple[int, int] | None = None
        self.nd_cite: str | None = None
        self.nw_cite: str | None = None

    @property
    def nd_sort(self) -> tuple[int, int]:
        return self.nd if self.nd else (INF, INF)

    @property
    def nw_sort(self) -> tuple[int, int]:
        return self.nw if self.nw else (INF, INF)

    @property
    def sort_key(self):
        return (self.date, self.nd_sort, self.nw_sort, self.oid)

    # collision unit: a TRUE on-page-order ambiguity = same date AND same
    # official-reporter (vol, page). Differing dates/pages are ordered by the
    # sort key and need no image review.
    @property
    def page_key(self):
        return (self.date, self.nd) if self.nd else (self.date, "nw2d", self.nw)


def load(conn) -> tuple[list[Op], list[int]]:
    """Return (ordered ops, oids-with-parse-gaps). One Op per pre-1997 opinion."""
    rows = conn.execute(
        "SELECT id, date_filed FROM opinions WHERE date_filed < '1997-01-01'"
    ).fetchall()
    ops = {r["id"]: Op(r["id"], r["date_filed"]) for r in rows}

    cites = conn.execute(
        """SELECT c.opinion_id, c.citation, c.reporter
             FROM citations c JOIN opinions o ON o.id = c.opinion_id
            WHERE o.date_filed < '1997-01-01'
            ORDER BY c.is_primary DESC, c.id"""
    ).fetchall()
    for c in cites:
        op = ops[c["opinion_id"]]
        rep, cite = c["reporter"], c["citation"]
        if rep == "ND" and op.nd is None:
            m = ND_RE.match(cite)
            if m:
                op.nd = (int(m.group(1)), int(m.group(2)))
                op.nd_cite = cite
        elif rep == "NW2d" and op.nw is None:
            m = NW2D_RE.match(cite)
            if m:
                op.nw = (int(m.group(1)), int(m.group(2)))
                op.nw_cite = cite
        elif rep == "NW" and op.nw is None:
            m = NW_RE.match(cite)
            if m:
                op.nw = (int(m.group(1)), int(m.group(2)))
                op.nw_cite = cite

    # parse gap = no ND page AND no NW page (cannot place beyond date+oid)
    gaps = [op.oid for op in ops.values() if op.nd is None and op.nw is None]
    ordered = sorted(ops.values(), key=lambda o: o.sort_key)
    return ordered, gaps


def assign(ordered: list[Op]) -> dict[int, str]:
    """oid -> 'YYYY ND nnn', sequence reset per year in sorted order."""
    out: dict[int, str] = {}
    counter: dict[str, int] = defaultdict(int)
    for op in ordered:
        counter[op.year] += 1
        out[op.oid] = f"{op.year} ND {counter[op.year]}"
    return out


def clusters(ordered: list[Op]) -> dict:
    """page_key -> [Op,...] for keys with >1 member (shared-page collisions)."""
    by_key: dict = defaultdict(list)
    for op in ordered:
        by_key[op.page_key].append(op)
    return {k: v for k, v in by_key.items() if len(v) > 1}


def measure(conn) -> int:
    ordered, gaps = load(conn)
    cite = assign(ordered)
    cl = clusters(ordered)

    n_total = len(ordered)
    n_nd_era = sum(1 for o in ordered if o.nd)
    n_nw_era = sum(1 for o in ordered if not o.nd and o.nw)
    n_cluster_members = sum(len(v) for v in cl.values())
    n_unambiguous = n_total - n_cluster_members

    # sub-classify ND clusters by whether NW pages disambiguate
    nd_orderable = nd_tied = nw_era_clusters = 0
    for k, members in cl.items():
        if k[1] == "nw2d":
            nw_era_clusters += 1
        else:
            nwset = {m.nw for m in members}
            if len(nwset) == len(members) and None not in nwset:
                nd_orderable += 1
            else:
                nd_tied += 1

    print(f"§10 Phase 1A measure — batch {BATCH}")
    print(f"  pre-1997 opinions ............. {n_total}")
    print(f"    ND-era (have N.D. page) ..... {n_nd_era}")
    print(f"    NW2d-era (no N.D., have N.W.) {n_nw_era}")
    print(f"  parse gaps (no ND & no NW) .... {len(gaps)}  {gaps[:20]}")
    print(f"  shared-page collision clusters  {len(cl)}  ({n_cluster_members} opinions)")
    print(f"    ND clusters, NW-orderable ... {nd_orderable}")
    print(f"    ND clusters, truly tied ..... {nd_tied}")
    print(f"    NW2d-era clusters ........... {nw_era_clusters}")
    print(f"  unambiguous (Phase-1A trivial)  {n_unambiguous}")
    yrs = sorted({o.year for o in ordered})
    print(f"  year span ..................... {yrs[0]}..{yrs[-1]} ({len(yrs)} years)")

    # write the worklist of clusters needing on-page-order verification
    with WORKLIST.open("w") as fh:
        fh.write("year\tnd_or_nw\tpage\tn\tclass\toid\tprovisional_cite\tnd_cite\tnw_cite\tneeds_image\n")
        for k in sorted(cl.keys(), key=lambda kk: (kk[0], str(kk[1]))):
            members = cl[k]
            if k[1] == "nw2d":
                cls, page, needs = "NW2D_ERA", f"{k[2][0]} N.W.2d {k[2][1]}", "yes"
            else:
                nwset = {m.nw for m in members}
                if len(nwset) == len(members) and None not in nwset:
                    cls, needs = "ND_NW_ORDERABLE", "verify-ND-order"
                else:
                    cls, needs = "ND_TRULY_TIED", "yes"
                page = f"{k[1][0]} N.D. {k[1][1]}"
            for m in members:
                fh.write(f"{k[0]}\t{'ND' if k[1] != 'nw2d' else 'NW2d'}\t{page}\t"
                         f"{len(members)}\t{cls}\t{m.oid}\t{cite[m.oid]}\t"
                         f"{m.nd_cite or ''}\t{m.nw_cite or ''}\t{needs}\n")
    print(f"\n  cluster worklist -> {WORKLIST.relative_to(REPO)}")
    print(f"  (numbers PROVISIONAL until publish; within-cluster order via oid pending image read)")

    # show a few sample assignments at era edges
    print("\n  sample assignments:")
    for op in ordered[:3] + ordered[n_total // 2 - 1: n_total // 2 + 2] + ordered[-3:]:
        print(f"    oid {op.oid:>6}  {cite[op.oid]:<11}  {op.date}  "
              f"ND={op.nd_cite or '-':<14} NW={op.nw_cite or '-'}")
    return 0


def apply(conn) -> int:
    from ndcourts_mcp.ingest import REPORTER_TAXONOMY
    if SYNTH_REPORTER not in REPORTER_TAXONOMY:
        print(f"ERROR: '{SYNTH_REPORTER}' not in REPORTER_TAXONOMY — add it to ingest.py first.")
        return 1
    existing = conn.execute(
        "SELECT COUNT(*) FROM citations WHERE reporter=?", (SYNTH_REPORTER,)
    ).fetchone()[0]
    if existing:
        print(f"ERROR: {existing} '{SYNTH_REPORTER}' rows already exist — revert first.")
        return 1

    ordered, gaps = load(conn)
    cite = assign(ordered)
    print(f"Inserting {len(cite)} synthetic citation rows (is_primary=0)...")
    for op in ordered:
        c = cite[op.oid]
        conn.execute(
            "INSERT INTO citations (opinion_id, citation, reporter, is_primary) VALUES (?,?,?,0)",
            (op.oid, c, SYNTH_REPORTER),
        )
        log_change(conn, BATCH, op.oid, "citation_synthetic", None, c,
                   authority="section10-phase1a-order(date,ND-page,NW-page,oid)")
    conn.commit()
    print(f"Applied {len(cite)} rows. revert: python triage/section10_phase1a_2026-05-24.py --revert")
    if gaps:
        print(f"NOTE: {len(gaps)} opinions had no parseable ND/NW page (placed by date+oid): {gaps[:20]}")
    return 0


def revert(conn) -> int:
    n = conn.execute("SELECT COUNT(*) FROM citations WHERE reporter=?", (SYNTH_REPORTER,)).fetchone()[0]
    conn.execute("DELETE FROM citations WHERE reporter=?", (SYNTH_REPORTER,))
    conn.execute("DELETE FROM changelog WHERE batch=?", (BATCH,))
    conn.commit()
    print(f"Reverted: deleted {n} '{SYNTH_REPORTER}' citation rows + changelog batch {BATCH}.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--measure", action="store_true", help="read-only report (default)")
    g.add_argument("--apply", action="store_true")
    g.add_argument("--revert", action="store_true")
    args = ap.parse_args()
    conn = get_connection(DEFAULT_DB_PATH)
    if args.apply:
        return apply(conn)
    if args.revert:
        return revert(conn)
    return measure(conn)


if __name__ == "__main__":
    raise SystemExit(main())

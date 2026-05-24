"""§10 cluster-order fix — apply the KNOWN on-page publication order to the
synthetic YYYY ND nnn cites, replacing the provisional oid-tiebreaker order.

Scope: only clusters whose true N.D. on-page order is authoritatively known.
  - 3 N.D. 538 (Globe→Kellogg) — vol 3 bound read, prior session (N.D.=N.W.).
  - 9 N.D. 608-614 Emmons block — vol 9 bound scan read this session
    (~/refs/nd/opin/N.D./9/_bound-volume.pdf, pp.608-614 = pdf 718-724,
    offset +110). Top-to-bottom on-page order transcribed below.
  - 44 N.D. 247 (Nelson→Lammadee) already correct — not touched.

Mechanism: a pure WITHIN-CLUSTER permutation — each cluster keeps its exact set
of sequence numbers (e.g. {66,67}); only the oid->number mapping is reordered to
match true publication order. No other opinion's number changes; per-year
uniqueness is preserved. Numbers remain PROVISIONAL until the publish freeze.

Modes: --apply (default --dry-run). Revert via changelog batch (old cite stored).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from ndcourts_mcp.db import DEFAULT_DB_PATH, get_connection, log_change  # noqa: E402

BATCH = "fix-section10-cluster-order-2026-05-24"
SYNTH = "ND-neutral-synthetic"

# Each entry: list of oids in TRUE published on-page order (top to bottom).
# The cluster's sequence numbers are read from the DB and re-dealt in this order.
ORDERED_CLUSTERS = [
    # 3 N.D. 538 — Globe Investment first, then Kellogg (vol 3; N.D.=N.W.)
    [5275, 5274],
    # 9 N.D. 608 — Cranmer, Davidson
    [20489, 5754],
    # 9 N.D. 609 — Davidson, Baker, Couch
    [20491, 20490, 5753],
    # 9 N.D. 610 — Cranmer, Ganger, Kelly
    [20492, 20493, 5752],
    # 9 N.D. 611 — Lilly, McKenzie, McKenzie (two identical -> oid order)
    [5751, 20494, 20500],
    # 9 N.D. 612 — McKenzie, McLain, Mellon
    [20495, 20496, 5750],
    # 9 N.D. 613 — Mellon, Mellon (two identical -> oid order), Robinson
    [20497, 20501, 5749],
    # 9 N.D. 614 — Thistlewaite, Thistlewaite (identical -> oid order)
    [5748, 20502],
]

AUTHORITY = ("on-page order: 3 N.D. 538 vol-3 bound (prior); 9 N.D. 608-614 "
             "vol-9 bound scan pp.718-724")


def synth_cite(conn, oid: int) -> tuple[int, str]:
    rows = conn.execute(
        "SELECT id, citation FROM citations WHERE opinion_id=? AND reporter=?",
        (oid, SYNTH),
    ).fetchall()
    if len(rows) != 1:
        raise SystemExit(f"oid {oid}: expected 1 synthetic cite, found {len(rows)}")
    return rows[0]["id"], rows[0]["citation"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    args = ap.parse_args()
    conn = get_connection(DEFAULT_DB_PATH)

    plan = []  # (cite_row_id, oid, old_cite, new_cite)
    n_changed = 0
    for cluster in ORDERED_CLUSTERS:
        current = [synth_cite(conn, oid) for oid in cluster]  # in true order
        numbers = sorted((c for _, c in current),
                         key=lambda s: int(s.rsplit(" ", 1)[1]))  # ascending
        # sanity: all same year, contiguous set preserved
        years = {c.rsplit(" ", 2)[0] for _, c in current}
        if len(years) != 1:
            raise SystemExit(f"cluster {cluster}: mixed years {years}")
        for oid, (row_id, old_cite), new_cite in zip(cluster, current, numbers):
            tag = "  (same)" if old_cite == new_cite else "  <-- CHANGE"
            print(f"  oid {oid:>6}  {old_cite:>11} -> {new_cite:<11}{tag}")
            if old_cite != new_cite:
                n_changed += 1
            plan.append((row_id, old_cite, new_cite))
        print()

    print(f"{'APPLY' if args.apply else 'DRY-RUN'}: {n_changed} cite strings change "
          f"across {len(ORDERED_CLUSTERS)} clusters ({len(plan)} members total).")
    if not args.apply:
        print("re-run with --apply to write.")
        return 0

    # Two-pass to avoid any transient duplicate ambiguity: park to temp, then set.
    for row_id, _old, _new in plan:
        conn.execute("UPDATE citations SET citation = citation || '#tmp' WHERE id=?",
                     (row_id,))
    for row_id, old_cite, new_cite in plan:
        conn.execute("UPDATE citations SET citation=? WHERE id=?", (new_cite, row_id))
        if old_cite != new_cite:
            # find the oid for the changelog row
            oid = conn.execute("SELECT opinion_id FROM citations WHERE id=?",
                               (row_id,)).fetchone()[0]
            log_change(conn, BATCH, oid, "citation_synthetic_order",
                       old_cite, new_cite, authority=AUTHORITY)
    conn.commit()
    print(f"Applied. Logged {n_changed} changes to batch {BATCH}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

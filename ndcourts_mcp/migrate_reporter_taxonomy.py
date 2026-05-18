"""One-off: migrate citations.reporter to the Contract-1 taxonomy (SCHEMA.md).

Reclassifies every citation row from its citation STRING via
ingest._classify_reporter (idempotent), so the rename ND->ND-neutral,
NDold->ND, the ~590 misfiled A.L.R./L.R.A. rows, and the 79 NULL rows are
all handled uniformly. Changelog-tracked under batch
'reporter-taxonomy-2026-05-17'. Dry-run by default.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from .db import DEFAULT_DB_PATH, get_connection
from .ingest import _classify_reporter, REPORTER_TAXONOMY

BATCH = "reporter-taxonomy-2026-05-17"


def run(db_path: Path, apply: bool) -> None:
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT id, opinion_id, citation, reporter FROM citations ORDER BY id"
    ).fetchall()

    old_dist: Counter = Counter()
    new_dist: Counter = Counter()
    changes: list[tuple[int, str | None, str | None, str]] = []
    unclassifiable: list[tuple[int, str]] = []

    for r in rows:
        old = r["reporter"]
        new = _classify_reporter(r["citation"])
        old_dist[old if old is not None else "<NULL>"] += 1
        new_dist[new if new is not None else "<NULL>"] += 1
        if new is None:
            unclassifiable.append((r["id"], r["citation"]))
        if new != old:
            changes.append((r["id"], old, new, r["citation"]))

    print("=== reporter distribution ===")
    print(f"{'reporter':<12} {'before':>7} {'after':>7}")
    for key in sorted(set(old_dist) | set(new_dist)):
        print(f"{key:<12} {old_dist.get(key, 0):>7} {new_dist.get(key, 0):>7}")
    print(f"\nrows changing: {len(changes)}")
    print(f"unclassifiable (stay NULL): {len(unclassifiable)}")
    bad = new_dist.get("<NULL>", 0) + sum(
        v for k, v in new_dist.items()
        if k != "<NULL>" and k not in REPORTER_TAXONOMY
    )
    print(f"post-migration out-of-taxonomy (incl NULL): {bad}")

    # Transition matrix old->new for the changed rows
    trans: Counter = Counter()
    for _id, old, new, _c in changes:
        trans[(old if old else "<NULL>", new if new else "<NULL>")] += 1
    print("\n=== transitions (old -> new : count) ===")
    for (o, n), cnt in sorted(trans.items(), key=lambda x: -x[1]):
        print(f"  {o:>10} -> {n:<10} {cnt}")

    if unclassifiable[:15]:
        print("\n=== sample unclassifiable citations ===")
        for _id, c in unclassifiable[:15]:
            print(f"  id={_id}  {c!r}")

    # Guard: deleting a sole-citation row would orphan an opinion.
    unc_ids = {i for i, _c in unclassifiable}
    from collections import Counter as _C
    tot = _C(r["opinion_id"] for r in rows)
    by_op = _C(
        r["opinion_id"] for r in rows
        if _classify_reporter(r["citation"]) is None
    )
    orphaning = [o for o in by_op if by_op[o] == tot[o]]
    if orphaning:
        print(f"\nABORT: {len(orphaning)} opinions would lose all citations; "
              "not safe to delete. No changes written.")
        conn.close()
        return

    if not apply:
        print("\nDRY RUN — no changes written. Re-run with --apply.")
        conn.close()
        return

    # 1. Delete the unclassifiable foreign/specialty cross-ref rows
    #    (mis-scraped into citations; belong in text_citations). Snapshot is
    #    the real revert; changelog row is for the audit trail.
    for cid, cite in unclassifiable:
        conn.execute(
            "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) "
            "SELECT ?, opinion_id, 'citations.delete', ?, NULL FROM citations WHERE id = ?",
            (BATCH, cite, cid),
        )
        conn.execute("DELETE FROM citations WHERE id = ?", (cid,))

    # 2. Reclassify the remaining rows to the Contract-1 taxonomy
    for cid, old, new, _c in changes:
        if cid in unc_ids:
            continue  # already deleted
        conn.execute(
            "UPDATE citations SET reporter = ? WHERE id = ?", (new, cid)
        )
        conn.execute(
            "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) "
            "SELECT ?, opinion_id, 'citations.reporter', ?, ? FROM citations WHERE id = ?",
            (BATCH, old, new, cid),
        )
    conn.commit()
    deleted = len(unclassifiable)
    updated = len(changes) - deleted
    print(f"\nAPPLIED: deleted {deleted} foreign cross-ref rows, "
          f"reclassified {updated} rows under batch {BATCH}.")
    conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    run(args.db, args.apply)


if __name__ == "__main__":
    main()

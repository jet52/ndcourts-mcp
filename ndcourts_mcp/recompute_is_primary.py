"""One-off: recompute citations.is_primary for every opinion (Contract 2).

Applies the SCHEMA.md ladder (ND-neutral > ND > NW3d > NW2d > NW; secondary
never primary; exactly one per opinion) via ingest.recompute_primary. Every
flip is changelog-logged under batch 'is-primary-recompute-2026-05-17'.
Dry-run by default.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .db import DEFAULT_DB_PATH, get_connection
from .ingest import recompute_primary

BATCH = "is-primary-recompute-2026-05-17"


def run(db_path: Path, apply: bool) -> None:
    conn = get_connection(db_path)
    oids = [r["id"] for r in conn.execute("SELECT id FROM opinions").fetchall()]

    total_flips = 0
    opinions_touched = 0
    # All recomputes run in one transaction so the verification queries below
    # see the true projected post-state even in dry-run; commit/rollback once.
    for oid in oids:
        changed = recompute_primary(conn, oid)
        if not changed:
            continue
        opinions_touched += 1
        total_flips += len(changed)
        for _cid, old, new in changed:
            conn.execute(
                "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) "
                "VALUES (?, ?, 'citations.is_primary', ?, ?)",
                (BATCH, oid, str(old), str(new)),
            )

    # Verify single-primary invariant against the in-transaction post-state
    multi = conn.execute(
        "SELECT COUNT(*) FROM (SELECT opinion_id FROM citations "
        "WHERE is_primary=1 GROUP BY opinion_id HAVING COUNT(*)>1)"
    ).fetchone()[0]
    zero = conn.execute(
        "SELECT COUNT(*) FROM opinions o WHERE NOT EXISTS "
        "(SELECT 1 FROM citations c WHERE c.opinion_id=o.id AND c.is_primary=1)"
    ).fetchone()[0]
    sec = conn.execute(
        "SELECT COUNT(*) FROM citations WHERE is_primary=1 "
        "AND reporter IN ('ALR','LRA','US','SCT','LED')"
    ).fetchone()[0]

    mode = "APPLIED" if apply else "DRY RUN"
    print(f"=== is_primary recompute: {mode} ===")
    print(f"opinions:                {len(oids)}")
    print(f"opinions with flips:     {opinions_touched}")
    print(f"total is_primary flips:  {total_flips}")
    print(f"post multi-primary:      {multi}")
    print(f"post zero-primary:       {zero}")
    print(f"post secondary-primary:  {sec}")
    if apply:
        conn.commit()
        print("\nCOMMITTED.")
    else:
        conn.rollback()
        print("\nDRY RUN — rolled back, no changes written. Re-run with --apply.")
    conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    run(args.db, args.apply)


if __name__ == "__main__":
    main()

"""One-shot migration: make the EXISTING opinions.db changelog CL-diff-ready.

Fresh DBs get this from db.create_schema. This migrates a live DB:
  1. ADD COLUMN cl_cluster_id, authority to changelog (if absent).
  2. CREATE the changelog_stamp_cluster trigger (auto-stamp future rows).
  3. Backfill cl_cluster_id for existing rows from the CURRENT
     opinions.cluster_id. This is BEST-EFFORT HISTORICAL: for rows whose
     opinion was later re-clustered or dedup-merged, the captured id is
     today's, not the value at correction time. That limitation is
     recorded in provenance. Going forward the trigger captures the
     correct at-insert value, so only the pre-migration backlog is
     approximate.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .db import DEFAULT_DB_PATH, get_connection, log_provenance


def _columns(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def migrate(conn) -> dict:
    cols = _columns(conn, "changelog")
    added = []
    if "cl_cluster_id" not in cols:
        conn.execute("ALTER TABLE changelog ADD COLUMN cl_cluster_id INTEGER")
        added.append("cl_cluster_id")
    if "authority" not in cols:
        conn.execute("ALTER TABLE changelog ADD COLUMN authority TEXT")
        added.append("authority")

    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS changelog_stamp_cluster
        AFTER INSERT ON changelog
        WHEN NEW.cl_cluster_id IS NULL
        BEGIN
            UPDATE changelog
            SET cl_cluster_id = (
                SELECT cluster_id FROM opinions WHERE id = NEW.opinion_id
            )
            WHERE id = NEW.id;
        END;
    """)

    cur = conn.execute("""
        UPDATE changelog
        SET cl_cluster_id = (
            SELECT cluster_id FROM opinions WHERE opinions.id = changelog.opinion_id
        )
        WHERE cl_cluster_id IS NULL
    """)
    backfilled = cur.rowcount

    still_null = conn.execute(
        "SELECT COUNT(*) FROM changelog WHERE cl_cluster_id IS NULL"
    ).fetchone()[0]
    return {
        "columns_added": added,
        "rows_backfilled": backfilled,
        "rows_still_null": still_null,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = ap.parse_args()

    conn = get_connection(args.db)
    try:
        stats = migrate(conn)
        log_provenance(
            conn,
            operation="migrate-changelog-cl-diff-ready",
            command="python -m ndcourts_mcp.migrate_changelog_cl",
            rows_affected=stats["rows_backfilled"],
            notes=(
                f"added cols {stats['columns_added']}; trigger "
                f"changelog_stamp_cluster created; backfilled "
                f"{stats['rows_backfilled']} rows' cl_cluster_id "
                f"(BEST-EFFORT HISTORICAL — current cluster_id, may differ "
                f"from at-correction value for re-clustered rows); "
                f"{stats['rows_still_null']} rows still NULL (opinion has "
                f"no cluster_id, e.g. Westlaw-only bound opinions)"
            ),
        )
        conn.commit()
        print(f"columns added:    {stats['columns_added']}")
        print(f"rows backfilled:  {stats['rows_backfilled']}")
        print(f"rows still NULL:  {stats['rows_still_null']} "
              f"(no cluster_id on the opinion — expected for Westlaw-only)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

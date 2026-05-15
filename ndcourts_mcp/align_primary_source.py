"""Align opinions.source_path and opinion_sources.is_primary with opinions.source_reporter.

Past ingests and batch operations (backfill promote, merge_westlaw_text) updated
opinions.source_reporter to reflect a new authoritative source, but left
opinions.source_path pointing at the old source file and left opinion_sources
with is_primary set on the wrong row. This script walks every opinion, treats
opinions.source_reporter as ground truth, and:

  1. Sets is_primary = 1 on the opinion_sources row whose source_reporter
     matches, and is_primary = 0 on every other row for that opinion.
  2. Updates opinions.source_path to match that row's source_path.

text_content is not touched — separate concern. Logged to changelog under
batch 'align-primary-source' for revertibility.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from .db import DEFAULT_DB_PATH, get_connection

DEFAULT_BATCH = "align-primary-source"


def align(conn: sqlite3.Connection, batch: str, apply: bool) -> dict:
    cur = conn.cursor()
    # LEFT JOIN (not INNER): an opinion whose opinion_sources rows are ALL
    # is_primary=0 (e.g. after a delete-then-insert swap) has no primary row
    # at all. An inner join silently drops exactly those rows — the ones that
    # most need realigning. s.id IS NULL flags them so the loop can promote a
    # primary by source_reporter.
    cur.execute("""
        SELECT o.id, o.source_reporter, o.source_path,
               s.id AS primary_sid, s.source_path AS primary_path
        FROM opinions o
        LEFT JOIN opinion_sources s ON s.opinion_id = o.id AND s.is_primary = 1
        WHERE s.id IS NULL
           OR o.source_path != s.source_path
           OR o.source_reporter != s.source_reporter
    """)
    mismatches = cur.fetchall()

    stats = {
        "scanned": 0,
        "source_path_updated": 0,
        "primary_flag_flipped": 0,
        "no_primary_resolved": 0,
        "no_primary_unresolved": 0,
    }

    cur.execute("SELECT COUNT(*) FROM opinions")
    stats["scanned"] = cur.fetchone()[0]

    for row in mismatches:
        oid = row["id"]
        target_reporter = row["source_reporter"]
        current_path = row["source_path"]
        had_no_primary = row["primary_sid"] is None

        # Find the opinion_sources row matching the authoritative source_reporter
        target_row = conn.execute(
            "SELECT id, source_path, is_primary FROM opinion_sources "
            "WHERE opinion_id = ? AND source_reporter = ?",
            (oid, target_reporter),
        ).fetchone()
        if not target_row:
            if had_no_primary:
                stats["no_primary_unresolved"] += 1
                print(
                    f"  [no-primary, UNRESOLVED] opinion {oid}: no primary row "
                    f"and no opinion_sources row matches source_reporter "
                    f"'{target_reporter}' — needs manual attention"
                )
            continue

        if had_no_primary:
            stats["no_primary_resolved"] += 1

        new_path = target_row["source_path"]

        # Flip primary flags if needed
        if not target_row["is_primary"]:
            stats["primary_flag_flipped"] += 1
            if apply:
                conn.execute(
                    "UPDATE opinion_sources SET is_primary = 0 WHERE opinion_id = ?",
                    (oid,),
                )
                conn.execute(
                    "UPDATE opinion_sources SET is_primary = 1 WHERE id = ?",
                    (target_row["id"],),
                )

        # Update opinions.source_path if needed
        if current_path != new_path:
            stats["source_path_updated"] += 1
            if apply:
                conn.execute(
                    "UPDATE opinions SET source_path = ? WHERE id = ?",
                    (new_path, oid),
                )
                conn.execute(
                    "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) "
                    "VALUES (?, ?, 'source_path', ?, ?)",
                    (batch, oid, current_path, new_path),
                )

    if apply:
        conn.commit()
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    ap.add_argument("--apply", action="store_true",
                    help="Write changes to the DB (default is dry-run)")
    ap.add_argument("--batch", default=DEFAULT_BATCH,
                    help=f"Changelog batch name (default: {DEFAULT_BATCH})")
    args = ap.parse_args()

    conn = get_connection(args.db)
    try:
        stats = align(conn, args.batch, apply=args.apply)
        mode = "APPLIED" if args.apply else "DRY RUN"
        print(f"=== Align primary source: {mode} ===")
        print(f"Opinions scanned:          {stats['scanned']}")
        print(f"source_path rewrites:      {stats['source_path_updated']}")
        print(f"primary-flag flips:        {stats['primary_flag_flipped']}")
        print(f"no-primary resolved:       {stats['no_primary_resolved']}")
        print(f"no-primary UNRESOLVED:     {stats['no_primary_unresolved']}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

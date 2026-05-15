"""Per-opinion validation ledger — the backbone for measurable, auditable
"is this corpus validated yet?" state.

The corpus already logs *corrections* (changelog), *operations* (provenance),
and *per-volume Westlaw progress* (westlaw_progress). What was missing is a
per-opinion answer to: has THIS opinion been cross-checked, against what
authority, when, with what outcome? This table provides it, which turns
"fully validated" into a COUNT query and lets validate.py emit a
deterministic completion gate the /goal evaluator can read.

Design contract (deliberate, flagged for review):

  * Only FACTUAL, derivable columns are backfilled here: era_tier,
    sources_seen, cl_cluster_id. These are observations, not judgments.
  * crosscheck_state starts 'unvalidated' for EVERY opinion. Prior
    validation work (Westlaw Quick Check, multi-source diff audit) is
    real, but promoting a row to 'cross_checked' is a judgment that must
    be EARNED by an explicit, logged validate.py step citing its
    authority — never a silent backfill. Backfilling unearned "validated"
    claims would directly undercut the authoritative-text bar.

era_tier (derived from date_filed; boundaries are refinable and documented):
  pre1953_westlaw    < 1953-01-01  — bound N.D. Reports vols 1-79 exist;
                                      Westlaw bound cross-check applicable.
  gap_1953_1996      1953..1996    — N.D. Reports series ended at vol 79.
                                      Completion = court NW-cite archive
                                      scrape (vols 139+, ~1966+) PLUS
                                      manual Westlaw acquisition of the
                                      remainder, error-indicator first.
  modern_1997_2019   1997..2019    — ndcourts.gov + archive.ndcourts.gov
                                      + CL NW2d multi-source.
  modern_2020_plus   >= 2020       — ndcourts.gov primary, NW2d secondary.

crosscheck_state lifecycle:
  unvalidated             — not yet examined by a validation pass.
  single_source_accepted  — only one source exists and no higher authority
                            is obtainable; accepted with that limitation
                            recorded (e.g. pre-court-archive gap years).
  cross_checked           — compared against a named authority_source and
                            found consistent.
  corrected               — a discrepancy was found and fixed (see
                            changelog batch); now consistent.
  flagged                 — a discrepancy was found that needs human
                            adjudication; NOT yet resolved.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from .db import DEFAULT_DB_PATH, get_connection, log_provenance

VALID_STATES = (
    "unvalidated",
    "single_source_accepted",
    "cross_checked",
    "corrected",
    "flagged",
)

ERA_TIERS = (
    "pre1953_westlaw",
    "gap_1953_1996",
    "modern_1997_2019",
    "modern_2020_plus",
)


def _era_tier(date_filed: str) -> str:
    """Bucket by filing date. Boundaries documented in the module docstring;
    refinable without data loss since this column is purely derived."""
    if date_filed < "1953-01-01":
        return "pre1953_westlaw"
    if date_filed < "1997-01-01":
        return "gap_1953_1996"
    if date_filed < "2020-01-01":
        return "modern_1997_2019"
    return "modern_2020_plus"


def create_table(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS validation_status (
            opinion_id       INTEGER PRIMARY KEY REFERENCES opinions(id),
            era_tier         TEXT NOT NULL,
            crosscheck_state TEXT NOT NULL DEFAULT 'unvalidated',
            authority_source TEXT,
            sources_seen     TEXT,
            cl_cluster_id    INTEGER,
            batch            TEXT,
            validated_at     TEXT,
            note             TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_valstatus_tier
            ON validation_status(era_tier);
        CREATE INDEX IF NOT EXISTS idx_valstatus_state
            ON validation_status(crosscheck_state);
    """)


def backfill(conn: sqlite3.Connection) -> dict:
    """Insert a row for every opinion that lacks one, populating only the
    factual/derived columns. Existing rows' crosscheck_state is never
    touched here — state transitions are validate.py's job."""
    sources: dict[int, set[str]] = {}
    for oid, rep in conn.execute(
        "SELECT opinion_id, source_reporter FROM opinion_sources"
    ):
        sources.setdefault(oid, set()).add(rep)

    inserted = 0
    refreshed = 0
    existing = {
        r[0] for r in conn.execute("SELECT opinion_id FROM validation_status")
    }
    for oid, date_filed, cluster_id in conn.execute(
        "SELECT id, date_filed, cluster_id FROM opinions"
    ):
        tier = _era_tier(date_filed)
        seen = json.dumps(sorted(sources.get(oid, [])))
        if oid in existing:
            # Keep crosscheck_state/authority/batch; refresh derived facts
            # only (sources or cluster_id may have changed since last run).
            conn.execute(
                "UPDATE validation_status "
                "SET era_tier=?, sources_seen=?, cl_cluster_id=? "
                "WHERE opinion_id=?",
                (tier, seen, cluster_id, oid),
            )
            refreshed += 1
        else:
            conn.execute(
                "INSERT INTO validation_status "
                "(opinion_id, era_tier, crosscheck_state, sources_seen, cl_cluster_id) "
                "VALUES (?, ?, 'unvalidated', ?, ?)",
                (oid, tier, seen, cluster_id),
            )
            inserted += 1
    return {"inserted": inserted, "refreshed": refreshed}


def coverage(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """(era_tier, crosscheck_state) → count. The orchestrator's gate input."""
    return conn.execute("""
        SELECT era_tier, crosscheck_state, COUNT(*) AS n
        FROM validation_status
        GROUP BY era_tier, crosscheck_state
        ORDER BY era_tier, crosscheck_state
    """).fetchall()


def print_coverage(conn: sqlite3.Connection) -> None:
    rows = coverage(conn)
    by_tier: dict[str, dict[str, int]] = {}
    for r in rows:
        by_tier.setdefault(r["era_tier"], {})[r["crosscheck_state"]] = r["n"]
    print(f"{'era_tier':<20} " + " ".join(f"{s[:11]:>11}" for s in VALID_STATES) + "      total")
    for tier in ERA_TIERS:
        states = by_tier.get(tier, {})
        cells = " ".join(f"{states.get(s, 0):>11}" for s in VALID_STATES)
        print(f"{tier:<20} {cells} {sum(states.values()):>10}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    ap.add_argument("--report-only", action="store_true",
                    help="Print coverage without creating/backfilling")
    args = ap.parse_args()

    conn = get_connection(args.db)
    try:
        if not args.report_only:
            create_table(conn)
            stats = backfill(conn)
            log_provenance(
                conn,
                operation="validation_status-backfill",
                command="python -m ndcourts_mcp.validation_status",
                rows_affected=stats["inserted"] + stats["refreshed"],
                notes=(
                    f"inserted={stats['inserted']} refreshed={stats['refreshed']}; "
                    "factual columns only, crosscheck_state left 'unvalidated' "
                    "(state transitions are validate.py's job)"
                ),
            )
            conn.commit()
            print(f"backfill: inserted={stats['inserted']} "
                  f"refreshed={stats['refreshed']}")
        print()
        print_coverage(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

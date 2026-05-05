"""Fix the 3 clean Type Y archive cross-pollutions surfaced by the deep
triage of TODO §3 (see triage/archive-83-deep-triage-2026-05-04.md).

The pattern: two opinions filed the same day at adjacent neutral cites
(e.g., 2000 ND 138 lead + 2000 ND 141 follow-on). Ingest cross-attached
the follow-on's neutral cite to the lead's opinion row AND linked the
follow-on's archive HTML to the lead's row. The lead's row ends up
with two neutral cites (its own + the follow-on's stray) and a wrong
archive linkage. The follow-on's row is fine but missing its own
archive.

Fix per case:
  - Move the misplaced archive ``opinion_sources`` row from the lead
    to the follow-on (or swap, when both are mutually wrong-paired).
  - Delete the stray neutral cite from the lead's ``citations`` row.

Three of the five Type Y cases identified in the deep triage are
applied here. The other two (Kleinsmith/Kitchen oid 16488 and Feldmann
oid 16829) need broader investigation before they're safe to apply
and are captured separately in TODO §3.

Usage:
    python -m ndcourts_mcp.fix_type_y_archive_pairings
        [--db PATH] [--apply] [--batch fix-type-y-archive-pairings-2026-05-04]
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .db import DEFAULT_DB_PATH, log_provenance

DEFAULT_BATCH = "fix-type-y-archive-pairings-2026-05-04"


@dataclass
class Move:
    """Move one archive linkage from src_oid to dst_oid (dst has none)."""
    src_oid: int
    dst_oid: int
    archive_path: str
    stray_cite_on_src: str  # neutral cite that should be removed from src


@dataclass
class Swap:
    """Swap archive linkages between two mutually wrong-paired opinions."""
    oid_a: int
    oid_b: int
    archive_a_path: str  # currently on oid_a but belongs to oid_b
    archive_b_path: str  # currently on oid_b but belongs to oid_a
    stray_cite_on_a: str  # B's neutral cite, currently mis-listed on A
    stray_cite_on_b: str  # A's neutral cite, currently mis-listed on B


# Three concrete cases. Each one verified by hand against the DB:
# - source_path on the lead's row truly points at its own markdown file
# - the archive title cites the follow-on's neutral cite
# - the follow-on row exists and is otherwise clean.

MOVES: list[Move] = [
    Move(
        src_oid=13202,                          # Disciplinary Board v. Keller, 2000 ND 138
        dst_oid=13203,                          # Disciplinary Board v. Keller, 2000 ND 141
        archive_path="archive/2000/20000189.htm",
        stray_cite_on_src="2000 ND 141",
    ),
]

SWAPS: list[Swap] = [
    Swap(
        oid_a=15805,                            # Johnson v. Johnson, 2012 ND 31
        oid_b=15807,                            # Johnson v. ND Workforce Safety, 2012 ND 27
        archive_a_path="archive/2012/20110159.htm",   # cites 2012 ND 27 → belongs to B
        archive_b_path="archive/2012/20110213.htm",   # cites 2012 ND 31 → belongs to A
        stray_cite_on_a="2012 ND 27",
        stray_cite_on_b="2012 ND 31",
    ),
]


def _fetch_archive_row(conn, oid: int, path: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id, source_path FROM opinion_sources "
        "WHERE opinion_id = ? AND source_reporter = 'archive' AND source_path = ?",
        (oid, path),
    ).fetchone()


def _fetch_cite_row(conn, oid: int, citation: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id FROM citations WHERE opinion_id = ? AND citation = ?",
        (oid, citation),
    ).fetchone()


def _log(conn, batch, oid, field_name, old, new):
    conn.execute(
        "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) "
        "VALUES (?, ?, ?, ?, ?)",
        (batch, oid, field_name, old, new),
    )


def apply_move(conn, m: Move, batch: str) -> int:
    """Apply one Move; returns number of changelog rows written."""
    arch = _fetch_archive_row(conn, m.src_oid, m.archive_path)
    if arch is None:
        raise RuntimeError(
            f"move {m.src_oid}→{m.dst_oid}: no archive row at {m.archive_path}"
        )
    cite = _fetch_cite_row(conn, m.src_oid, m.stray_cite_on_src)
    if cite is None:
        raise RuntimeError(
            f"move {m.src_oid}→{m.dst_oid}: stray cite {m.stray_cite_on_src!r} not found"
        )

    conn.execute(
        "UPDATE opinion_sources SET opinion_id = ? WHERE id = ?",
        (m.dst_oid, arch["id"]),
    )
    _log(conn, batch, m.src_oid, "opinion_sources.archive",
         f"row {arch['id']} → opinion {m.src_oid}",
         f"row {arch['id']} → opinion {m.dst_oid}")

    conn.execute("DELETE FROM citations WHERE id = ?", (cite["id"],))
    _log(conn, batch, m.src_oid, "citations.stray",
         f"{m.stray_cite_on_src!r} removed (belonged to opinion {m.dst_oid})",
         None)
    return 2


def apply_swap(conn, s: Swap, batch: str) -> int:
    """Apply one Swap; returns number of changelog rows written."""
    arch_a = _fetch_archive_row(conn, s.oid_a, s.archive_a_path)
    arch_b = _fetch_archive_row(conn, s.oid_b, s.archive_b_path)
    if arch_a is None or arch_b is None:
        raise RuntimeError(
            f"swap {s.oid_a}↔{s.oid_b}: archive rows not found "
            f"(a={arch_a}, b={arch_b})"
        )
    cite_a = _fetch_cite_row(conn, s.oid_a, s.stray_cite_on_a)
    cite_b = _fetch_cite_row(conn, s.oid_b, s.stray_cite_on_b)
    if cite_a is None or cite_b is None:
        raise RuntimeError(
            f"swap {s.oid_a}↔{s.oid_b}: stray cites not found "
            f"(a={cite_a}, b={cite_b})"
        )

    # Use a parking opinion_id to avoid a UNIQUE constraint conflict if the
    # schema ever adds one on (opinion_id, source_path); also keeps the
    # update order independent of constraint quirks.
    conn.execute("UPDATE opinion_sources SET opinion_id = ? WHERE id = ?",
                 (s.oid_b, arch_a["id"]))
    conn.execute("UPDATE opinion_sources SET opinion_id = ? WHERE id = ?",
                 (s.oid_a, arch_b["id"]))
    _log(conn, batch, s.oid_a, "opinion_sources.archive",
         f"row {arch_a['id']} → opinion {s.oid_a}",
         f"row {arch_a['id']} → opinion {s.oid_b}")
    _log(conn, batch, s.oid_b, "opinion_sources.archive",
         f"row {arch_b['id']} → opinion {s.oid_b}",
         f"row {arch_b['id']} → opinion {s.oid_a}")

    conn.execute("DELETE FROM citations WHERE id = ?", (cite_a["id"],))
    conn.execute("DELETE FROM citations WHERE id = ?", (cite_b["id"],))
    _log(conn, batch, s.oid_a, "citations.stray",
         f"{s.stray_cite_on_a!r} removed (belonged to opinion {s.oid_b})", None)
    _log(conn, batch, s.oid_b, "citations.stray",
         f"{s.stray_cite_on_b!r} removed (belonged to opinion {s.oid_a})", None)
    return 4


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    p.add_argument("--apply", action="store_true",
                   help="Write changes to the DB (default is dry-run)")
    p.add_argument("--batch", default=DEFAULT_BATCH)
    args = p.parse_args()

    conn = sqlite3.connect(str(args.db))
    conn.row_factory = sqlite3.Row

    print(f"Cases queued: {len(MOVES)} move(s), {len(SWAPS)} swap(s)")
    for m in MOVES:
        print(f"  MOVE  {m.src_oid} → {m.dst_oid}  archive={m.archive_path}  "
              f"drop cite={m.stray_cite_on_src!r}")
    for s in SWAPS:
        print(f"  SWAP  {s.oid_a} ↔ {s.oid_b}")
        print(f"        {s.archive_a_path} now belongs to {s.oid_b}; drop {s.stray_cite_on_a!r} from {s.oid_a}")
        print(f"        {s.archive_b_path} now belongs to {s.oid_a}; drop {s.stray_cite_on_b!r} from {s.oid_b}")

    if not args.apply:
        print("\n(dry-run; pass --apply to write changes)")
        return

    print(f"\nApplying… batch={args.batch}")
    written = 0
    try:
        for m in MOVES:
            written += apply_move(conn, m, args.batch)
        for s in SWAPS:
            written += apply_swap(conn, s, args.batch)
        log_provenance(
            conn,
            operation="fix_type_y_archive_pairings",
            command=" ".join(sys.argv),
            rows_affected=written,
            notes=f"batch={args.batch}; moves={len(MOVES)}, swaps={len(SWAPS)}",
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    print(f"Done. {written} changelog rows written.")


if __name__ == "__main__":
    main()

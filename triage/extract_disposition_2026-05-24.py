"""Populate opinions.disposition (§12 faceted-search facet + later
detect_overruled reuse).

Derives a disposition string from each opinion's text via the modern
all-caps disposition line (e.g. "REVERSED AND REMANDED.") that ND opinions
print between the "Appeal from..." line and the authoring byline. Pre-modern
opinions that lack that convention stay NULL — honest: this is a derived,
best-effort metadata field, NOT authoritative text.

Adds the column if absent, then sets it where the extractor finds a line.
Idempotent (only writes where the value changes). Modes: --apply (default
--dry-run); --revert sets every disposition back to NULL. Logged to provenance
(operation=disposition-extract-2026-05-24).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from ndcourts_mcp.db import DEFAULT_DB_PATH, get_connection, log_provenance  # noqa: E402
from ndcourts_mcp.memo import extract_disposition  # noqa: E402

BATCH = "disposition-extract-2026-05-24"


def _ensure_column(conn) -> None:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(opinions)")]
    if "disposition" not in cols:
        conn.execute("ALTER TABLE opinions ADD COLUMN disposition TEXT")
        conn.commit()
        print("added column opinions.disposition")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()

    conn = get_connection(DEFAULT_DB_PATH)
    _ensure_column(conn)

    if args.revert:
        if not args.apply:
            n = conn.execute(
                "SELECT COUNT(*) FROM opinions WHERE disposition IS NOT NULL"
            ).fetchone()[0]
            print(f"DRY-RUN revert: would NULL {n} dispositions. re-run with --apply.")
            return 0
        n = conn.execute(
            "UPDATE opinions SET disposition = NULL WHERE disposition IS NOT NULL"
        ).rowcount
        conn.commit()
        log_provenance(conn, BATCH, command="--revert", rows_affected=n,
                       notes="cleared all disposition values")
        print(f"reverted {n} dispositions to NULL.")
        return 0

    rows = conn.execute(
        "SELECT id, disposition, text_content FROM opinions"
    ).fetchall()
    changes: list[tuple[int, str | None, str | None]] = []
    for r in rows:
        new = extract_disposition(r["text_content"])
        if new != r["disposition"]:
            changes.append((r["id"], r["disposition"], new))

    set_count = sum(1 for _, _, new in changes if new is not None)
    print(f"opinions scanned: {len(rows)}")
    print(f"rows changing:    {len(changes)} ({set_count} get a disposition)")
    if changes[:8]:
        print("sample:")
        for oid, old, new in changes[:8]:
            print(f"  oid {oid}: {old!r} -> {new!r}")

    if not args.apply:
        print("\nDRY-RUN. re-run with --apply.")
        return 0

    applied = 0
    for oid, _old, new in changes:
        conn.execute("UPDATE opinions SET disposition = ? WHERE id = ?", (new, oid))
        applied += 1
        if applied % 1000 == 0:
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.commit()
    log_provenance(
        conn, BATCH, command="extract_disposition over opinions.text_content",
        rows_affected=applied,
        notes=f"{set_count} opinions assigned a derived disposition "
              "(modern all-caps line); rest NULL",
    )
    print(f"\napplied {applied} updates; batch {BATCH}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

r"""Validation orchestrator + the /goal completion gate.

`/goal`'s evaluator is a small fast model that reads ONLY the transcript —
it cannot run tools or read files. So a usable goal condition needs a
single command whose printed output deterministically demonstrates
"this batch is done". That command is `validate.py --gate --batch X`,
which ends with a literal `BATCH STATUS: COMPLETE` / `INCOMPLETE` line
plus the four sub-check results, so the evaluator can decide by reading.

This module is the GATE, not the grind. It does not mutate the DB. Each
batch's detection/correction runner is plugged into the registry during
the grind phase; the gate reads live state (validation_status,
invariants, changelog, CHANGELOG-data.md) and reports whether the batch's
completion predicate holds.

A batch is COMPLETE when all four hold:
  1. scope drained   — every opinion in the batch's scope has reached a
                        terminal crosscheck_state (cross_checked /
                        corrected / single_source_accepted); none left
                        'unvalidated' or 'flagged'.
  2. corrections logged — if the batch made corrections they are in the
                        changelog under the batch name (informational:
                        zero corrections is valid when nothing needed
                        fixing).
  3. invariants clean — invariants.py reports 0 regressed.
  4. changelog/doc parity — if the batch has changelog rows, CHANGELOG-
                        data.md has a `## Batch \`name\`` section whose
                        stated row count matches the changelog count.

Usage:
  python -m ndcourts_mcp.validate --status            # corpus dashboard
  python -m ndcourts_mcp.validate --gate --batch NAME  # the /goal gate
  python -m ndcourts_mcp.validate --list-batches
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .db import DEFAULT_DB_PATH, get_connection
from .validation_status import print_coverage

CHANGELOG_DOC = Path(__file__).parent.parent / "CHANGELOG-data.md"

TERMINAL_STATES = ("cross_checked", "corrected", "single_source_accepted")


@dataclass
class Batch:
    name: str
    description: str
    # SQL boolean over `validation_status v` (optionally joined to
    # `opinions o`) selecting the opinions this batch is responsible for.
    scope_sql: str
    # Changelog/CHANGELOG-data.md batch labels are dated and may recur
    # (re-runs), e.g. `court-archive-promote-2026-05-15`. This is the
    # label PREFIX the logical batch's corrections carry, so the
    # corrections-logged and doc-parity checks read the right rows
    # instead of the (un-dated) registry key.
    changelog_prefix: str


# Registry of the near-term grind batches. scope_sql defines WHICH opinions
# each batch must drive to a terminal state. Correction runners are added
# during the grind; the gate already works against live state.
BATCHES: dict[str, Batch] = {
    "type-y-sweep": Batch(
        name="type-y-sweep",
        description="Corpus-wide Type Y supplemental-publications sweep "
                    "(westlaw-paired .docs whose All-Citations N.W. cite "
                    "differs from the DB primary).",
        scope_sql="""
            v.opinion_id IN (
                SELECT opinion_id FROM opinion_sources
                WHERE source_reporter = 'westlaw'
            )
        """,
        changelog_prefix="type-y-sweep",
    ),
    "court-archive-1966-1996": Batch(
        name="court-archive-1966-1996",
        description="Cross-check the 1953-1996 gap era against the "
                    "court-sourced archive.ndcourts.gov NW-cite index "
                    "(N.W.2d vols 139+).",
        scope_sql="v.era_tier = 'gap_1953_1996'",
        changelog_prefix="court-archive-promote-",
    ),
    "pre1953-westlaw-quickcheck": Batch(
        name="pre1953-westlaw-quickcheck",
        description="Pre-1953 opinions with a Westlaw bound source — "
                    "promote to cross_checked citing westlaw_progress.",
        scope_sql="""
            v.era_tier = 'pre1953_westlaw'
            AND v.opinion_id IN (
                SELECT opinion_id FROM opinion_sources
                WHERE source_reporter = 'westlaw'
            )
        """,
        changelog_prefix="pre1953-westlaw-quickcheck",
    ),
}


def _invariants_status() -> tuple[bool, str]:
    """Run invariants.py; return (clean, summary_line). clean == 0 regressed."""
    proc = subprocess.run(
        [sys.executable, "-m", "ndcourts_mcp.invariants"],
        capture_output=True, text=True,
    )
    out = proc.stdout + proc.stderr
    m = re.search(r"Invariants:.*regressed", out)
    summary = m.group(0) if m else "Invariants: (summary line not found)"
    regressed = re.search(r"(\d+)\s+regressed", summary)
    clean = bool(regressed) and int(regressed.group(1)) == 0
    return clean, summary


def _doc_batch_count(prefix: str) -> int | None:
    r"""Summed row count across every `## Batch \`<prefix>...\` (N rows)`
    header in CHANGELOG-data.md, or None if no section matches the
    prefix. Summed because a logical batch's label is dated and may
    recur across re-runs."""
    if not CHANGELOG_DOC.exists():
        return None
    text = CHANGELOG_DOC.read_text(encoding="utf-8")
    matches = re.findall(
        rf"^##\s+Batch\s+`{re.escape(prefix)}[^`]*`\s*\((\d[\d,]*)\s+rows?\)",
        text, re.MULTILINE,
    )
    if not matches:
        return None
    return sum(int(m.replace(",", "")) for m in matches)


def gate(conn, batch_name: str) -> bool:
    batch = BATCHES.get(batch_name)
    print(f"BATCH: {batch_name}")
    if batch is None:
        print(f"  [ ] unknown batch — not in registry "
              f"({', '.join(sorted(BATCHES))})")
        print("BATCH STATUS: INCOMPLETE")
        return False
    print(f"  scope: {batch.description}")

    checks: list[tuple[bool, str]] = []

    # 1. scope drained
    total = conn.execute(
        f"SELECT COUNT(*) FROM validation_status v WHERE {batch.scope_sql}"
    ).fetchone()[0]
    placeholders = ",".join("?" * len(TERMINAL_STATES))
    pending = conn.execute(
        f"SELECT COUNT(*) FROM validation_status v "
        f"WHERE {batch.scope_sql} "
        f"AND v.crosscheck_state NOT IN ({placeholders})",
        TERMINAL_STATES,
    ).fetchone()[0]
    drained = pending == 0 and total > 0
    checks.append((
        drained,
        f"scope drained: {total - pending}/{total} in-scope opinions "
        f"terminal, {pending} still unvalidated/flagged",
    ))

    # 2. corrections logged (informational — zero is valid)
    cl_rows = conn.execute(
        "SELECT COUNT(*) FROM changelog WHERE batch LIKE ?",
        (batch.changelog_prefix + "%",),
    ).fetchone()[0]
    checks.append((True, f"corrections logged: {cl_rows} changelog rows "
                          f"under '{batch.changelog_prefix}*' (0 is valid "
                          f"if nothing needed fixing)"))

    # 3. invariants clean
    inv_clean, inv_summary = _invariants_status()
    checks.append((inv_clean, inv_summary))

    # 4. changelog / CHANGELOG-data.md parity
    doc_count = _doc_batch_count(batch.changelog_prefix)
    if cl_rows == 0:
        parity_ok, parity_msg = True, "doc parity: n/a (no changelog rows)"
    elif doc_count is None:
        parity_ok, parity_msg = False, (
            f"doc parity: changelog has {cl_rows} rows but CHANGELOG-data.md "
            f"has no `## Batch \\`{batch.changelog_prefix}*\\`` section")
    else:
        parity_ok = doc_count == cl_rows
        parity_msg = (f"doc parity: CHANGELOG-data.md says {doc_count} rows, "
                      f"changelog has {cl_rows}"
                      f"{'' if parity_ok else ' — MISMATCH'}")
    checks.append((parity_ok, parity_msg))

    for ok, msg in checks:
        print(f"  [{'x' if ok else ' '}] {msg}")

    complete = all(ok for ok, _ in checks)
    print(f"BATCH STATUS: {'COMPLETE' if complete else 'INCOMPLETE'}")
    return complete


def status(conn) -> None:
    print("=== Validation coverage ===")
    print_coverage(conn)
    print()
    _, inv_summary = _invariants_status()
    print(inv_summary)
    print()
    print("=== Registered batches ===")
    for b in BATCHES.values():
        n = conn.execute(
            f"SELECT COUNT(*) FROM validation_status v WHERE {b.scope_sql}"
        ).fetchone()[0]
        term = conn.execute(
            f"SELECT COUNT(*) FROM validation_status v WHERE {b.scope_sql} "
            f"AND v.crosscheck_state IN "
            f"({','.join('?' * len(TERMINAL_STATES))})",
            TERMINAL_STATES,
        ).fetchone()[0]
        print(f"  {b.name:<28} {term}/{n} terminal")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    ap.add_argument("--status", action="store_true",
                    help="Print corpus validation dashboard (read-only)")
    ap.add_argument("--gate", action="store_true",
                    help="Print the /goal completion gate for --batch")
    ap.add_argument("--batch", help="Batch name for --gate")
    ap.add_argument("--list-batches", action="store_true")
    args = ap.parse_args()

    conn = get_connection(args.db)
    try:
        if args.list_batches:
            for b in BATCHES.values():
                print(f"{b.name}\n  {b.description}\n")
            return
        if args.gate:
            if not args.batch:
                ap.error("--gate requires --batch")
            ok = gate(conn, args.batch)
            sys.exit(0 if ok else 1)
        status(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

"""Fix the 9 Westlaw .doc pairings that were attached to the wrong opinion.

Each of the 9 vol/page locations in the bound N.D. Reports has two short
opinions (a lead opinion + a per curiam follow-on filed the same day) and
both share the same `<vol> N.D. <page>` cite. The volume-based ingest paired
one .doc with one opinion arbitrarily and orphaned the other. This rewires:

  pair: at vol/page, .doc-X belongs with opinion-B (matches NW cite),
                     .doc-Y belongs with opinion-A (matches NW cite).

  Current state: .doc-X is paired with opinion-A (wrong); .doc-Y is unpaired.

  Fix:
    1. Delete the .doc-X ↔ opinion-A row in opinion_sources.
    2. Insert .doc-X ↔ opinion-B.
    3. Insert .doc-Y ↔ opinion-A.

After this script runs, `merge_westlaw_text --apply` should pick up all 18
correctly-paired westlaw rows and merge their text.

Usage:
    python -m ndcourts_mcp.fix_westlaw_pairings [--apply]
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .db import DEFAULT_DB_PATH, get_connection, log_provenance


REFS_ROOT = Path("/Users/jerod/refs/nd/opin/N.D.")
BATCH = "westlaw-merge-residuals-2026-04-27-pairings"


@dataclass(frozen=True)
class Pair:
    vol: int
    page: int
    # The .doc currently paired with the wrong opinion (will be re-paired)
    wrong_paired_doc: str
    wrong_paired_opinion: int
    # The opinion that .doc actually belongs to
    correct_opinion: int
    # The other .doc at the same vol/page (currently unpaired) and its opinion
    orphan_doc: str
    orphan_opinion: int

    def wrong_paired_path(self) -> Path:
        return REFS_ROOT / str(self.vol) / self.wrong_paired_doc

    def orphan_path(self) -> Path:
        return REFS_ROOT / str(self.vol) / self.orphan_doc


PAIRS: list[Pair] = [
    Pair(
        vol=14, page=557,
        wrong_paired_doc="0557-Murphy-v-District-Court-of-Eighth-Judicial-Dist.doc",
        wrong_paired_opinion=146,   # State v. Poull (105 N.W. 717)
        correct_opinion=152,        # Murphy v. Dist. Ct. (105 N.W. 734)
        orphan_doc="0557-State-v-Poull.doc",
        orphan_opinion=146,
    ),
    Pair(
        vol=24, page=326,
        wrong_paired_doc="0326-Seckerson-v-Sinclair.doc",
        wrong_paired_opinion=1012,  # Burger v. Sinclair (140 N.W. 235)
        correct_opinion=1013,       # Seckerson v. Sinclair (140 N.W. 239)
        orphan_doc="0326-Burger-v-Sinclair.doc",
        orphan_opinion=1012,
    ),
    Pair(
        vol=17, page=266,
        wrong_paired_doc="0266-Skeffington-v-Prante.doc",
        wrong_paired_opinion=382,   # Ross v. Prante (115 N.W. 833)
        correct_opinion=383,        # Skeffington v. Prante (115 N.W. 834)
        orphan_doc="0266-Ross-v-Prante.doc",
        orphan_opinion=382,
    ),
    Pair(
        vol=17, page=393,
        wrong_paired_doc="0393-Erickson-v-Elliott.doc",
        wrong_paired_opinion=415,   # Soliah v. Cormack (117 N.W. 125)
        correct_opinion=422,        # Erickson v. Elliott (117 N.W. 363)
        orphan_doc="0393-Soliah-v-Cormack.doc",
        orphan_opinion=415,
    ),
    Pair(
        vol=16, page=106,
        wrong_paired_doc="0106-State-v-Davies.doc",
        wrong_paired_opinion=295,   # A. B. Farquhar Co. v. Higham (112 N.W. 557)
        correct_opinion=296,        # State ex rel. Harvey v. Davies (112 N.W. 60)
        orphan_doc="0106-AB-Farquhar-Co-v-Higham.doc",
        orphan_opinion=295,
    ),
    Pair(
        vol=51, page=13,
        wrong_paired_doc="0013-Klingenstein-v-National-Union-Fire-Ins-Co.doc",
        wrong_paired_opinion=2955,  # Hintz v. Jackson (198 N.W. 475)
        correct_opinion=2958,       # Klingenstein (198 N.W. 550)
        orphan_doc="0013-Hintz-v-Jackson.doc",
        orphan_opinion=2955,
    ),
    Pair(
        vol=48, page=577,
        wrong_paired_doc="0577-Hanson-v-Houska.doc",
        wrong_paired_opinion=2597,  # Johnson Const. Co. v. Hildreth (185 N.W. 811)
        correct_opinion=2606,       # Hanson v. Houska (186 N.W. 256)
        orphan_doc="0577-Johnson-Const-Co-v-Hildreth.doc",
        orphan_opinion=2597,
    ),
    Pair(
        vol=64, page=367,
        wrong_paired_doc="0367-Ott-v-Kelley.doc",
        wrong_paired_opinion=4482,  # Thorvaldson-Johnson Co. v. Cochran (252 N.W. 268)
        correct_opinion=4484,       # Ott v. Kelley (252 N.W. 271) — 4485 is a dup, deferred
        orphan_doc="0367-Thorvaldson-Johnson-Co-v-Cochran.doc",
        orphan_opinion=4482,
    ),
    Pair(
        vol=50, page=813,
        wrong_paired_doc="0813-Hassen-v-Salem.doc",
        wrong_paired_opinion=2935,  # Farmers State Bank v. Jeske (197 N.W. 854)
        correct_opinion=2946,       # Hassen v. Salem (198 N.W. 115); N.D. cite conflict noted in TODO
        orphan_doc="0813-Farmers'-State-Bank-of-Cathay-v-Jeske.doc",
        orphan_opinion=2935,
    ),
]


def _verify(conn) -> list[str]:
    """Pre-flight: confirm DB state matches expectations. Returns error list."""
    errors = []
    for p in PAIRS:
        wp = str(p.wrong_paired_path())
        op = str(p.orphan_path())

        if not p.wrong_paired_path().exists():
            errors.append(f"Missing file: {wp}")
        if not p.orphan_path().exists():
            errors.append(f"Missing file: {op}")

        wrong_row = conn.execute(
            "SELECT id, opinion_id FROM opinion_sources "
            "WHERE source_path = ? AND source_reporter = 'westlaw'",
            (wp,),
        ).fetchone()
        if wrong_row is None:
            errors.append(f"Expected wrong-paired row not found for {p.wrong_paired_doc}")
        elif wrong_row["opinion_id"] != p.wrong_paired_opinion:
            errors.append(
                f"Wrong-paired row points to opinion {wrong_row['opinion_id']}, "
                f"expected {p.wrong_paired_opinion} ({p.wrong_paired_doc})"
            )

        orphan_row = conn.execute(
            "SELECT id FROM opinion_sources "
            "WHERE source_path = ? AND source_reporter = 'westlaw'",
            (op,),
        ).fetchone()
        if orphan_row is not None:
            errors.append(
                f"Orphan .doc unexpectedly already paired: {p.orphan_doc} (id={orphan_row['id']})"
            )

        # The correct_opinion should not yet have a westlaw row.
        # The orphan_opinion's only westlaw row is the wrong-pairing row we're
        # about to delete; we'd flag any *other* westlaw row on either opinion.
        for oid in (p.correct_opinion, p.orphan_opinion):
            extras = conn.execute(
                "SELECT id, source_path FROM opinion_sources "
                "WHERE opinion_id = ? AND source_reporter = 'westlaw' AND source_path != ?",
                (oid, wp),
            ).fetchall()
            for r in extras:
                errors.append(
                    f"Target opinion {oid} unexpectedly already has a westlaw row "
                    f"(id={r['id']}, path={r['source_path']})"
                )
    return errors


def _doc_text_length(path: Path) -> int:
    """Return the on-disk byte size of the .doc; opinion_sources.text_length stores this."""
    try:
        return path.stat().st_size
    except OSError:
        return 0


def apply(db_path: Path, dry_run: bool) -> None:
    conn = get_connection(db_path)
    conn.execute("BEGIN")

    pre_errors = _verify(conn)
    if pre_errors:
        print("PRE-FLIGHT FAILED:")
        for e in pre_errors:
            print(f"  - {e}")
        conn.execute("ROLLBACK")
        conn.close()
        return

    print(f"Pre-flight OK: {len(PAIRS)} pairs match expected state.\n")

    deleted = inserted = 0
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    for p in PAIRS:
        wp = str(p.wrong_paired_path())
        op = str(p.orphan_path())
        print(f"vol {p.vol} page {p.page}:")

        # 1. Delete wrong pairing
        row = conn.execute(
            "SELECT id FROM opinion_sources "
            "WHERE source_path = ? AND source_reporter = 'westlaw'",
            (wp,),
        ).fetchone()
        sid = row["id"]
        if dry_run:
            print(f"  WOULD DELETE opinion_sources.id={sid}: opinion={p.wrong_paired_opinion} ↔ {p.wrong_paired_doc}")
        else:
            conn.execute("DELETE FROM opinion_sources WHERE id = ?", (sid,))
            conn.execute(
                "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) "
                "VALUES (?, ?, 'opinion_sources.westlaw', ?, NULL)",
                (BATCH, p.wrong_paired_opinion, wp),
            )
            print(f"  DELETED opinion_sources.id={sid}: opinion={p.wrong_paired_opinion} ↔ {p.wrong_paired_doc}")
        deleted += 1

        # 2. Insert correct pairing for the .doc that was mis-paired
        if dry_run:
            print(f"  WOULD INSERT: opinion={p.correct_opinion} ↔ {p.wrong_paired_doc}")
        else:
            tlen = _doc_text_length(p.wrong_paired_path())
            conn.execute(
                "INSERT INTO opinion_sources "
                "(opinion_id, source_reporter, source_path, text_length, is_primary, added_at) "
                "VALUES (?, 'westlaw', ?, ?, 0, ?)",
                (p.correct_opinion, wp, tlen, now),
            )
            conn.execute(
                "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) "
                "VALUES (?, ?, 'opinion_sources.westlaw', NULL, ?)",
                (BATCH, p.correct_opinion, wp),
            )
            print(f"  INSERTED: opinion={p.correct_opinion} ↔ {p.wrong_paired_doc}")
        inserted += 1

        # 3. Insert pairing for the orphan .doc
        if dry_run:
            print(f"  WOULD INSERT: opinion={p.orphan_opinion} ↔ {p.orphan_doc}")
        else:
            tlen = _doc_text_length(p.orphan_path())
            conn.execute(
                "INSERT INTO opinion_sources "
                "(opinion_id, source_reporter, source_path, text_length, is_primary, added_at) "
                "VALUES (?, 'westlaw', ?, ?, 0, ?)",
                (p.orphan_opinion, op, tlen, now),
            )
            conn.execute(
                "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) "
                "VALUES (?, ?, 'opinion_sources.westlaw', NULL, ?)",
                (BATCH, p.orphan_opinion, op),
            )
            print(f"  INSERTED: opinion={p.orphan_opinion} ↔ {p.orphan_doc}")
        inserted += 1
        print()

    if dry_run:
        conn.execute("ROLLBACK")
        print(f"DRY RUN — would delete {deleted} rows, insert {inserted} rows.")
        print("Re-run with --apply to commit.")
    else:
        conn.commit()
        log_provenance(
            conn, "fix_westlaw_pairings",
            rows_affected=deleted + inserted,
            notes=f"batch={BATCH}; deleted={deleted}, inserted={inserted}",
        )
        print(f"DONE — deleted {deleted} rows, inserted {inserted} rows.")
        print("Next: python -m ndcourts_mcp.merge_westlaw_text --apply --batch westlaw-text-merge-2026-04-27-pairings")
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--apply", action="store_true",
                        help="Commit changes (default is dry-run)")
    args = parser.parse_args()
    apply(args.db, dry_run=not args.apply)


if __name__ == "__main__":
    main()

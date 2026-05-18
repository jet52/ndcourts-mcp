"""Insert new opinion rows for Westlaw .docs that represent SEPARATE
supplemental publications (concurring opinions, rehearings, per-curiam
follow-ons, memorandum decisions) rather than the main opinion.

Background: in older N.D. Reports, the bound reporter sometimes published
a supplemental opinion (concurrence, rehearing decision, follow-on per
curiam) at a discontinuous N.W. cite from the main opinion, while sharing
the same N.D. starting page. Westlaw indexes each as its own document.
The volume-based ingest paired the supplemental .doc with the main DB row
because they shared the N.D. cite — but the right model is one DB row per
distinct *publication* (each with its own N.W. cite).

This script:
  1. Detaches the supplemental .doc from the existing main opinion row
     (delete opinion_sources.westlaw row pairing them).
  2. Inserts a new opinion row for the supplemental publication, with
     date/author/text parsed from the .doc and citations from the .doc's
     "All Citations" footer.
  3. Inserts the citation rows for the new opinion.
  4. Inserts a fresh opinion_sources westlaw row pairing the .doc with
     the new opinion (is_primary=1).
  5. Special-case Chester: moves the misattached `35 N.W.2d 137` citation
     from the main row (9128) to the new row.

Usage:
    python -m ndcourts_mcp.insert_supplemental_opinions [--apply]
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .db import DEFAULT_DB_PATH, get_connection, log_provenance
from .ingest import _classify_reporter, recompute_primary
from .ingest_westlaw import _doc_to_text, _parse_westlaw_doc


BATCH = "westlaw-supplemental-publications-2026-04-28"


@dataclass(frozen=True)
class Supp:
    main_opinion_id: int
    main_cite: str             # for the notes field
    doc_path: str
    nature: str                # human description for case_name suffix / notes
    citations: list[str]       # primary first, then parallels
    date_filed: str | None     # ISO date if known to differ from .doc parse; else None
    move_cite_from_main: str | None = None  # citation to move from main row to new


SUPPLEMENTALS: list[Supp] = [
    Supp(
        main_opinion_id=458,
        main_cite="118 N.W. 820",
        doc_path="/Users/jerod/refs/nd/opin/N.D./18/0076-State-ex-rel-City-of-Minot-v-Willis.doc",
        nature="per curiam follow-on",
        citations=["118 N.W. 823 (Mem)", "18 N.D. 76"],
        date_filed=None,  # parser will pick up Nov 19, 1908
    ),
    Supp(
        main_opinion_id=2125,
        main_cite="172 N.W. 663",
        doc_path="/Users/jerod/refs/nd/opin/N.D./41/0473-Druey-v-Baldwin.doc",
        nature="Robinson, J., separate opinion",
        citations=["182 N.W. 700 (Mem)", "41 N.D. 473"],
        date_filed=None,
    ),
    Supp(
        main_opinion_id=2473,
        main_cite="181 N.W. 590",
        doc_path="/Users/jerod/refs/nd/opin/N.D./47/0266-Altenbrun-v-First-Nat-Bank-of-Rock-Lake.doc",
        nature="concurring opinion",
        citations=["181 N.W. 908", "47 N.D. 266"],
        date_filed=None,
    ),
    Supp(
        main_opinion_id=2635,
        main_cite="187 N.W. 233",
        doc_path="/Users/jerod/refs/nd/opin/N.D./48/0894-State-ex-rel-Bauer-v-Nestos.doc",
        nature="on rehearing — rehearing denied",
        citations=["187 N.W. 619", "48 N.D. 894"],
        date_filed=None,  # .doc says April 11, 1922
    ),
    Supp(
        main_opinion_id=2863,
        main_cite="195 N.W. 14",
        doc_path="/Users/jerod/refs/nd/opin/N.D./50/0025-Lincoln-Addition-Improvement-Co-v-Lenhart.doc",
        nature="per curiam (joint with Baker v. Lenhart)",
        citations=["195 N.W. 33 (Mem)", "50 N.D. 25"],
        date_filed=None,
    ),
    Supp(
        main_opinion_id=9128,
        main_cite="34 N.W.2d 418",
        doc_path="/Users/jerod/refs/nd/opin/N.D./76/0205-Chester-v-Einarson.doc",
        nature="on petition for rehearing",
        citations=["35 N.W.2d 137", "76 N.D. 205"],
        date_filed=None,  # .doc says Dec 6, 1948
        move_cite_from_main="35 N.W.2d 137",
    ),
]


def _build_text_content(parsed: dict, main_case_name: str, main_full_name: str | None,
                        nature: str, main_id: int, main_cite: str,
                        primary_cite: str, parallel_cites: list[str],
                        date_filed: str | None) -> str:
    """Build the YAML frontmatter + body text for the new opinion row.
    Mirrors the format used by the existing CL ingest so that downstream
    consumers (FTS, jetcite, etc.) see consistent layout."""
    cites_yaml = "\n".join(f' - "{c}"' for c in [primary_cite] + parallel_cites)
    title = main_case_name
    title_full = main_full_name or main_case_name
    body = parsed.get("full_bound_text") or parsed.get("opinion_text") or ""
    fm = (
        "---\n"
        f'title: "{title}"\n'
        f'title_full: "{title_full}"\n'
        f'court: "North Dakota Supreme Court"\n'
        f'date_filed: {date_filed}\n'
        "citations:\n"
        f"{cites_yaml}\n"
        f'note: "Supplemental publication ({nature}) of opinion #{main_id} '
        f'(main opinion at {main_cite})"\n'
        "---\n\n"
    )
    return fm + body


def _detect_per_curiam(parsed: dict) -> int:
    body = (parsed.get("full_bound_text") or parsed.get("opinion_text") or "")[:500]
    return 1 if body.lstrip().startswith("PER CURIAM") else 0


def apply(db_path: Path, dry_run: bool) -> None:
    conn = get_connection(db_path)
    conn.execute("BEGIN")

    inserts = 0
    detaches = 0
    cite_moves = 0
    cite_inserts = 0

    for s in SUPPLEMENTALS:
        doc = Path(s.doc_path)
        if not doc.exists():
            print(f"  SKIP: missing .doc {doc}")
            continue

        main = conn.execute(
            "SELECT case_name, case_name_full, date_filed, judges FROM opinions WHERE id = ?",
            (s.main_opinion_id,),
        ).fetchone()
        if not main:
            print(f"  SKIP: main opinion {s.main_opinion_id} not in DB")
            continue

        existing_pairing = conn.execute(
            "SELECT id FROM opinion_sources "
            "WHERE opinion_id = ? AND source_path = ? AND source_reporter = 'westlaw'",
            (s.main_opinion_id, s.doc_path),
        ).fetchone()
        if not existing_pairing:
            print(f"  SKIP: expected westlaw pairing of .doc with opinion {s.main_opinion_id} not found")
            continue

        raw = _doc_to_text(doc)
        parsed = _parse_westlaw_doc(raw) or {}

        date = s.date_filed or parsed.get("date_filed") or main["date_filed"]
        author = parsed.get("author")
        per_curiam = _detect_per_curiam(parsed)
        primary_cite = s.citations[0]
        parallel_cites = s.citations[1:]

        text_content = _build_text_content(
            parsed=parsed,
            main_case_name=main["case_name"],
            main_full_name=main["case_name_full"],
            nature=s.nature,
            main_id=s.main_opinion_id,
            main_cite=s.main_cite,
            primary_cite=primary_cite,
            parallel_cites=parallel_cites,
            date_filed=date,
        )

        case_name_suffix = f" ({s.nature})"
        new_case_name = main["case_name"] + case_name_suffix
        notes_str = (
            f"Supplemental publication ({s.nature}) of opinion #{s.main_opinion_id} "
            f"(main opinion at {s.main_cite}). Inserted by batch {BATCH}."
        )

        print(f"main {s.main_opinion_id} → new supplemental for {primary_cite}:")
        if dry_run:
            print(f"  WOULD DETACH opinion_sources.id={existing_pairing['id']}")
            print(f"  WOULD INSERT opinions row (case='{new_case_name}', date={date}, "
                  f"text_len={len(text_content)})")
            for c in s.citations:
                print(f"  WOULD INSERT citation: {c}")
            if s.move_cite_from_main:
                print(f"  WOULD MOVE citation '{s.move_cite_from_main}' from main {s.main_opinion_id} to new")
            print()
            detaches += 1
            inserts += 1
            cite_inserts += len(s.citations)
            if s.move_cite_from_main:
                cite_moves += 1
            continue

        # Detach the misattached pairing
        conn.execute("DELETE FROM opinion_sources WHERE id = ?", (existing_pairing["id"],))
        conn.execute(
            "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) "
            "VALUES (?, ?, 'opinion_sources.westlaw', ?, NULL)",
            (BATCH, s.main_opinion_id, s.doc_path),
        )
        detaches += 1

        # Insert new opinion row
        cur = conn.execute(
            """INSERT INTO opinions (
                case_name, case_name_full, date_filed, court,
                judges, per_curiam, author,
                source_reporter, source_path, text_content, notes
            ) VALUES (?, ?, ?, 'North Dakota Supreme Court', ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_case_name, main["case_name_full"], date,
                main["judges"], per_curiam, author,
                "westlaw", s.doc_path, text_content, notes_str,
            ),
        )
        new_id = cur.lastrowid
        conn.execute(
            "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) "
            "VALUES (?, ?, 'opinions.insert', NULL, ?)",
            (BATCH, new_id, f"supplemental of #{s.main_opinion_id} ({primary_cite})"),
        )
        inserts += 1
        print(f"  INSERTED opinions.id={new_id}")

        # Insert citations for the new row. reporter follows Contract 1;
        # is_primary follows the Contract-2 ladder via recompute_primary.
        for c in s.citations:
            conn.execute(
                "INSERT INTO citations (opinion_id, citation, reporter, is_primary) VALUES (?, ?, ?, 0)",
                (new_id, c, _classify_reporter(c)),
            )
            conn.execute(
                "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) "
                "VALUES (?, ?, 'citation', NULL, ?)",
                (BATCH, new_id, c),
            )
            cite_inserts += 1
        recompute_primary(conn, new_id)

        # Move misattached citation from main to new (Chester case)
        if s.move_cite_from_main:
            row = conn.execute(
                "SELECT id FROM citations WHERE opinion_id = ? AND citation = ?",
                (s.main_opinion_id, s.move_cite_from_main),
            ).fetchone()
            if row:
                conn.execute("DELETE FROM citations WHERE id = ?", (row["id"],))
                conn.execute(
                    "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) "
                    "VALUES (?, ?, 'citation', ?, NULL)",
                    (BATCH, s.main_opinion_id, s.move_cite_from_main),
                )
                # Note: the citation is also being inserted on the new row above,
                # so the net effect is a move. The changelog rows show
                # the delete on main and the insert on new.
                cite_moves += 1
                print(f"  MOVED citation '{s.move_cite_from_main}' main→new")

        # Insert opinion_sources westlaw row for the new opinion
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        try:
            tlen = doc.stat().st_size
        except OSError:
            tlen = 0
        conn.execute(
            "INSERT INTO opinion_sources "
            "(opinion_id, source_reporter, source_path, text_length, is_primary, added_at) "
            "VALUES (?, 'westlaw', ?, ?, 1, ?)",
            (new_id, s.doc_path, tlen, now),
        )
        conn.execute(
            "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) "
            "VALUES (?, ?, 'opinion_sources.westlaw', NULL, ?)",
            (BATCH, new_id, s.doc_path),
        )
        print()

    if dry_run:
        conn.execute("ROLLBACK")
        print(f"DRY RUN — would: detach {detaches} pairings, insert {inserts} opinions, "
              f"insert {cite_inserts} citations, move {cite_moves} citations.")
        print("Re-run with --apply to commit.")
    else:
        conn.commit()
        log_provenance(
            conn, "insert_supplemental_opinions",
            rows_affected=inserts + detaches + cite_inserts + cite_moves,
            notes=f"batch={BATCH}; inserts={inserts}, detaches={detaches}, "
                  f"cite_inserts={cite_inserts}, cite_moves={cite_moves}",
        )
        print(f"DONE — inserted {inserts} opinions ({detaches} detaches, "
              f"{cite_inserts} citations, {cite_moves} moves).")
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

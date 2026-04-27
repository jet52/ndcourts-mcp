"""Repair stale opinion_sources.source_path values for Westlaw .doc files.

Volume-based ingest records source_path as the temporary staging path before
the batch archiver moves the file to ~/refs/nd/opin/N.D./N/. The DB row was
never updated, leaving stale paths in three patterns:

    input-data/vol{N}/...               (vols 11–79)
    /tmp/westlaw-vol{N}/...             (vols 53–62)
    /tmp/westlaw-stage/vol{N}/...       (vols 63–68)

This pass walks every `westlaw` row whose source_path doesn't start with
~/refs/nd/opin/, resolves it to the archived file, and updates the DB.
Disambiguates same-slug collisions within a volume by matching the page
number from the opinion's `vol N.D. page` citation.

Usage:
    python -m ndcourts_mcp.backfill_westlaw_paths [--db PATH] [--apply]
"""

import argparse
import re
from pathlib import Path

from .db import DEFAULT_DB_PATH, get_connection, log_provenance

REFS_BASE = Path.home() / "refs/nd/opin"


_STALE_PATTERNS = [
    re.compile(r"^input-data/vol(\d+)/"),
    re.compile(r"^/tmp/westlaw-vol(\d+)/"),
    re.compile(r"^/tmp/westlaw-stage/vol(\d+)/"),
]


def resolve_archive_path(
    stale_path: str, opinion_id: int, citations: list[str]
) -> tuple[Path | None, str]:
    """Return (resolved_path, status). status is 'ok', 'ambiguous', or 'not-found'."""
    vol_m = None
    for pat in _STALE_PATTERNS:
        vol_m = pat.match(stale_path)
        if vol_m:
            break
    if not vol_m:
        return None, "bad-stale-format"
    vol = int(vol_m.group(1))

    p = Path(stale_path)
    name_m = re.match(r"\d+\s*-\s*(.+)\.doc$", p.name)
    if not name_m:
        return None, "bad-filename-format"
    slug = name_m.group(1).strip().replace(" ", "-")

    archive_dir = REFS_BASE / "N.D." / str(vol)
    cands = sorted(archive_dir.glob(f"*-{slug}.doc"))
    if len(cands) == 1:
        return cands[0], "ok"
    if len(cands) == 0:
        return None, "not-found"

    # Multiple matches — disambiguate by page from opinion's vol N.D. page citation
    for cite in citations:
        m = re.match(rf"{vol}\s+N\.D\.\s+(\d+)", cite)
        if m:
            page = int(m.group(1))
            page_match = archive_dir / f"{page:04d}-{slug}.doc"
            if page_match in cands:
                return page_match, "ok"
            break

    return None, "ambiguous"


def backfill(db_path: Path, apply: bool, batch: str) -> None:
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT os.id sid, os.opinion_id, os.source_path
        FROM opinion_sources os
        WHERE os.source_reporter = 'westlaw'
          AND (os.source_path LIKE 'input-data/%'
               OR os.source_path LIKE '/tmp/%')
    """).fetchall()

    print(f"Stale westlaw source_path rows: {len(rows)}")

    ok = 0
    not_found = 0
    ambiguous = 0
    bad_format = 0
    no_change = 0

    samples = {"not-found": [], "ambiguous": [], "bad-stale-format": [], "bad-filename-format": []}

    for row in rows:
        sid = row["sid"]
        oid = row["opinion_id"]
        sp = row["source_path"]

        cite_rows = conn.execute(
            "SELECT citation FROM citations WHERE opinion_id = ?", (oid,)
        ).fetchall()
        citations = [c["citation"] for c in cite_rows]

        new_path, status = resolve_archive_path(sp, oid, citations)
        if status == "ok" and new_path is not None:
            new_str = str(new_path)
            if new_str == sp:
                no_change += 1
                continue
            if apply:
                conn.execute(
                    "UPDATE opinion_sources SET source_path = ? WHERE id = ?",
                    (new_str, sid),
                )
                conn.execute(
                    "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) "
                    "VALUES (?, ?, 'opinion_sources.source_path', ?, ?)",
                    (batch, oid, sp, new_str),
                )
            ok += 1
        elif status == "not-found":
            not_found += 1
            if len(samples["not-found"]) < 10:
                samples["not-found"].append(sp)
        elif status == "ambiguous":
            ambiguous += 1
            if len(samples["ambiguous"]) < 10:
                samples["ambiguous"].append((sp, citations))
        else:
            bad_format += 1
            samples.setdefault(status, []).append(sp)

    if apply:
        conn.commit()
        log_provenance(
            conn, "backfill_westlaw_paths", rows_affected=ok,
            notes=f"resolved={ok}, not_found={not_found}, ambiguous={ambiguous}, bad_format={bad_format}",
        )
    conn.close()

    prefix = "" if apply else "DRY RUN — "
    print(f"\n{prefix}Summary:")
    print(f"  Resolved & updated:  {ok}")
    print(f"  Already correct:     {no_change}")
    print(f"  Not found in archive:{not_found}")
    print(f"  Ambiguous:           {ambiguous}")
    print(f"  Bad format:          {bad_format}")
    for kind, items in samples.items():
        if items:
            print(f"\n  Sample [{kind}]:")
            for it in items[:5]:
                print(f"    {it}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill stale Westlaw source_path values")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--apply", action="store_true", help="Actually update DB")
    parser.add_argument("--batch", default="backfill-westlaw-source-paths",
                        help="Changelog batch name")
    args = parser.parse_args()
    backfill(args.db, apply=args.apply, batch=args.batch)


if __name__ == "__main__":
    main()

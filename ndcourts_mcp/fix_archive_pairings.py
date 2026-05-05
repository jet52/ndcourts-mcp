"""Fix wrong-paired archive HTML linkages surfaced by the multi-source diff audit.

Each row in ``opinion_sources`` with ``source_reporter='archive'`` should
point at an HTML file from archive.ndcourts.gov whose ``<title>`` cites
the same opinion as the DB row. The audit (TODO §3) found 101 such
rows where the title cites a DIFFERENT opinion than the DB row — most
often two opinions in the same case-name series (e.g., serial Estate
of Feldmann opinions) where the archive scraper used a key that
collided.

This script:

  1. Parses ``<title>`` of every archive HTML under
     ``~/refs/nd/opin/archive/`` and indexes them by the neutral
     citation embedded in the title (and by the parallel N.W. cite).
  2. Walks every ``opinion_sources`` row with reporter='archive' and
     compares the file's title-citation to the linked opinion's
     citations in the ``citations`` table.
  3. Classifies each linkage as ok / move-to-correct-opinion /
     swap-with-correct-archive / detach.
  4. Applies the fixes (under ``--apply``) and logs every change to
     the changelog table for revertibility.

Classifications:
  ok                  — file's title-cite matches one of the linked opinion's
                        citations; nothing to do.
  swap                — file points at opinion-W, the title cites opinion-C, and
                        a DIFFERENT archive file matching W's citation exists.
                        Swap the linkage so file ↔ C and (the other file) ↔ W.
                        Best outcome — both opinions end up with a correct
                        archive source.
  move                — file points at W, title cites C, no other archive file
                        matches W. Move the row from W to C; W loses its
                        archive (no replacement available).
  detach              — file points at W, title cites C, but C already has its
                        own archive linkage. Just delete the wrong row from W.
  unparseable         — file is missing or its title has no parseable citation;
                        leave alone.

Usage:
    python -m ndcourts_mcp.fix_archive_pairings
        [--db PATH] [--refs PATH]
        [--apply]
        [--report triage/fix-archive-pairings-2026-05-04.md]
        [--batch fix-archive-pairings-2026-05-04]
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .db import DEFAULT_DB_PATH, log_provenance

DEFAULT_REFS_DIR = Path.home() / "refs" / "nd" / "opin"
DEFAULT_BATCH = "fix-archive-pairings-2026-05-04"

_TITLE_RE = re.compile(r"<title>([^<]+)</title>", re.IGNORECASE)
_ND_CITE_RE = re.compile(r"\b(\d{4})\s+ND\s+(\d+)\b")
_NW_CITE_RE = re.compile(r"\b(\d+)\s+N\.W\.(?:\s*(\d+)d)?\s+(\d+)\b")


@dataclass
class ArchiveTitle:
    path: str          # relative to refs_dir (e.g., "archive/2017/20170034.htm")
    title: str
    neutral_cite: str | None
    parallel_cite: str | None


@dataclass
class Linkage:
    opinion_sources_id: int
    opinion_id: int
    archive_path: str         # what the DB says
    db_citations: list[str]   # citations on the linked opinion
    title_neutral: str | None
    title_parallel: str | None
    classification: str = "unknown"
    target_opinion_id: int | None = None
    swap_archive_path: str | None = None
    note: str = ""


def _norm_cite(cite: str | None) -> str | None:
    """Normalize whitespace in a citation for comparison."""
    if not cite:
        return None
    return re.sub(r"\s+", " ", cite).strip()


def _parse_title(text: str) -> tuple[str | None, str | None, str | None]:
    """Return (title, neutral_cite, parallel_cite) from HTML."""
    m = _TITLE_RE.search(text)
    if not m:
        return None, None, None
    title = m.group(1).strip()
    nd = _ND_CITE_RE.search(title)
    nw = _NW_CITE_RE.search(title)
    neutral = f"{nd.group(1)} ND {nd.group(2)}" if nd else None
    parallel = None
    if nw:
        if nw.group(2):
            parallel = f"{nw.group(1)} N.W.{nw.group(2)}d {nw.group(3)}"
        else:
            parallel = f"{nw.group(1)} N.W. {nw.group(3)}"
    return title, neutral, parallel


def index_archives(refs_dir: Path) -> tuple[dict[str, str], dict[str, ArchiveTitle]]:
    """Build (cite → archive_path) and (archive_path → ArchiveTitle).

    The cite index uses the neutral cite when available, falling back to
    the parallel N.W. cite. Same archive file may be reachable under both.
    """
    cite_to_path: dict[str, str] = {}
    path_to_title: dict[str, ArchiveTitle] = {}

    archive_root = refs_dir / "archive"
    for f in archive_root.rglob("*.htm"):
        rel = str(f.relative_to(refs_dir))
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        title, neutral, parallel = _parse_title(text)
        path_to_title[rel] = ArchiveTitle(
            path=rel, title=title or "", neutral_cite=neutral,
            parallel_cite=parallel,
        )
        for cite in (neutral, parallel):
            if cite and cite not in cite_to_path:
                cite_to_path[cite] = rel
    return cite_to_path, path_to_title


def _title_cite_matches_opinion(
    title_neutral: str | None,
    title_parallel: str | None,
    db_citations: list[str],
) -> bool:
    cites = {_norm_cite(c) for c in db_citations}
    if title_neutral and _norm_cite(title_neutral) in cites:
        return True
    if title_parallel and _norm_cite(title_parallel) in cites:
        return True
    return False


def classify(
    conn: sqlite3.Connection,
    refs_dir: Path,
    cite_to_path: dict[str, str],
    path_to_title: dict[str, ArchiveTitle],
) -> list[Linkage]:
    """Walk all archive linkages and classify each."""
    rows = conn.execute("""
        SELECT os.id, os.opinion_id, os.source_path
        FROM opinion_sources os
        WHERE os.source_reporter = 'archive'
    """).fetchall()

    # Cache: opinion_id -> list of citations
    cite_cache: dict[int, list[str]] = defaultdict(list)
    for r in conn.execute("SELECT opinion_id, citation FROM citations"):
        cite_cache[r[0]].append(r[1])

    # Cache: opinion_id -> bool (already has at least one valid archive linkage
    # other than the row under consideration). Used to decide between move
    # and detach.
    archive_owners: dict[int, set[int]] = defaultdict(set)  # opinion_id -> {os.id}
    for r in conn.execute(
        "SELECT id, opinion_id FROM opinion_sources WHERE source_reporter='archive'"
    ):
        archive_owners[r[1]].add(r[0])

    linkages: list[Linkage] = []
    for r in rows:
        os_id, oid, path = r["id"], r["opinion_id"], r["source_path"]
        link = Linkage(
            opinion_sources_id=os_id,
            opinion_id=oid,
            archive_path=path,
            db_citations=cite_cache.get(oid, []),
            title_neutral=None,
            title_parallel=None,
        )
        title = path_to_title.get(path)
        if title is None:
            link.classification = "unparseable"
            link.note = "archive file missing on disk"
            linkages.append(link)
            continue
        link.title_neutral = title.neutral_cite
        link.title_parallel = title.parallel_cite
        if not (title.neutral_cite or title.parallel_cite):
            link.classification = "unparseable"
            link.note = "title has no parseable citation"
            linkages.append(link)
            continue
        if _title_cite_matches_opinion(
            title.neutral_cite, title.parallel_cite, link.db_citations
        ):
            link.classification = "ok"
            linkages.append(link)
            continue

        # Wrong linkage — find the correct target opinion
        target_id: int | None = None
        for cite in (title.neutral_cite, title.parallel_cite):
            if not cite:
                continue
            row = conn.execute(
                "SELECT opinion_id FROM citations WHERE citation = ? LIMIT 1",
                (cite,),
            ).fetchone()
            if row:
                target_id = row[0]
                break
        link.target_opinion_id = target_id

        if target_id is None:
            link.classification = "detach"
            link.note = "title cite not found in DB"
        else:
            target_has_archive = bool(archive_owners.get(target_id, set()) - {os_id})
            # Look for a swap candidate: an archive file matching THIS
            # opinion's citation that isn't already linked to a different
            # opinion.
            swap_path = None
            for c in link.db_citations:
                cand = cite_to_path.get(_norm_cite(c) or "")
                if cand and cand != path:
                    swap_path = cand
                    break

            if target_has_archive:
                if swap_path:
                    link.classification = "swap"
                    link.swap_archive_path = swap_path
                    link.note = (
                        f"target {target_id} already has archive; "
                        f"swap with {swap_path}"
                    )
                else:
                    link.classification = "detach"
                    link.note = f"target {target_id} already has archive"
            else:
                link.classification = "move"
                link.note = f"move linkage to opinion {target_id}"
                if swap_path:
                    link.swap_archive_path = swap_path

        linkages.append(link)
    return linkages


def apply_fixes(
    conn: sqlite3.Connection,
    linkages: list[Linkage],
    batch: str,
    refs_dir: Path,
) -> dict[str, int]:
    """Apply move/swap/detach actions. Logs every change to changelog."""
    counts = defaultdict(int)
    cur = conn.cursor()

    for link in linkages:
        if link.classification == "ok" or link.classification == "unparseable":
            continue

        if link.classification == "move":
            # Repoint the row from link.opinion_id to target_opinion_id.
            cur.execute(
                "UPDATE opinion_sources SET opinion_id = ? WHERE id = ?",
                (link.target_opinion_id, link.opinion_sources_id),
            )
            cur.execute(
                """INSERT INTO changelog (batch, opinion_id, field, old_value, new_value)
                   VALUES (?, ?, 'opinion_sources.archive', ?, ?)""",
                (batch, link.opinion_id, f"row {link.opinion_sources_id} → opinion {link.opinion_id}",
                 f"row {link.opinion_sources_id} → opinion {link.target_opinion_id}"),
            )
            counts["moved"] += 1

            # If we found a swap candidate that fits opinion_id (the row
            # we just left), insert a new linkage for it.
            if link.swap_archive_path:
                _insert_archive_link(
                    cur, link.opinion_id, link.swap_archive_path, refs_dir, batch,
                )
                counts["relinked_after_move"] += 1

        elif link.classification == "swap":
            # File belongs with target. The original opinion needs a
            # replacement linkage (swap_archive_path) since the target
            # already had its own archive.
            cur.execute(
                "UPDATE opinion_sources SET opinion_id = ? WHERE id = ?",
                (link.target_opinion_id, link.opinion_sources_id),
            )
            cur.execute(
                """INSERT INTO changelog (batch, opinion_id, field, old_value, new_value)
                   VALUES (?, ?, 'opinion_sources.archive', ?, ?)""",
                (batch, link.opinion_id, f"row {link.opinion_sources_id} → opinion {link.opinion_id}",
                 f"row {link.opinion_sources_id} → opinion {link.target_opinion_id}"),
            )
            counts["swapped"] += 1

            if link.swap_archive_path:
                _insert_archive_link(
                    cur, link.opinion_id, link.swap_archive_path, refs_dir, batch,
                )
                counts["relinked_after_swap"] += 1

        elif link.classification == "detach":
            cur.execute(
                "DELETE FROM opinion_sources WHERE id = ?",
                (link.opinion_sources_id,),
            )
            cur.execute(
                """INSERT INTO changelog (batch, opinion_id, field, old_value, new_value)
                   VALUES (?, ?, 'opinion_sources.archive', ?, NULL)""",
                (batch, link.opinion_id,
                 f"row {link.opinion_sources_id} → {link.archive_path}"),
            )
            counts["detached"] += 1

    conn.commit()
    return counts


def _insert_archive_link(cur, opinion_id: int, path: str, refs_dir: Path, batch: str):
    """Insert a new archive opinion_sources row and log it."""
    full = refs_dir / path
    text_length = full.stat().st_size if full.exists() else None
    cur.execute(
        """INSERT INTO opinion_sources
              (opinion_id, source_reporter, source_path, text_length, is_primary, added_at)
           VALUES (?, 'archive', ?, ?, 0, datetime('now'))""",
        (opinion_id, path, text_length),
    )
    new_id = cur.lastrowid
    cur.execute(
        """INSERT INTO changelog (batch, opinion_id, field, old_value, new_value)
           VALUES (?, ?, 'opinion_sources.archive', NULL, ?)""",
        (batch, opinion_id, f"row {new_id} → {path}"),
    )


def write_report(linkages: list[Linkage], counts: dict[str, int], out_path: Path,
                 applied: bool):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    by_class = defaultdict(list)
    for link in linkages:
        by_class[link.classification].append(link)

    lines: list[str] = []
    lines.append(f"# Archive linkage audit ({'applied' if applied else 'dry-run'})")
    lines.append("")
    lines.append("## Summary")
    for k in ("ok", "move", "swap", "detach", "unparseable"):
        lines.append(f"- {k:<12} {len(by_class[k])}")
    if counts:
        lines.append("")
        lines.append("## Actions")
        for k, n in counts.items():
            lines.append(f"- {k:<24} {n}")

    for label in ("move", "swap", "detach", "unparseable"):
        rows = by_class[label]
        if not rows:
            continue
        lines.append("")
        lines.append(f"## {label} ({len(rows)})")
        lines.append("| os.id | opinion_id | archive_path | DB cites | title cite | target | swap_path | note |")
        lines.append("|------:|-----------:|-------------|----------|-----------|-------:|-----------|------|")
        for r in rows[:200]:
            cites = ", ".join(r.db_citations)[:60]
            tcite = r.title_neutral or r.title_parallel or "—"
            target = str(r.target_opinion_id) if r.target_opinion_id else "—"
            swap = r.swap_archive_path or "—"
            lines.append(
                f"| {r.opinion_sources_id} | {r.opinion_id} | "
                f"`{r.archive_path}` | {cites} | {tcite} | {target} | "
                f"`{swap}` | {r.note} |"
            )
        if len(rows) > 200:
            lines.append(f"\n_… and {len(rows) - 200} more_")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    p.add_argument("--refs", type=Path, default=DEFAULT_REFS_DIR)
    p.add_argument("--apply", action="store_true",
                   help="Apply moves/swaps/detaches (default is dry-run)")
    p.add_argument("--batch", default=DEFAULT_BATCH)
    p.add_argument("--report", type=Path,
                   default=Path("triage") / f"{DEFAULT_BATCH}.md")
    args = p.parse_args()

    conn = sqlite3.connect(str(args.db))
    conn.row_factory = sqlite3.Row

    print("Indexing archive HTMLs…")
    cite_to_path, path_to_title = index_archives(args.refs)
    print(f"  {len(path_to_title)} archive files, {len(cite_to_path)} unique cites")

    print("Classifying archive linkages…")
    linkages = classify(conn, args.refs, cite_to_path, path_to_title)
    by_class = defaultdict(int)
    for l in linkages:
        by_class[l.classification] += 1
    print(f"  {len(linkages)} linkages")
    for k in ("ok", "move", "swap", "detach", "unparseable"):
        print(f"    {k:<12} {by_class[k]}")

    counts: dict[str, int] = {}
    if args.apply:
        print(f"Applying fixes (batch={args.batch})…")
        counts = apply_fixes(conn, linkages, args.batch, args.refs)
        log_provenance(
            conn,
            operation="fix_archive_pairings",
            command=" ".join(sys.argv),
            rows_affected=sum(counts.values()),
            notes=f"batch={args.batch}; "
                  + ", ".join(f"{k}={v}" for k, v in counts.items()),
        )
        for k, v in counts.items():
            print(f"  {k:<24} {v}")
    else:
        print("(dry-run; pass --apply to write changes)")

    write_report(linkages, counts, args.report, args.apply)
    print(f"\nReport: {args.report}")


if __name__ == "__main__":
    main()

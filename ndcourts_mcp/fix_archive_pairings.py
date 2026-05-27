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


def index_archives(
    refs_dir: Path, subdir: str = "archive"
) -> tuple[dict[str, str], dict[str, ArchiveTitle]]:
    """Build (cite → archive_path) and (archive_path → ArchiveTitle).

    The cite index uses the neutral cite when available, falling back to
    the parallel N.W. cite. Same archive file may be reachable under both.

    ``subdir`` selects which tree under ``refs_dir`` to walk: ``archive``
    (archive.ndcourts.gov HTML, neutral-cite era) or ``court-archive``
    (N.W.-cite-keyed archive HTML, pre-1997).
    """
    cite_to_path: dict[str, str] = {}
    path_to_title: dict[str, ArchiveTitle] = {}

    archive_root = refs_dir / subdir
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


_NEUTRAL_RE = re.compile(r"\s*(\d{4})\s+N\.?\s*D\.?\s+0*(\d+)\s*$")


def _canon_neutral(cite: str | None) -> str | None:
    """Canonicalize an ND neutral cite for equality comparison.

    `2010 ND 9`, `2010 ND 09`, and `2010 N.D. 3` are the same citation but
    differ as strings (zero-padding, "N.D." vs "ND"). _norm_cite only
    collapses whitespace, so without this a tightened neutral-cite check
    floods on format-only "mismatches". Returns None for non-neutral cites
    (e.g. N.W. parallels), which are compared via _norm_cite instead.
    """
    if not cite:
        return None
    m = _NEUTRAL_RE.match(cite)
    return f"{m.group(1)} ND {int(m.group(2))}" if m else None


def _title_cite_status(
    title_neutral: str | None,
    title_parallel: str | None,
    db_citations: list[str],
) -> str:
    """Tri-state match of an archive file's title cite against a DB row.

    Returns:
      "match"    — strong agreement: the title's neutral cite matches a DB
                   cite, OR the title has only a parallel cite and it matches.
      "mismatch" — the title HAS a neutral cite and it does NOT match any DB
                   cite. This is treated as a mismatch even when the parallel
                   cite matches, because CourtListener has cross-contaminated
                   parallel cites across unrelated opinions (e.g. WSI v.
                   Questar oid 17030: title neutral 2017 ND 216 disagrees with
                   the row's 2017 ND 241, but the shared parallel 901 N.W.2d
                   727 would otherwise mask the wrong linkage).
      "weak"     — the title has ONLY a parallel cite (no neutral) and it
                   matches. Parallel-only agreement is contamination-prone, so
                   it is not auto-blessed as "ok" nor auto-fixed; it is routed
                   to a human-verify bucket.
    """
    if title_neutral:
        tn = _canon_neutral(title_neutral)
        db_neutrals = {_canon_neutral(c) for c in db_citations} - {None}
        return "match" if tn and tn in db_neutrals else "mismatch"
    cites = {_norm_cite(c) for c in db_citations}
    if title_parallel and _norm_cite(title_parallel) in cites:
        return "weak"
    return "mismatch"


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
        status = _title_cite_status(
            title.neutral_cite, title.parallel_cite, link.db_citations
        )
        if status == "match":
            link.classification = "ok"
            linkages.append(link)
            continue
        if status == "weak":
            # Parallel-only agreement, no neutral cite to corroborate.
            # Not auto-fixed (apply_fixes has no branch for "verify") and
            # not auto-blessed — surfaced for human review.
            link.classification = "verify"
            link.note = (
                "parallel-cite-only match; no neutral cite in title to "
                "corroborate — verify manually before trusting linkage"
            )
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

        # dup-suspect guard: the tightened neutral check correctly rejects
        # these as not-"ok", but swap/detach is the WRONG remedy when the
        # source row and the title's target are actually the SAME opinion
        # ingested from two sources and never deduplicated (one row carries
        # only the N.W. parallel, the other only the neutral). Signal: the
        # archive file's own title asserts BOTH cites — its parallel matches
        # a source-row cite AND its neutral resolves to the target — and the
        # two opinions share a filing date. Route to §6 dup-queue review,
        # never auto-mutate (apply_fixes has no branch for this label).
        if target_id is not None and target_id != oid and title.parallel_cite:
            src_cites = {_norm_cite(c) for c in link.db_citations}
            if _norm_cite(title.parallel_cite) in src_cites:
                pair = conn.execute(
                    "SELECT (SELECT date_filed FROM opinions WHERE id=?) AS src_d, "
                    "       (SELECT date_filed FROM opinions WHERE id=?) AS tgt_d",
                    (oid, target_id),
                ).fetchone()
                if pair and pair["src_d"] and pair["src_d"] == pair["tgt_d"]:
                    link.classification = "dup-suspect"
                    link.note = (
                        f"source opinion {oid} and title target {target_id} "
                        f"appear to be the same case ingested from two "
                        f"sources (undeduplicated parallel/neutral split); "
                        f"§6 dup-queue, do not swap/detach"
                    )
                    linkages.append(link)
                    continue

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
    for k in ("ok", "move", "swap", "detach", "verify", "dup-suspect", "unparseable"):
        lines.append(f"- {k:<12} {len(by_class[k])}")
    if counts:
        lines.append("")
        lines.append("## Actions")
        for k, n in counts.items():
            lines.append(f"- {k:<24} {n}")

    for label in ("move", "swap", "detach", "verify", "unparseable"):
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


_NW_KEY_RE = re.compile(r"\b(\d+)\s+N\.W\.(?:\s*(\d+)d)?\s+0*(\d+)\b")
_ND_KEY_RE = re.compile(r"\b(\d{4})\s+N\.?\s*D\.?\s+0*(\d+)\b")


def cite_key(cite: str | None) -> str | None:
    """Normalize a citation into a comparison key.

    Collapses the format differences that otherwise create false
    mismatches: ``N.W.`` vs ``N.W.2d`` series, page zero-padding
    (``465 N.W.2d 0480`` == ``465 N.W.2d 480``), and ``N.D.`` vs ``ND``
    on neutral cites. Returns None if no recognizable cite is present.
    """
    if not cite:
        return None
    m = _NW_KEY_RE.search(cite)
    if m:
        return f"NW{m.group(2) or '1'}:{int(m.group(1))}:{int(m.group(3))}"
    m = _ND_KEY_RE.search(cite)
    if m:
        return f"ND:{int(m.group(1))}:{int(m.group(2))}"
    return None


def title_cite_keys(title: str) -> set[str]:
    """Every cite key appearing in an archive file's title.

    Court-archive titles occasionally splice two opinions' cites into one
    string (a scraper artifact). Capturing *all* of them lets the
    page-cardinality check recognize when the linked opinion's own cite is
    present even though a sibling's cite is also there.
    """
    keys: set[str] = set()
    for m in _NW_KEY_RE.finditer(title):
        keys.add(f"NW{m.group(2) or '1'}:{int(m.group(1))}:{int(m.group(3))}")
    for m in _ND_KEY_RE.finditer(title):
        keys.add(f"ND:{int(m.group(1))}:{int(m.group(2))}")
    return keys


@dataclass
class CourtArchiveLink:
    opinion_sources_id: int
    opinion_id: int
    archive_path: str
    title: str
    title_keys: list[str]
    classification: str
    other_opinions: list[int] = field(default_factory=list)
    note: str = ""


def classify_court_archive(
    conn: sqlite3.Connection,
    path_to_title: dict[str, ArchiveTitle],
) -> list[CourtArchiveLink]:
    """Audit ``source_reporter='court-archive'`` linkages by page cardinality.

    Court-archive titles are pre-1997 and carry only an N.W. *parallel*
    cite (no neutral), and the bound reporter routinely prints several
    N.D.R.App.P. 35.1 summary dispositions on one shared "Table" page — so
    the neutral-cite logic used for ``archive`` rows does not apply and a
    bare parallel-cite match is not by itself reliable. Instead, classify
    by how many opinions own each cite the title asserts:

      ok             — the linked opinion uniquely owns a cite named in the
                       title. The linkage is corroborated.
      shared_page    — a title cite is owned by the linked opinion *and* at
                       least one other (a shared Table page). The link may
                       be right, but the page collides; verify by DOCKET in
                       the file body (this is the Ellis/Reimers class).
      title_elsewhere— no title cite is owned by the linked opinion, but one
                       resolves to a *different* opinion. Either the linkage
                       is wrong or (commonly) only the file's <title> tag is
                       contaminated while its body is correct — verify the
                       BODY, never the title.
      unresolved     — file missing, title unparseable, or no title cite
                       resolves to any opinion.

    Report-only: fixes here require reading the file body (titles lie), so
    this function never mutates.
    """
    key_owners: dict[str, set[int]] = defaultdict(set)
    for r in conn.execute("SELECT opinion_id, citation FROM citations"):
        k = cite_key(r["citation"])
        if k:
            key_owners[k].add(r["opinion_id"])

    rows = conn.execute(
        "SELECT id, opinion_id, source_path FROM opinion_sources "
        "WHERE source_reporter = 'court-archive'"
    ).fetchall()

    links: list[CourtArchiveLink] = []
    for r in rows:
        os_id, oid, path = r["id"], r["opinion_id"], r["source_path"]
        at = path_to_title.get(path)
        if at is None or not at.title:
            links.append(CourtArchiveLink(
                os_id, oid, path, "", [], "unresolved",
                note="archive file missing or empty",
            ))
            continue
        keys = title_cite_keys(at.title)
        if not keys:
            links.append(CourtArchiveLink(
                os_id, oid, path, at.title, [], "unresolved",
                note="title has no parseable citation",
            ))
            continue

        # Precedence: a cite the linked opinion *uniquely* owns blesses the
        # link even if a sibling's cite is also spliced into the title.
        unique_to_linked = [k for k in keys
                            if key_owners.get(k) == {oid}]
        shared_with_linked = [k for k in keys
                              if oid in key_owners.get(k, set())
                              and len(key_owners[k]) > 1]
        elsewhere = sorted({
            o for k in keys for o in key_owners.get(k, set()) if o != oid
        })

        if unique_to_linked:
            cls, note = "ok", ""
        elif shared_with_linked:
            cls = "shared_page"
            note = (f"title cite {shared_with_linked[0]} shared with "
                    f"opinion(s) {elsewhere}; verify by docket in body")
        elif elsewhere:
            cls = "title_elsewhere"
            note = (f"title cite resolves to opinion(s) {elsewhere}, not the "
                    f"linked {oid}; verify file BODY (title may be contaminated)")
        else:
            cls = "unresolved"
            note = "title cite(s) match no opinion in DB"
        links.append(CourtArchiveLink(
            os_id, oid, path, at.title, sorted(keys), cls,
            other_opinions=elsewhere, note=note,
        ))
    return links


def write_court_archive_report(links: list[CourtArchiveLink], out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    by_class: dict[str, list[CourtArchiveLink]] = defaultdict(list)
    for l in links:
        by_class[l.classification].append(l)
    lines = ["# Court-archive linkage audit (report-only)", ""]
    lines.append("Page-cardinality rule; court-archive fixes require reading "
                 "the file BODY (titles are unreliable) and are not automated.")
    lines.append("")
    lines.append("## Summary")
    for k in ("ok", "shared_page", "title_elsewhere", "unresolved"):
        lines.append(f"- {k:<16} {len(by_class[k])}")
    for label in ("shared_page", "title_elsewhere", "unresolved"):
        rows = by_class[label]
        if not rows:
            continue
        lines += ["", f"## {label} ({len(rows)})",
                  "| os.id | opinion_id | other | path | title | note |",
                  "|------:|-----------:|-------|------|-------|------|"]
        for r in rows:
            other = ",".join(str(o) for o in r.other_opinions) or "—"
            lines.append(
                f"| {r.opinion_sources_id} | {r.opinion_id} | {other} | "
                f"`{r.archive_path}` | {r.title[:70]} | {r.note} |"
            )
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    p.add_argument("--refs", type=Path, default=DEFAULT_REFS_DIR)
    p.add_argument("--reporter", choices=("archive", "court-archive"),
                   default="archive",
                   help="which source tree to audit (court-archive is "
                        "report-only)")
    p.add_argument("--apply", action="store_true",
                   help="Apply moves/swaps/detaches (default is dry-run; "
                        "ignored for court-archive)")
    p.add_argument("--batch", default=DEFAULT_BATCH)
    p.add_argument("--report", type=Path, default=None)
    args = p.parse_args()

    conn = sqlite3.connect(str(args.db))
    conn.row_factory = sqlite3.Row

    if args.reporter == "court-archive":
        report = args.report or (
            Path("triage") / "court-archive-pairing-audit-2026-05-27.md")
        print("Indexing court-archive HTMLs…")
        _, path_to_title = index_archives(args.refs, subdir="court-archive")
        print(f"  {len(path_to_title)} court-archive files")
        print("Classifying court-archive linkages (page-cardinality)…")
        links = classify_court_archive(conn, path_to_title)
        by_class = defaultdict(int)
        for l in links:
            by_class[l.classification] += 1
        print(f"  {len(links)} linkages")
        for k in ("ok", "shared_page", "title_elsewhere", "unresolved"):
            print(f"    {k:<16} {by_class[k]}")
        if args.apply:
            print("(court-archive is report-only — titles lie; fixes need a "
                  "body read. No changes written.)")
        write_court_archive_report(links, report)
        print(f"\nReport: {report}")
        return

    report = args.report or (Path("triage") / f"{DEFAULT_BATCH}.md")
    print("Indexing archive HTMLs…")
    cite_to_path, path_to_title = index_archives(args.refs)
    print(f"  {len(path_to_title)} archive files, {len(cite_to_path)} unique cites")

    print("Classifying archive linkages…")
    linkages = classify(conn, args.refs, cite_to_path, path_to_title)
    by_class = defaultdict(int)
    for l in linkages:
        by_class[l.classification] += 1
    print(f"  {len(linkages)} linkages")
    for k in ("ok", "move", "swap", "detach", "verify", "dup-suspect", "unparseable"):
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

    write_report(linkages, counts, report, args.apply)
    print(f"\nReport: {report}")


if __name__ == "__main__":
    main()

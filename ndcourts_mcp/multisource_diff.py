"""Multi-source diff audit (TODO §3).

Read-only audit: for every opinion with two or more sources linked in
``opinion_sources``, load the primary text from ``opinions.text_content``
and the secondary text from disk, then compute a similarity score.
Pairs whose similarity falls below a configurable threshold are
written to a triage report — those are the candidates for human review
(genuine disagreements, wrong-paired sources, syllabus omissions, OCR
divergence past noise).

Algorithm:
  1. Normalize both texts (lowercase, strip punctuation, collapse
     whitespace) into word lists.
  2. Build the set of 4-word shingles for each.
  3. Similarity = Jaccard of the shingle sets = |A ∩ B| / |A ∪ B|.

Shingle Jaccard is robust to small OCR-level differences while still
flagging substantive content gaps (e.g., one source missing the
syllabus, or a wrong-paired source pointing at a different opinion).

Source format handling:
  - Markdown (ND, NW, NW2d): read directly.
  - Archive HTML: tags stripped, entities decoded.
  - Westlaw .doc: skipped — only 3 ND+westlaw pairs in the corpus and
    they'd need binary extraction. The 5,747 westlaw-primary pairs are
    fine since the westlaw text is in opinions.text_content.

Usage:
    python -m ndcourts_mcp.multisource_diff
        [--db PATH] [--refs PATH]
        [--threshold 0.85]
        [--out triage/multisource-diff.md]
        [--limit N]
        [--workers N]
"""

from __future__ import annotations

import argparse
import csv
import html
import multiprocessing as mp
import os
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .db import DEFAULT_DB_PATH

DEFAULT_REFS_DIR = Path.home() / "refs" / "nd" / "opin"
SHINGLE_K = 4


@dataclass
class PairResult:
    opinion_id: int
    citation: str
    case_name: str
    date_filed: str
    primary_reporter: str
    secondary_reporter: str
    secondary_path: str
    similarity: float
    primary_words: int
    secondary_words: int
    note: str = ""

    def length_ratio(self) -> float:
        if self.primary_words == 0 and self.secondary_words == 0:
            return 1.0
        big = max(self.primary_words, self.secondary_words)
        small = min(self.primary_words, self.secondary_words)
        return small / big if big else 0.0


_WORD_RE = re.compile(r"[^a-z0-9]+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def normalize_words(text: str) -> list[str]:
    """Lowercase, strip punctuation, split into words."""
    return _WORD_RE.sub(" ", text.lower()).split()


def strip_html(text: str) -> str:
    """Remove HTML tags and decode entities for archive sources."""
    text = _HTML_TAG_RE.sub(" ", text)
    return html.unescape(text)


def shingles(words: list[str], k: int = SHINGLE_K) -> set[tuple]:
    """Build the set of k-word shingles."""
    if len(words) < k:
        return {tuple(words)} if words else set()
    return {tuple(words[i:i + k]) for i in range(len(words) - k + 1)}


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def load_secondary_text(reporter: str, path: str, refs: Path) -> str | None:
    """Load text for a secondary source. Returns None for unsupported formats."""
    full = Path(path) if os.path.isabs(path) else refs / path
    if not full.exists():
        return None
    try:
        raw = full.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if reporter == "archive" or path.endswith(".htm") or path.endswith(".html"):
        return strip_html(raw)
    if path.endswith(".doc"):
        # Westlaw bound .doc — skip; would need textutil.
        return None
    return raw


def _compare_one(args: tuple) -> PairResult | None:
    """Worker entry point. args = (db_path, refs_dir_str, opinion_id)."""
    db_path, refs_str, oid = args
    refs = Path(refs_str)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    op = conn.execute(
        "SELECT id, case_name, date_filed, source_reporter, text_content "
        "FROM opinions WHERE id = ?", (oid,),
    ).fetchone()
    if op is None:
        return None
    cite_row = conn.execute(
        "SELECT citation FROM citations WHERE opinion_id = ? AND is_primary = 1 "
        "ORDER BY id LIMIT 1", (oid,),
    ).fetchone()
    citation = cite_row["citation"] if cite_row else f"opinion-{oid}"
    secondaries = conn.execute(
        "SELECT source_reporter, source_path FROM opinion_sources "
        "WHERE opinion_id = ? AND is_primary = 0", (oid,),
    ).fetchall()
    conn.close()

    primary_words = normalize_words(op["text_content"] or "")
    primary_shingles = shingles(primary_words)

    results: list[PairResult] = []
    for sec in secondaries:
        sec_text = load_secondary_text(
            sec["source_reporter"], sec["source_path"], refs,
        )
        if sec_text is None:
            results.append(PairResult(
                opinion_id=oid, citation=citation,
                case_name=op["case_name"], date_filed=op["date_filed"],
                primary_reporter=op["source_reporter"],
                secondary_reporter=sec["source_reporter"],
                secondary_path=sec["source_path"],
                similarity=-1.0,
                primary_words=len(primary_words), secondary_words=0,
                note="secondary unreadable",
            ))
            continue
        sec_words = normalize_words(sec_text)
        sec_shingles = shingles(sec_words)
        sim = jaccard(primary_shingles, sec_shingles)
        results.append(PairResult(
            opinion_id=oid, citation=citation,
            case_name=op["case_name"], date_filed=op["date_filed"],
            primary_reporter=op["source_reporter"],
            secondary_reporter=sec["source_reporter"],
            secondary_path=sec["source_path"],
            similarity=sim,
            primary_words=len(primary_words), secondary_words=len(sec_words),
        ))

    # Return the worst pair for this opinion (we'll surface all of them
    # via the merged stream, but the worker returns the full list).
    return results  # type: ignore[return-value]


def collect_opinion_ids(db_path: Path, limit: int | None) -> list[int]:
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT opinion_id FROM opinion_sources "
        "GROUP BY opinion_id HAVING COUNT(*) >= 2 "
        "ORDER BY opinion_id"
    ).fetchall()
    conn.close()
    oids = [r[0] for r in rows]
    if limit:
        oids = oids[:limit]
    return oids


def write_markdown_report(
    results: list[PairResult], threshold: float, out_path: Path,
) -> None:
    flagged = [r for r in results if 0 <= r.similarity < threshold]
    unread = [r for r in results if r.similarity < 0]
    flagged.sort(key=lambda r: (r.similarity, r.opinion_id))

    lines: list[str] = []
    lines.append(f"# Multi-source diff audit\n")
    lines.append(f"- Pairs compared:   **{len(results) - len(unread)}**")
    lines.append(f"- Below threshold:  **{len(flagged)}** (threshold = {threshold})")
    lines.append(f"- Unreadable secondary: **{len(unread)}**")
    lines.append("")

    if flagged:
        lines.append("## Flagged pairs (sorted by similarity, lowest first)\n")
        lines.append(
            "| sim | len_ratio | citation | case_name | primary | secondary | secondary_path |"
        )
        lines.append("|-----|-----------|----------|-----------|---------|-----------|----------------|")
        for r in flagged:
            cn = (r.case_name or "")[:50]
            lines.append(
                f"| {r.similarity:.3f} | {r.length_ratio():.3f} | "
                f"{r.citation} | {cn} | {r.primary_reporter} | "
                f"{r.secondary_reporter} | `{r.secondary_path}` |"
            )
        lines.append("")

    if unread:
        lines.append("## Unreadable secondary sources\n")
        lines.append("| citation | case_name | secondary | secondary_path | note |")
        lines.append("|----------|-----------|-----------|----------------|------|")
        for r in unread:
            cn = (r.case_name or "")[:50]
            lines.append(
                f"| {r.citation} | {cn} | {r.secondary_reporter} | "
                f"`{r.secondary_path}` | {r.note} |"
            )
        lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_csv_report(results: list[PairResult], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "opinion_id", "citation", "case_name", "date_filed",
            "primary_reporter", "secondary_reporter", "secondary_path",
            "similarity", "primary_words", "secondary_words", "note",
        ])
        for r in results:
            w.writerow([
                r.opinion_id, r.citation, r.case_name, r.date_filed,
                r.primary_reporter, r.secondary_reporter, r.secondary_path,
                f"{r.similarity:.4f}", r.primary_words, r.secondary_words,
                r.note,
            ])


def histogram(results: list[PairResult]) -> str:
    """Build a similarity-distribution string for the console summary."""
    bands = [
        ("0.95–1.00", 0.95, 1.01),
        ("0.85–0.95", 0.85, 0.95),
        ("0.70–0.85", 0.70, 0.85),
        ("0.50–0.70", 0.50, 0.70),
        ("0.20–0.50", 0.20, 0.50),
        ("0.00–0.20", 0.00, 0.20),
    ]
    counts = []
    for label, lo, hi in bands:
        n = sum(1 for r in results if lo <= r.similarity < hi)
        counts.append(f"  {label}: {n}")
    return "\n".join(counts)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    p.add_argument("--refs", type=Path, default=DEFAULT_REFS_DIR)
    p.add_argument("--threshold", type=float, default=0.85,
                   help="Pairs below this similarity are flagged (default 0.85)")
    p.add_argument("--out", type=Path,
                   default=Path("triage") / "multisource-diff.md",
                   help="Markdown report path")
    p.add_argument("--csv", type=Path,
                   help="Optional CSV with every pair (not just flagged)")
    p.add_argument("--limit", type=int,
                   help="Process at most N opinions (debugging)")
    p.add_argument("--workers", type=int,
                   default=max(1, mp.cpu_count() - 1),
                   help="Worker processes (default cpu-1)")
    args = p.parse_args()

    oids = collect_opinion_ids(args.db, args.limit)
    print(f"Multi-source opinions to scan: {len(oids)}")
    print(f"Workers: {args.workers}, threshold: {args.threshold}")

    db_str = str(args.db)
    refs_str = str(args.refs)
    work = [(db_str, refs_str, oid) for oid in oids]

    start = time.time()
    all_results: list[PairResult] = []
    if args.workers > 1:
        with mp.Pool(args.workers) as pool:
            for i, batch in enumerate(pool.imap_unordered(_compare_one, work, chunksize=20), 1):
                if batch is None:
                    continue
                all_results.extend(batch)
                if i % 500 == 0:
                    elapsed = time.time() - start
                    rate = i / elapsed if elapsed else 0
                    eta = (len(oids) - i) / rate if rate else 0
                    print(f"  {i}/{len(oids)} ({rate:.0f} ops/s, ETA {eta/60:.1f}m)")
    else:
        for i, w_args in enumerate(work, 1):
            batch = _compare_one(w_args)
            if batch is not None:
                all_results.extend(batch)
            if i % 500 == 0:
                print(f"  {i}/{len(oids)}")

    elapsed = time.time() - start
    print(f"\nDone in {elapsed/60:.1f}m. {len(all_results)} pairs compared.\n")

    flagged = [r for r in all_results if 0 <= r.similarity < args.threshold]
    unread = [r for r in all_results if r.similarity < 0]
    print(f"Below threshold ({args.threshold}): {len(flagged)}")
    print(f"Unreadable secondary:               {len(unread)}")
    print()
    print("Similarity distribution:")
    print(histogram(all_results))

    write_markdown_report(all_results, args.threshold, args.out)
    print(f"\nReport written to {args.out}")

    if args.csv:
        write_csv_report(all_results, args.csv)
        print(f"Per-pair CSV at {args.csv}")


if __name__ == "__main__":
    main()

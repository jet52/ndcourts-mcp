"""Ingest the N.D. Administrative Code (N.D.A.C.) into a corpus DB.

Source: ~/refs/reg/NDAC (produced by ~/code/code-mirror, same family as the
N.D.C.C. mirror). Layout has two article forms:
  title-<T>/article-<T>-<AA>.md                      (small, single-file)
  title-<T>/article-<T>-<AA>/chapter-<T>-<AA>-<CC>.md (multi-chapter)
Sections appear as ``### §`` headings, like the N.D.C.C. mirror. This output is
current text only, so this is a current-text v1 (point-in-time deferred). The
canonical citation form is N.D.A.C. § ... — matching jetcite's normalized
'regulation' cites, so opinions cross-link.

Usage:
    python -m ndcourts_mcp.ingest_admin                # dry run summary
    python -m ndcourts_mcp.ingest_admin --apply        # build admincode.db
    python -m ndcourts_mcp.ingest_admin --apply --limit-titles 2
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import corpus
from .ingest_statutes import _SECTION_RE, _REPEAL_RE

DEFAULT_SRC = Path("/Users/jerod/refs/reg/NDAC")
PUB_DATE = "2025-07-01"  # "as published" date; lets pre-date queries warn honestly


def parse_sections(text: str) -> list[dict]:
    """Extract ### § section blocks (number, heading, body, repeal status)."""
    out: list[dict] = []
    matches = list(_SECTION_RE.finditer(text))
    for i, m in enumerate(matches):
        sec_num = m.group(1)
        heading = m.group(2).strip().rstrip(".")
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        repealed = "[repealed]" in heading.lower() or bool(
            re.match(r"(?i)^\s*repealed\b", body)
        )
        rm = _REPEAL_RE.search(body or heading)
        out.append({
            "sec_num": sec_num,
            "heading": None if heading.lower().startswith("[repealed") else (heading or None),
            "text": body or heading,
            "repealed": repealed,
            "repeal_auth": rm.group(1).strip() if rm else None,
        })
    return out


def section_files(src: Path, limit_titles: int | None) -> list[Path]:
    """All section-bearing .md files (chapter files + single-file articles),
    excluding _title.md / _article.md metadata."""
    titles = sorted((d for d in src.glob("title-*") if d.is_dir()), key=lambda p: p.name)
    if limit_titles:
        titles = titles[:limit_titles]
    files: list[Path] = []
    for tdir in titles:
        # single-file articles directly under the title
        files += [p for p in tdir.glob("article-*.md") if not p.name.startswith("_")]
        # multi-chapter articles: article-*/chapter-*.md
        for adir in tdir.glob("article-*"):
            if adir.is_dir():
                files += [p for p in adir.glob("chapter-*.md") if not p.name.startswith("_")]
    return sorted(files)


def build(db_path: Path, src: Path, *, limit_titles: int | None, batch: str) -> dict:
    conn = corpus.get_corpus_connection(db_path, must_exist=False)
    corpus.create_corpus_schema(conn)

    files = section_files(src, limit_titles)
    n_prov = n_ver = n_amend = 0
    seen: set[str] = set()
    for f in files:
        for sec in parse_sections(f.read_text()):
            citation = f"N.D.A.C. § {sec['sec_num']}"
            key = corpus.cite_key(citation)
            if key in seen:
                continue
            seen.add(key)
            status = "repealed" if sec["repealed"] else "active"
            src_auth = (
                f"Repealed by {sec['repeal_auth']}" if sec["repeal_auth"]
                else f"current text (N.D.A.C., as of {PUB_DATE})"
            )
            pid = conn.execute(
                "INSERT INTO provisions (corpus, citation, cite_key, heading, status) "
                "VALUES (?,?,?,?,?)",
                ("admin", citation, key, sec["heading"], status),
            ).lastrowid
            n_prov += 1
            vid = conn.execute(
                "INSERT INTO provision_versions "
                "(provision_id, effective_start, effective_end, text_content, "
                " source_authority, source_url, batch) VALUES (?,?,?,?,?,?,?)",
                (pid, PUB_DATE, None, sec["text"], src_auth, None, batch),
            ).lastrowid
            n_ver += 1
            conn.execute("UPDATE provisions SET current_version_id=? WHERE id=?", (vid, pid))
            corpus.index_version_fts(conn, vid, citation, sec["heading"], sec["text"])
            if sec["repealed"]:
                conn.execute(
                    "INSERT OR IGNORE INTO amendments "
                    "(provision_id, version_id, action, effective_date, raw_date, "
                    " authority, source_url, raw) VALUES (?,?,?,?,?,?,?,?)",
                    (pid, vid, "repealed", None, None, sec["repeal_auth"], None,
                     f"Repealed by {sec['repeal_auth']}" if sec["repeal_auth"] else "Repealed"),
                )
                n_amend += 1
    conn.commit()

    conn.execute(
        "INSERT INTO provenance (operation, command, source_paths, rows_affected, notes) "
        "VALUES (?,?,?,?,?)",
        ("ingest_admin", batch, str(src), n_prov,
         f"{n_prov} sections (current text as of {PUB_DATE}); {n_amend} repeals"),
    )
    conn.commit()
    conn.close()
    return {"sections": n_prov, "versions": n_ver, "repeals": n_amend}


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest N.D. Administrative Code (current text)")
    ap.add_argument("--apply", action="store_true", help="write the DB (default: dry run)")
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC, help="NDAC markdown root")
    ap.add_argument("--db", type=Path, default=None, help="output DB path")
    ap.add_argument("--limit-titles", type=int, default=None, help="first N titles only")
    args = ap.parse_args()

    if not args.src.is_dir():
        sys.exit(f"NDAC source not found: {args.src}")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    batch = f"admin-ingest-{stamp}"

    if not args.apply:
        files = section_files(args.src, args.limit_titles)
        print(f"NDAC root {args.src}: {len(files)} section-bearing files")
        for f in files[:3]:
            secs = parse_sections(f.read_text())
            print(f"  {f.relative_to(args.src)}: {len(secs)} sections; "
                  f"e.g. {secs[0]['sec_num'] if secs else '—'} "
                  f"[{secs[0]['heading'] if secs else ''}]")
        print("\nDry run only. Re-run with --apply to build the DB.")
        return

    db_path = args.db or corpus.resolve_corpus_db_path("admin")
    print(f"Building admin-code corpus → {db_path}")
    stats = build(db_path, args.src, limit_titles=args.limit_titles, batch=batch)
    print(f"Done: {stats}")


if __name__ == "__main__":
    main()

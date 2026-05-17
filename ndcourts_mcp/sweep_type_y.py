"""Corpus-wide Type Y supplemental-publication detector (read-only).

Type Y: a Westlaw .doc paired to a DB opinion whose own "All Citations"
N.W. cite differs from every N.W. cite the DB row carries. In the bound
N.D. Reports era the reporter sometimes published a supplemental
(rehearing, concurrence, follow-on per curiam) at a *discontinuous* N.W.
page while sharing the N.D. starting page; the volume-based ingest paired
that supplemental .doc with the main DB row on the shared N.D. cite. The
correct model is one DB row per distinct publication, so each mismatch is
a candidate for a new opinion row (see insert_supplemental_opinions).

This module only *detects* and reports — it never writes to the DB.
Output: triage/type-y-sweep-<date>.tsv with one row per flagged pairing.

Usage:
    python -m ndcourts_mcp.sweep_type_y [--db DB] [--limit N] [--out PATH]
"""

from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
from datetime import date
from pathlib import Path

from .db import DEFAULT_DB_PATH, get_connection
from .ingest_nwcite import _split_frontmatter
from .ingest_westlaw import _parse_westlaw_doc
from .multisource_diff import jaccard, normalize_words, shingles


def _doc_to_text_hard(path: Path, timeout: int = 25) -> str:
    """textutil .doc->txt with a process-group hard kill on timeout.

    The shared ingest_westlaw._doc_to_text uses subprocess.run(timeout=),
    which on a wedged/D-state textutil child fails to reap it and blocks
    indefinitely (observed: a single bad .doc hung a corpus sweep for
    hours). Here textutil runs in its own session so a timeout can
    SIGKILL the whole process group and move on."""
    p = subprocess.Popen(
        ["textutil", "-convert", "txt", "-stdout", str(path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True,
    )
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        p.wait()
        raise
    if p.returncode != 0:
        raise RuntimeError(f"textutil rc={p.returncode} on {path}: {err[:120]}")
    return out

REFS_ROOT = Path.home() / "refs" / "nd" / "opin"

_NW = re.compile(r"\b(\d+)\s+N\.\s?W\.(?:\s?2d)?\s+(\d+)\b")
_ND = re.compile(r"\b(\d+)\s+N\.\s?D\.\s+(\d+)\b")


def _resolve(sp: str) -> Path:
    """opinion_sources.source_path is a mix of absolute (bound-volume
    ingest) and refs-relative (receive_westlaw _archive_doc) paths.
    Resolve relative ones against REFS_ROOT — same rule invariants uses."""
    return Path(sp) if os.path.isabs(sp) else REFS_ROOT / sp

# Above this body-jaccard the .doc and the DB row are the SAME opinion,
# so an N.W.-cite mismatch is a citation-accuracy bug (OCR/metadata wrong
# digit), NOT a separate Type Y publication. Below it, a shared N.D. cite
# + distinct text is a genuine supplemental-publication candidate.
_SAME_OPINION_J = 0.55


def _nw_keys(text: str) -> set[tuple[str, str, str]]:
    """All N.W./N.W.2d cites in a string, normalized to (vol, series, page)."""
    out = set()
    for m in _NW.finditer(text or ""):
        series = "2d" if "2d" in m.group(0).replace(" ", "") else "1"
        out.add((m.group(1), series, m.group(2)))
    return out


def _doc_nw_keys(parsed: dict) -> set[tuple[str, str, str]]:
    cites = list(parsed.get("all_citations") or [])
    if parsed.get("primary_citation"):
        cites.append(parsed["primary_citation"])
    keys: set[tuple[str, str, str]] = set()
    for c in cites:
        keys |= _nw_keys(c)
    return keys


def _nd_keys(text: str) -> set[tuple[str, str]]:
    return {(m.group(1), m.group(2)) for m in _ND.finditer(text or "")}


def _doc_nd_keys(parsed: dict) -> set[tuple[str, str]]:
    cites = list(parsed.get("all_citations") or [])
    if parsed.get("primary_citation"):
        cites.append(parsed["primary_citation"])
    out: set[tuple[str, str]] = set()
    for c in cites:
        out |= _nd_keys(c)
    return out


_HDR = ("kind\toid\tdate_filed\tcase_name\tjac\tnd_shared\t"
        "db_nw\tdoc_nw\tdb_cites\tdoc_path\n")


def _row_tsv(r: dict) -> str:
    return "\t".join(str(x) for x in (
        r["kind"], r["id"], r["date_filed"], r["case_name"],
        r.get("jac", ""), r.get("nd", ""),
        r.get("db_nw", ""), r.get("doc_nw", ""),
        (r["cites"] or "").replace("\t", " "),
        r["source_path"])) + "\n"


def _classify(r, db_nw) -> dict:
    doc = _resolve(r["source_path"])
    if not doc.exists():
        return dict(r, kind="MISSING_DOC", doc_nw="", db_nw="", jac="", nd="")
    try:
        parsed = _parse_westlaw_doc(_doc_to_text_hard(doc)) or {}
    except Exception as e:  # noqa: BLE001 — incl. TimeoutExpired (hard-killed)
        return dict(r, kind="PARSE_ERROR", doc_nw=type(e).__name__,
                    db_nw=str(e)[:50], jac="", nd="")
    doc_nw = _doc_nw_keys(parsed)
    if not doc_nw:
        return dict(r, kind="DOC_NO_NW", doc_nw="", db_nw="", jac="", nd="")
    if not db_nw:
        return dict(r, kind="DB_NO_NW", doc_nw=_fmt(doc_nw), db_nw="",
                    jac="", nd="")
    if not doc_nw.isdisjoint(db_nw):
        return {}  # .doc N.W. cite matches the DB row — normal pairing
    # N.W. cites disjoint: separate publication (Type Y) vs same-opinion
    # citation-accuracy bug — decided by body text + shared N.D. cite.
    db_body = _split_frontmatter(r["text_content"] or "")[1]
    doc_body = parsed.get("full_bound_text") or parsed.get("opinion_text") or ""
    j = jaccard(shingles(normalize_words(doc_body)),
                shingles(normalize_words(db_body)))
    nd_shared = bool(_doc_nd_keys(parsed) & _nd_keys(r["cites"] or ""))
    if j >= _SAME_OPINION_J:
        kind = "CITE_DISCREPANCY"        # same opinion, wrong N.W. digit
    elif nd_shared:
        kind = "TYPE_Y"                  # distinct text, shared N.D. page
    else:
        kind = "TYPE_Y_NO_NDSHARE"       # distinct text, N.D. cite differs
    return dict(r, kind=kind, doc_nw=_fmt(doc_nw), db_nw=_fmt(db_nw),
                jac=f"{j:.2f}", nd="Y" if nd_shared else "n")


def sweep(conn, limit: int | None, out_path: Path,
          resume: bool) -> dict:
    rows = conn.execute(
        """SELECT o.id, o.date_filed, o.case_name, o.text_content,
                  s.source_path,
                  (SELECT GROUP_CONCAT(citation, ' | ') FROM citations c
                    WHERE c.opinion_id = o.id) AS cites
           FROM opinion_sources s
           JOIN opinions o ON o.id = s.opinion_id
           WHERE s.source_reporter = 'westlaw'
             AND s.source_path LIKE '%.doc'
           ORDER BY o.date_filed, o.id"""
    ).fetchall()
    if limit:
        rows = rows[:limit]

    done: set[int] = set()
    progress = out_path.with_suffix(".progress")
    if resume and out_path.exists():
        for ln in out_path.read_text().splitlines()[1:]:
            parts = ln.split("\t")
            if len(parts) > 1 and parts[1].isdigit():
                done.add(int(parts[1]))
        mode = "a"
    else:
        mode = "w"

    from collections import Counter
    tally: Counter = Counter()
    n = len(rows)
    with out_path.open(mode) as f:
        if mode == "w":
            f.write(_HDR)
        for i, r in enumerate(rows):
            if r["id"] in done:
                continue
            if i % 100 == 0:
                msg = (f"{i}/{n} scanned, {sum(tally.values())} flagged "
                       f"(oid {r['id']}, {r['date_filed']})")
                progress.write_text(msg)
                print("  .. " + msg, file=sys.stderr, flush=True)
            db_nw = _nw_keys(r["cites"] or "")
            res = _classify(dict(r), db_nw)
            if res:
                f.write(_row_tsv(res))
                f.flush()
                tally[res["kind"]] += 1
    progress.write_text(f"DONE {n}/{n}")
    print(f"  done: {n} scanned", file=sys.stderr)
    return dict(tally)


def _fmt(keys: set[tuple[str, str, str]]) -> str:
    return ";".join(
        f"{v} N.W.{'2d' if s == '2d' else ''} {p}"
        for v, s, p in sorted(keys, key=lambda k: (int(k[0]), int(k[2])))
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--resume", action="store_true",
                    help="append, skipping oids already in --out")
    ap.add_argument("--out", type=Path,
                    default=Path("triage")
                    / f"type-y-sweep-{date.today().isoformat()}.tsv")
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(args.db)
    try:
        tally = sweep(conn, args.limit, args.out, args.resume)
    finally:
        conn.close()
    print(f"wrote -> {args.out}")
    for k, c in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"  {k}: {c}")


if __name__ == "__main__":
    main()

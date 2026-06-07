"""Build the point-in-time history of the ND Constitution (Model 1).

Spine = the numbering that actually applied at each date. The 1889 constitution
used continuous section numbering (§1–217 across Articles I–XIX, with the
Prohibition article and the Schedule numbered separately); the 1981
reorganization introduced today's article/section scheme. This module builds the
**1889 base layer** (validated against the official 1889 publication and the
State Constitutions Project transcription), to which amendments 1894–1980 are
applied step by step from their authoritative session-law PDFs.

Output: a dedicated `constitution_history.db` (the same versioned-provision
schema as the other corpora) kept separate from the served modern `const`
corpus until the full historical layer is complete and validated.

Base source (text): ndconst.org's 1889 snapshot — a clean transcription that
matches the official 1889 publication. Validation harness lives alongside.

Usage:
    python -m ndcourts_mcp.ingest_constitution_history            # dry run (structure)
    python -m ndcourts_mcp.ingest_constitution_history --apply    # build base layer
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

from . import corpus

AMENDMENTS_JSON = Path(__file__).resolve().parent.parent / "data" / "constitution_amendments.json"

BASE_URL = "https://ndconst.org"
SNAPSHOT_1889 = "date/1889-11-02"
ADOPTED = "1889-11-02"           # ratified Oct 1, 1889; effective Nov 2, 1889
REORG = "1981-01-01"             # the 1981 reorganization renumbered everything
REORG_EVE = "1980-12-31"         # provisional cap for 1889-scheme sections
OFFICIAL_PDF = "https://ndlegis.gov/sites/default/files/resource/historical-constitution-documents/1889-constitution.pdf"
USER_AGENT = "ndcourts-mcp constitution-history ingest (CC0 corpus build)"


def fetch(page: str) -> str:
    url = f"{BASE_URL}/{page}?do=export_raw"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


# Headers are usually one line ("===== ARTICLE I. ... ====="), but Article
# XVIII's title wraps onto a second line with the closing ===== on a third, so
# match the opening and don't require a trailing ===== on the same line.
_ART_RE = re.compile(r"=====\s*ARTICLE\s+([IVXLCDM]+)\b\.?\s*(.*)")
_SPECIAL_RE = re.compile(r"=====\s*(SCHEDULE|PREAMBLE)\b\.?\s*(.*)", re.I)
_SEC_RE = re.compile(r"===\s*Section\s+([0-9A-Za-z]+)\.\s*===")


def _clean_name(s: str) -> str:
    return re.sub(r"\s*=+\s*$", "", s).strip().rstrip(".").strip()


def parse_1889(raw: str) -> list[dict]:
    """Parse the 1889 snapshot into ordered sections with article context."""
    out: list[dict] = []
    art_roman = art_name = None
    special = None  # 'SCHEDULE' | 'PREAMBLE'
    sec = None
    buf: list[str] = []

    def flush():
        nonlocal sec, buf
        text = "\n".join(buf).strip()
        if special == "PREAMBLE":
            if text:
                out.append({"kind": "preamble", "text": text})
        elif sec is not None:
            out.append({
                "kind": "section",
                "art_roman": art_roman, "art_name": art_name,
                "special": special, "secnum": sec, "text": text,
            })
        buf = []

    for line in raw.splitlines():
        m = _SPECIAL_RE.match(line)
        if m:
            flush(); sec = None; special = m.group(1).upper()
            art_roman = None; art_name = _clean_name(m.group(2)) or special.title()
            if special == "PREAMBLE":
                sec = "_"  # capture body
            continue
        m = _ART_RE.match(line)
        if m:
            flush(); sec = None; special = None
            art_roman = m.group(1); art_name = _clean_name(m.group(2))
            continue
        m = _SEC_RE.match(line)
        if m:
            flush(); sec = m.group(1)
            continue
        if sec is not None:
            buf.append(line)
    flush()
    return out


def citation_for(item: dict, seen_main: set) -> str:
    """Citation in the 1889 numbering. Main-body Articles I–XIX are continuously
    numbered (cite '§ N'); the Prohibition article and the Schedule are numbered
    separately (cite with their container to stay unique)."""
    if item["kind"] == "preamble":
        return "N.D. Const. pmbl."
    n = item["secnum"]
    if item["special"] == "SCHEDULE":
        return f"N.D. Const. Schedule, § {n}"
    name = (item.get("art_name") or "").lower()
    if "prohibition" in name:
        return f"N.D. Const. art. {item['art_roman']}, § {n} (Prohibition)"
    # main body: continuous numbering, but guard against an unexpected restart
    if n in seen_main:
        return f"N.D. Const. art. {item['art_roman']}, § {n}"
    return f"N.D. Const. § {n}"


def build(db_path: Path, *, batch: str) -> dict:
    raw = fetch(SNAPSHOT_1889)
    items = parse_1889(raw)
    conn = corpus.get_corpus_connection(db_path, must_exist=False)
    corpus.create_corpus_schema(conn)

    seen_main: set = set()
    n_prov = n_ver = 0
    for it in items:
        cite = citation_for(it, seen_main)
        if it["kind"] == "section" and not it.get("special") and "art." not in cite:
            seen_main.add(it["secnum"])
        key = corpus.cite_key(cite)
        hierarchy = None
        if it["kind"] == "section":
            import json
            hierarchy = json.dumps({
                "scheme": "1889",
                "article_roman": it.get("art_roman"),
                "article_name": it.get("art_name"),
                "section": it["secnum"],
            })
        try:
            pid = conn.execute(
                "INSERT INTO provisions (corpus, citation, cite_key, hierarchy, heading, status) "
                "VALUES (?,?,?,?,?,?)",
                ("const", cite, key, hierarchy, None, "active"),
            ).lastrowid
        except Exception as e:
            print(f"  WARN dup {cite}: {e}", file=sys.stderr); continue
        n_prov += 1
        vid = conn.execute(
            "INSERT INTO provision_versions "
            "(provision_id, effective_start, effective_end, text_content, "
            " source_authority, source_url, batch) VALUES (?,?,?,?,?,?,?)",
            (pid, ADOPTED, REORG_EVE, it["text"],
             "1889 Constitution (adopted Oct. 1, 1889; in effect Nov. 2, 1889)",
             OFFICIAL_PDF, batch),
        ).lastrowid
        conn.execute("UPDATE provisions SET current_version_id=? WHERE id=?", (vid, pid))
        corpus.index_version_fts(conn, vid, cite, None, it["text"])
        n_ver += 1

    conn.execute(
        "INSERT INTO provenance (operation, command, source_paths, rows_affected, notes) "
        "VALUES (?,?,?,?,?)",
        ("ingest_constitution_history:base1889", batch, BASE_URL, n_prov,
         f"1889 base layer: {n_prov} provisions (effective {ADOPTED}..{REORG_EVE}, "
         f"to be subdivided by amendments)"),
    )
    conn.commit()
    amd = apply_amendments(conn, batch=batch)
    conn.close()
    return {"provisions": n_prov, "versions": n_ver, **amd}


def _day_before(iso: str) -> str:
    d = datetime.strptime(iso, "%Y-%m-%d").date() - timedelta(days=1)
    return d.isoformat()


def apply_amendments(conn, *, batch: str) -> dict:
    """Apply the source-verified pre-1981 amendments (data/constitution_amendments
    .json) in order on top of the 1889 base. 'new_article' appends an Amendment
    Article; 'amend_section' caps the target section's current version at the day
    before the effective date and adds the amended text as a new version."""
    if not AMENDMENTS_JSON.exists():
        return {"amendments_applied": 0}
    records = json.loads(AMENDMENTS_JSON.read_text()).get("amendments", [])
    n_new = n_mod = 0
    for r in records:
        eff = r["effective_date"]
        auth = r.get("authority")
        url = (r.get("source_urls") or [None])[0]
        if r["type"] == "new_article":
            cite = r["citation"]
            pid = conn.execute(
                "INSERT INTO provisions (corpus, citation, cite_key, hierarchy, heading, status) "
                "VALUES (?,?,?,?,?,?)",
                ("const", cite, corpus.cite_key(cite),
                 json.dumps({"scheme": "1889-amendment", "amendment_number": r.get("number")}),
                 r.get("heading"), "active"),
            ).lastrowid
            vid = conn.execute(
                "INSERT INTO provision_versions (provision_id, effective_start, effective_end, "
                " text_content, source_authority, source_url, batch) VALUES (?,?,?,?,?,?,?)",
                (pid, eff, REORG_EVE, r["text"], auth, url, batch),
            ).lastrowid
            conn.execute("UPDATE provisions SET current_version_id=? WHERE id=?", (vid, pid))
            corpus.index_version_fts(conn, vid, cite, r.get("heading"), r["text"])
            n_new += 1
        elif r["type"] == "amend_section":
            cite = r["target"]
            row = conn.execute(
                "SELECT p.id pid, v.id vid FROM provisions p "
                "JOIN provision_versions v ON v.id=p.current_version_id "
                "WHERE p.cite_key=?", (corpus.cite_key(cite),)).fetchone()
            if not row:
                print(f"  WARN amend §{cite}: target not found", file=sys.stderr); continue
            conn.execute("UPDATE provision_versions SET effective_end=? WHERE id=?",
                         (_day_before(eff), row["vid"]))
            vid = conn.execute(
                "INSERT INTO provision_versions (provision_id, effective_start, effective_end, "
                " text_content, source_authority, source_url, batch) VALUES (?,?,?,?,?,?,?)",
                (row["pid"], eff, REORG_EVE, r["text"], auth, url, batch),
            ).lastrowid
            conn.execute("UPDATE provisions SET current_version_id=? WHERE id=?", (vid, row["pid"]))
            corpus.index_version_fts(conn, vid, cite, None, r["text"])
            n_mod += 1
        # record the amendment event
        pid_for_event = conn.execute(
            "SELECT id FROM provisions WHERE cite_key=?",
            (corpus.cite_key(r.get("citation") or r.get("target")),)).fetchone()
        conn.execute(
            "INSERT OR IGNORE INTO amendments (provision_id, action, effective_date, "
            " election_date, affected, amendment_number, authority, source_url, raw) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (pid_for_event["id"] if pid_for_event else None,
             "adopted" if r["type"] == "new_article" else "amended",
             eff, r.get("election_date"), r.get("affected") or r.get("citation") or r.get("target"),
             r.get("number"), auth, url, r.get("heading") or ""),
        )
    conn.commit()
    return {"amendments_applied": n_new + n_mod, "new_articles": n_new, "section_amendments": n_mod}


def main() -> None:
    ap = argparse.ArgumentParser(description="Build ND Constitution point-in-time history (Model 1)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--db", type=Path, default=Path("/Users/jerod/code/ndcourts-mcp/constitution_history.db"))
    args = ap.parse_args()

    raw = fetch(SNAPSHOT_1889)
    items = parse_1889(raw)
    secs = [i for i in items if i["kind"] == "section"]
    arts: dict = {}
    for s in secs:
        k = s.get("special") or s.get("art_roman")
        arts.setdefault(k, []).append(s["secnum"])
    print(f"Parsed: 1 preamble + {len(secs)} sections across {len(arts)} containers")
    seen: set = set()
    for k, nums in arts.items():
        print(f"  {str(k):10} §§ {nums[0]}..{nums[-1]} ({len(nums)} sections)")
    # show citation scheme on a few
    print("\nSample citations:")
    seen = set()
    for it in items[:3] + [i for i in items if i['kind']=='section'][-3:]:
        c = citation_for(it, seen)
        if it["kind"]=="section" and "art." not in c and not it.get("special"): seen.add(it["secnum"])
        print(f"  {c}")

    if not args.apply:
        print("\nDry run only. Re-run with --apply to build the base layer.")
        return
    stats = build(args.db, batch="const-history-base1889")
    print(f"\nBuilt {args.db}: {stats}")


if __name__ == "__main__":
    main()

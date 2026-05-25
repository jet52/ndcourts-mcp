"""Backfill text_citations.antecedent_name for opinions that cite a shared
(colliding) reporter page, so rebuild_cited_by can disambiguate them.

Fast path: for each colliding-cite row, locate the cite's surface text
(raw_text) inside the citing opinion and run jetcite's extract_antecedent_name
on the preceding prose — skipping the full (slow) jetcite matcher sweep. Only
UPDATEs antecedent_name on still-NULL colliding rows (idempotent / resumable).
"""
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from jetcite import extract_antecedent_name  # noqa: E402
from ndcourts_mcp import cite_extract as ce  # noqa: E402

DB = REPO / "opinions.db"


def _name_for(text: str, raw_text: str, normalized: str) -> str | None:
    """First non-None antecedent name among occurrences of the cite in text."""
    needles = [raw_text] if raw_text else []
    if normalized and normalized != raw_text:
        needles.append(normalized)
    for needle in needles:
        start = 0
        for _ in range(12):  # cap occurrences scanned
            pos = text.find(needle, start)
            if pos < 0:
                break
            name = extract_antecedent_name(text, pos)
            if name:
                return name
            start = pos + len(needle)
    return None


def main() -> int:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    lookup = ce.build_citation_lookup(conn)
    coll_keys = {k for k, v in lookup.items() if len(v) > 1}

    rows = conn.execute(
        "SELECT opinion_id, normalized, raw_text FROM text_citations "
        "WHERE cite_type='case' AND antecedent_name IS NULL"
    ).fetchall()
    targets: dict[int, list[tuple[str, str]]] = {}
    for r in rows:
        if r["normalized"] in coll_keys or ce._normalize_cite_key(r["normalized"]) in coll_keys:
            targets.setdefault(r["opinion_id"], []).append((r["normalized"], r["raw_text"]))

    total_rows = sum(len(v) for v in targets.values())
    print(f"opinions: {len(targets)}, colliding rows still NULL: {total_rows}", flush=True)

    updated = done = 0
    for oid, cites in targets.items():
        row = conn.execute("SELECT text_content FROM opinions WHERE id=?", (oid,)).fetchone()
        if not row:
            continue
        text = row[0]
        for normalized, raw_text in cites:
            name = _name_for(text, raw_text or "", normalized)
            if name:
                conn.execute(
                    "UPDATE text_citations SET antecedent_name=? WHERE opinion_id=? AND normalized=?",
                    (name, oid, normalized))
                updated += 1
        done += 1
        if done % 1000 == 0:
            conn.commit()
            print(f"  {done}/{len(targets)} opinions, {updated} named", flush=True)

    conn.commit()
    print(f"DONE: {done} opinions, {updated} colliding rows got an antecedent_name", flush=True)
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

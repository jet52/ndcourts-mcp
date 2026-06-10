"""Apply the PDF-verified citing-text cite corrections (class 1).

For each VERIFIED row in triage/flip-verification-2026-06-09.tsv the citing
opinion's court PDF contains the corrected cite and does NOT contain the
corrupted one, so every occurrence of the corrupted cite in text_content is
scraper-OCR digit corruption -> replace all. Also patches the on-disk
source markdown so a future full re-ingest doesn't resurrect the corruption.

Usage: apply_citeflips_2026-06-09.py [--apply]
"""
import argparse, csv, re, sqlite3, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ndcourts_mcp.db import log_change, log_provenance

BATCH = "citeflip-surgical-2026-06-09"
REFS = Path.home() / "refs/nd/opin"

ap = argparse.ArgumentParser()
ap.add_argument("--apply", action="store_true")
args = ap.parse_args()

conn = sqlite3.connect("opinions.db")
rows = [r for r in csv.DictReader(open("triage/flip-verification-2026-06-09.tsv"), delimiter="\t")
        if r["pdf_verdict"] == "VERIFIED"]

# dedupe (oid, bad, good)
fixes = sorted({(int(r["citing_oid"]), r["bad_cite"], r["good_cite"]) for r in rows})
print(f"{len(rows)} verified rows -> {len(fixes)} distinct (opinion, bad, good) fixes")

n_db = n_md = 0
touched = set()
for oid, bad, good in fixes:
    text, sp = conn.execute(
        "SELECT text_content, source_path FROM opinions WHERE id=?", (oid,)).fetchone()
    cnt = text.count(bad)
    if cnt == 0:
        print(f"  oid{oid}: '{bad}' not found (already fixed?) — skip")
        continue
    new_text = text.replace(bad, good)
    md_note = ""
    md_path = None
    if sp:
        p = Path(sp) if sp.startswith("/") else REFS / sp
        if p.exists():
            md = p.read_text()
            mcnt = md.count(bad)
            if mcnt:
                md_path, md_note = p, f"; markdown {p.name} ×{mcnt}"
    print(f"  oid{oid}: {bad} -> {good} ×{cnt}{md_note}")
    if args.apply:
        conn.execute("UPDATE opinions SET text_content=? WHERE id=?", (new_text, oid))
        log_change(conn, BATCH, oid, "text_content.citefix", f"{bad} x{cnt}", good,
                   authority="court PDF (corrected cite present, corrupted absent; "
                             "parallel-cite consistency, triage/flip-verification-2026-06-09.tsv)")
        if md_path:
            md_path.write_text(md.replace(bad, good))
            n_md += 1
        n_db += 1
        touched.add(oid)

if args.apply:
    log_provenance(conn, "citeflip-surgical", command="triage/apply_citeflips_2026-06-09.py --apply",
                   rows_affected=n_db,
                   notes=f"{n_db} cite fixes across {len(touched)} opinions; {n_md} markdown files patched")
    conn.commit()
    print(f"\nAPPLIED: {n_db} fixes, {len(touched)} opinions, {n_md} markdown files")
else:
    print("\nDRY RUN — re-run with --apply")

"""Apply the 5 oddball cite fixes (class 2 residue). Authority varies per row."""
import sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ndcourts_mcp.db import log_change, log_provenance

BATCH = "citeflip-surgical-oddballs-2026-06-09"
REFS = Path.home() / "refs/nd/opin"
FIXES = [
    (12567, "569 N.W.2d 568", "569 N.W.2d 563",
     "Braaten v. Deere, 1997 ND 202 = 569 N.W.2d 563 (citations table); court PDF prints no parallel — the parallel was added by our source and corrupted"),
    (12736, "670 N.W.2d 195", "570 N.W.2d 195",
     "State v. Clark, 1997 ND 199 = 570 N.W.2d 195; 670 N.W.2d is 2003-era, impossible in a 1998 opinion; PDF is image-OCR"),
    (13449, "634 N.W.2d 627", "634 N.W.2d 527",
     "City of West Fargo v. Ross, 2001 ND 163 = 634 N.W.2d 527 (citations table); court PDF prints no parallel"),
    (16116, "885 N.W.2d 819", "835 N.W.2d 819",
     "Jensen v. Jensen, 2013 ND 144 = 835 N.W.2d 819; 885 N.W.2d is 2016-era, impossible in a 2013 opinion; PDF prints no parallel"),
    (15948, "599 N.W.3d 323", "599 N.W.2d 323",
     "Svedberg, 1999 ND 181 = 599 N.W.2d 323; court PDF prints N.W.2d; N.W.3d did not exist in 1999"),
]
apply = "--apply" in sys.argv
conn = sqlite3.connect("opinions.db")
n = 0
for oid, bad, good, auth in FIXES:
    text, sp = conn.execute("SELECT text_content, source_path FROM opinions WHERE id=?", (oid,)).fetchone()
    cnt = text.count(bad)
    print(f"oid{oid}: {bad} -> {good} ×{cnt}")
    if cnt == 0:
        continue
    if apply:
        conn.execute("UPDATE opinions SET text_content=? WHERE id=?", (text.replace(bad, good), oid))
        log_change(conn, BATCH, oid, "text_content.citefix", f"{bad} x{cnt}", good, authority=auth)
        if sp:
            p = Path(sp) if sp.startswith("/") else REFS / sp
            if p.exists() and bad in (md := p.read_text()):
                p.write_text(md.replace(bad, good)); print(f"  markdown {p.name} patched")
        n += 1
if apply:
    log_provenance(conn, "citeflip-oddballs", command="triage/apply_oddballs_2026-06-09.py --apply",
                   rows_affected=n, notes="5 per-item-verified cite fixes; 2 court typos preserved (14127, 16894)")
    conn.commit(); print(f"APPLIED {n}")

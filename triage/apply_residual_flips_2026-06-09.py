"""Final pinpoint-queue residue: 4 opinions with double digit flips (year+page
corrupted in the same cite string), each verified against the citing court PDF
(or, for 16362, by name+double-convergence on one real case). 16446 is a court
typo (PDF prints 'Jaste v. Gailfus, 2004 ND 87') — preserved verbatim."""
import sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ndcourts_mcp.db import log_change, log_provenance

BATCH = "citeflip-surgical-residual-2026-06-09"
REFS = Path.home() / "refs/nd/opin"
FIXES = [  # (oid, [(bad, good), ...], authority)
    (14384, [("2008 ND 195", "2003 ND 195"), ("672 N.W.2d 648", "672 N.W.2d 643")],
     "court PDF prints 'Linser, 2003 ND 195, ¶ 11, 672 N.W.2d 643'"),
    (17071, [("2016 ND 122", "2015 ND 122"), ("863 N.W.2d 621", "863 N.W.2d 521")],
     "court PDF prints 'Nelson, 2015 ND 122, ¶ 5, 863 N.W.2d 521'"),
    (13175, [("1999 ND 187", "1999 ND 137"), ("697 N.W.2d 644", "597 N.W.2d 644")],
     "court PDF prints 'Syvertson, 1999 ND 137, ¶¶ 26-27, 597 N.W.2d 644' (State v. Syvertson, oid 12929)"),
    (16362, [("2009 ND 48, ¶¶ 15-16, 768 N.W.2d 783", "2009 ND 43, ¶¶ 15-16, 763 N.W.2d 783")],
     "named case Interest of J.S.L. = 2009 ND 43 = 763 N.W.2d 783 (oid 15168); both 1-digit fixes converge on it"),
]
apply = "--apply" in sys.argv
conn = sqlite3.connect("opinions.db")
n = 0
for oid, pairs, auth in FIXES:
    text, sp = conn.execute("SELECT text_content, source_path FROM opinions WHERE id=?", (oid,)).fetchone()
    new = text
    for bad, good in pairs:
        cnt = new.count(bad)
        print(f"oid{oid}: {bad} -> {good} ×{cnt}")
        new = new.replace(bad, good)
    if new == text:
        continue
    if apply:
        conn.execute("UPDATE opinions SET text_content=? WHERE id=?", (new, oid))
        for bad, good in pairs:
            log_change(conn, BATCH, oid, "text_content.citefix", bad, good, authority=auth)
        if sp:
            p = Path(sp) if sp.startswith("/") else REFS / sp
            if p.exists():
                md = p.read_text(); md2 = md
                for bad, good in pairs:
                    md2 = md2.replace(bad, good)
                if md2 != md:
                    p.write_text(md2); print(f"  markdown {p.name} patched")
        n += 1
if apply:
    log_provenance(conn, "citeflip-residual", command="triage/apply_residual_flips_2026-06-09.py --apply",
                   rows_affected=n, notes=f"batch {BATCH}; final pinpoint-queue residue; 16446 court typo preserved")
    conn.commit(); print(f"APPLIED {n}")

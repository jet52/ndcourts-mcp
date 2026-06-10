"""Apply the 6 PDF-verified citing-side pincite corrections (class 2, group A)."""
import re, sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ndcourts_mcp.db import log_change, log_provenance

BATCH = "pincite-surgical-2026-06-09"
REFS = Path.home() / "refs/nd/opin"
FIXES = [  # (citing_oid, cite, bad_pin, good_pin) — each verified vs citing court PDF
    (15752, "2010 ND 10", "88", "33"),
    (13766, "1999 ND 89", "87", "37"),
    (13438, "1997 ND 112", "83", "33"),
    (15151, "2007 ND 146", "81", "31"),
    (16253, "2009 ND 205", "82", "32"),
    (15946, "2000 ND 111", "18", "13"),
]
apply = "--apply" in sys.argv
conn = sqlite3.connect("opinions.db")
n = 0
for oid, cite, bad, good in FIXES:
    text, sp = conn.execute("SELECT text_content, source_path FROM opinions WHERE id=?", (oid,)).fetchone()
    pat = re.compile("(" + re.escape(cite) + r"\s*,\s*¶¶?\s*)" + bad + r"\b")
    new_text, cnt = pat.subn(r"\g<1>" + good, text)
    print(f"oid{oid}: {cite} ¶{bad} -> ¶{good} ×{cnt}")
    if cnt != 1:
        print("  !! expected exactly 1 occurrence — skipping"); continue
    if apply:
        conn.execute("UPDATE opinions SET text_content=? WHERE id=?", (new_text, oid))
        log_change(conn, BATCH, oid, "text_content.pincite", f"{cite}, ¶ {bad}", f"{cite}, ¶ {good}",
                   authority="citing opinion's court PDF prints the corrected pincite (triage/pincite_direction_2026-06-09.py)")
        if sp:
            p = Path(sp) if sp.startswith("/") else REFS / sp
            if p.exists():
                md = p.read_text()
                nm, c2 = pat.subn(r"\g<1>" + good, md)
                if c2 == 1:
                    p.write_text(nm); print(f"  markdown {p.name} patched")
        n += 1
if apply:
    log_provenance(conn, "pincite-surgical", command="triage/apply_pinflips_2026-06-09.py --apply",
                   rows_affected=n, notes="6 citing-side pincite digit flips, PDF-verified")
    conn.commit(); print(f"APPLIED {n}")
else:
    print("DRY RUN")

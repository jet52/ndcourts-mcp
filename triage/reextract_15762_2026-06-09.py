"""One-off pdfminer re-extract of oid 15762 (2011 ND 242, State v. Mittleider).
DB copy is CL-format OCR (corrupted ¶ markers: [118]=[¶18]; star pagination;
'MeCLINTOCK'). Keep the frontmatter/header prefix through the 'Decided' line,
replace everything after with the full court-PDF text (pdfminer, clean)."""
import re, sqlite3, sys
from pathlib import Path
from pdfminer.high_level import extract_text
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ndcourts_mcp.db import log_change, log_provenance

BATCH = "reextract-pdfminer-15762-2026-06-09"
REFS = Path.home() / "refs/nd/opin"
PDF = REFS / "pdfs/2011/2011ND242.pdf"
MARK = re.compile(r"\[\s*¶\s*(\d+)\s*\]")

conn = sqlite3.connect("opinions.db")
cur = conn.execute("SELECT text_content FROM opinions WHERE id=15762").fetchone()[0]
m = re.search(r"(?m)^Decided 2011-12-22\s*$", cur)
assert m, "no Decided line"
body = extract_text(str(PDF))
assert body.startswith("Filed 12/22/11")
new = cur[:m.end()].rstrip() + "\n\n" + body.strip() + "\n"
nums = [int(g) for g in MARK.findall(new)]
print("markers:", nums)
assert nums == list(range(1, max(nums) + 1)), "marker sequence not contiguous"
assert not any(c in new for c in "¡¿■£„"), "artifacts remain"
assert "McClintock" in new and "*309" not in new
print(f"old {len(cur)} chars -> new {len(new)} chars")
if "--apply" in sys.argv:
    conn.execute("UPDATE opinions SET text_content=? WHERE id=15762", (new,))
    log_change(conn, BATCH, 15762, "text_content",
               "OCR-corrupted CL-format body (¶ markers misread as digits: [118]=[¶18]; star pagination)",
               f"pdfminer re-extract from {PDF}", authority="court PDF re-extraction (pdfminer)")
    (REFS / "markdown/2011/2011ND242.md").write_text(new, encoding="utf-8")
    log_provenance(conn, "reextract_pdfminer", command="triage/reextract_15762_2026-06-09.py --apply",
                   rows_affected=1, notes=f"batch {BATCH}; 2011 ND 242 marker recovery ¶1-20")
    conn.commit()
    print("APPLIED")

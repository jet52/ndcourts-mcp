"""For each SAME-class pinpoint flag, determine the defect side:
  - citing PDF's pincite for this cite  vs  our citing text's pincite
  - cited opinion's PDF max [¶N]        vs  our cited text's max
Read-only."""
import csv, re, sqlite3
from pathlib import Path
from pdfminer.high_level import extract_text

conn = sqlite3.connect("opinions.db")
PDF_ROOT = Path.home() / "refs/nd/opin/pdfs"
MARK = re.compile(r"\[?¶\s*(\d+)\]")

def pdf_path(oid):
    sp = conn.execute("SELECT source_path FROM opinions WHERE id=?", (oid,)).fetchone()[0] or ""
    m = re.search(r"(\d{4})ND(\d+)\.md$", sp)
    if not m: return None
    p = PDF_ROOT / m.group(1) / f"{m.group(1)}ND{int(m.group(2))}.pdf"
    return p if p.exists() else None

cache = {}
def ptext(p):
    if p not in cache:
        try: cache[p] = extract_text(str(p))
        except Exception: cache[p] = ""
    return cache[p]

# the SAME rows from the pinpoint queue: cite resolves to the cited oid AND
# parallel agrees -> only the pincite or the cited copy can be wrong
same = [r for r in csv.DictReader(open("triage/pinpoint-classified-2026-06-09.tsv"), delimiter="\t")
        if r["class"] == "SAME"]
pin_rows = {(r["citing_oid"], r["cited_neutral_cite"]): r for r in
            csv.DictReader(open("triage/audit-pinpoint-range-2026-06-09.tsv"), delimiter="\t")}

for r in same:
    citing, cite, cited = int(r["citing_oid"]), r["cite"], int(r["cited_oid"])
    pq = pin_rows.get((r["citing_oid"], cite))
    pin, mx = pq["pincite_para"], pq["max_marker_in_db"]
    # citing side: what pincite does the citing PDF print for this cite?
    cp = pdf_path(citing)
    citing_pdf_pins = []
    if cp:
        t = " ".join(ptext(cp).split())
        citing_pdf_pins = re.findall(re.escape(cite) + r"\s*,\s*¶¶?\s*([\d\s,-]{1,9}\d)", t)
    # cited side: PDF max marker
    dp = pdf_path(cited)
    cited_pdf_max = None
    if dp:
        nums = [int(m) for m in re.findall(r"\[?¶\s*(\d+)\]", ptext(dp))]
        cited_pdf_max = max(nums) if nums else None
    print(f"citing oid{citing} cites {cite} ¶{pin} (our cited max {mx}) | "
          f"citing-PDF pins for this cite: {citing_pdf_pins or 'no PDF/none'} | "
          f"cited oid{cited} PDF max ¶: {cited_pdf_max if dp else 'no PDF'}")

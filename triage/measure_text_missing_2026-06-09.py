"""For each TEXT_MISSING gap with a PDF: extract the missing paragraph(s) from
the court PDF and measure length/content. Splits the class into SIGNATURE
(one-line names) vs SUBSTANTIVE (real paragraphs). Read-only."""
import csv, re, sqlite3
from pathlib import Path
from pdfminer.high_level import extract_text
conn = sqlite3.connect("opinions.db")
MARK = re.compile(r"\[¶\s*(\d+)\]")
rows = [r for r in csv.DictReader(open("triage/para-gap-classified-2026-06-09.tsv"), delimiter="\t")
        if r["main_cause"] == "TEXT_MISSING" and r["has_pdf"] == "True"]
out = []
for i, r in enumerate(rows):
    oid = int(r["oid"])
    sp = conn.execute("SELECT source_path FROM opinions WHERE id=?", (oid,)).fetchone()[0]
    m = re.search(r"(\d{4})ND(\d+)\.md$", sp)
    pdf = Path.home() / f"refs/nd/opin/pdfs/{m.group(1)}/{m.group(1)}ND{int(m.group(2))}.pdf"
    if not pdf.exists():
        out.append((oid, r["case_name"], r["date"], "", "NO_PDF", "", "")); continue
    try:
        t = extract_text(str(pdf))
    except Exception as ex:
        out.append((oid, r["case_name"], r["date"], "", "PDF_ERR", str(ex)[:40], "")); continue
    ptoks = [(mm.start(), mm.end(), int(mm.group(1))) for mm in MARK.finditer(t)]
    pmap = {}
    for j, (s, e, n) in enumerate(ptoks):
        end = ptoks[j+1][0] if j+1 < len(ptoks) else len(t)
        pmap.setdefault(n, t[e:end].strip())
    for gm in re.finditer(r"¶(\d+)(?:-(\d+))?:TEXT_MISSING", r["gap_detail"]):
        a, b = int(gm.group(1)), int(gm.group(2) or gm.group(1))
        for n in range(a, b + 1):
            body = pmap.get(n)
            if body is None:
                out.append((oid, r["case_name"], r["date"], n, "PDF_LACKS_MARKER", "", "")); continue
            words = body.split()
            is_sig = len(body) < 160 and not re.search(r"\b(the|of|and|to|that)\b", body.lower())
            klass = "SIGNATURE" if is_sig else "SUBSTANTIVE"
            out.append((oid, r["case_name"], r["date"], n, klass, len(body), " ".join(words)[:100]))
    if (i + 1) % 100 == 0:
        print(f"...{i+1}/{len(rows)}")
w = csv.writer(open("triage/text-missing-measured-2026-06-09.tsv", "w"), delimiter="\t", lineterminator="\n")
w.writerow(["oid","case_name","date","missing_para","class","pdf_len","pdf_text_head"])
w.writerows(out)
from collections import Counter
print(Counter(o[4] for o in out))

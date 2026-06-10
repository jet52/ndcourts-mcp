"""Digit-flip exposure audit for the substantive-missing cohort (the 226
worklist opinions — analyzer texts with demonstrated extraction failures).

For every [¶N] present in BOTH the DB text and the court PDF extraction,
compare the ordered sequence of digit tokens (runs of digits). Page-footer
digits at form feeds are stripped from the PDF side. Mismatched ¶s are
written to triage/digit-compare-2026-06-09.tsv with both token sequences
for verification. Read-only."""
import csv, re, sqlite3
from pathlib import Path
from pdfminer.high_level import extract_text

conn = sqlite3.connect("opinions.db")
MARK = re.compile(r"\[\s*¶\s*(\d+)\s*\]")
DIGITS = re.compile(r"\d+")

rows = list(csv.DictReader(open("triage/text-missing-measured-2026-06-09.tsv"), delimiter="\t"))
oids = sorted({int(r["oid"]) for r in rows if r["class"] == "SUBSTANTIVE"})
spliced = {(int(r["oid"]), int(r["missing_para"])) for r in rows}

def para_map(text):
    toks = [(m.start(), m.end(), int(m.group(1))) for m in MARK.finditer(text)]
    out = {}
    for j, (s, e, n) in enumerate(toks):
        end = toks[j + 1][0] if j + 1 < len(toks) else len(text)
        out.setdefault(n, text[e:end])
    return out

out = []
n_para = 0
for i, oid in enumerate(oids):
    text, sp = conn.execute(
        "SELECT text_content, source_path FROM opinions WHERE id=?", (oid,)).fetchone()
    m = re.search(r"(\d{4})ND(\d+)\.md$", sp or "")
    if not m:
        continue
    pdf = Path.home() / f"refs/nd/opin/pdfs/{m.group(1)}/{m.group(1)}ND{int(m.group(2))}.pdf"
    if not pdf.exists():
        continue
    try:
        pt = extract_text(str(pdf))
    except Exception:
        continue
    pt = re.sub(r"\n\s*\d+\s*\n\s*\x0c", "\n", pt)  # page footers
    db_map, pdf_map = para_map(text), para_map(pt)
    for n in sorted(set(db_map) & set(pdf_map)):
        if (oid, n) in spliced:
            continue  # just spliced from this PDF — identical by construction
        d_db = DIGITS.findall(db_map[n])
        d_pdf = DIGITS.findall(pdf_map[n])
        n_para += 1
        if d_db != d_pdf:
            out.append((oid, m.group(0)[:-3], n, " ".join(d_db)[:200], " ".join(d_pdf)[:200]))
    if (i + 1) % 50 == 0:
        print(f"...{i+1}/{len(oids)}")

w = csv.writer(open("triage/digit-compare-2026-06-09.tsv", "w"), delimiter="\t", lineterminator="\n")
w.writerow(["oid", "cite", "para", "db_digits", "pdf_digits"])
w.writerows(out)
print(f"compared {n_para} ¶s across {len(oids)} opinions; {len(out)} ¶s with digit mismatches "
      f"in {len({o[0] for o in out})} opinions -> triage/digit-compare-2026-06-09.tsv")

"""Verify each DIGIT_FLIP fix against the citing opinion's court PDF:
the corrected cite must appear in fresh pdfminer text and the corrupted
one must not. Read-only."""
import csv, re, sqlite3
from pathlib import Path
from pdfminer.high_level import extract_text

conn = sqlite3.connect("opinions.db")
rows = [r for r in csv.DictReader(open("triage/parallel-pair-classified-2026-06-09.tsv"), delimiter="\t")
        if r["class"].endswith("DIGIT_FLIP")]

PDF_ROOT = Path.home() / "refs/nd/opin/pdfs"

def pdf_for(oid):
    sp = conn.execute("SELECT source_path FROM opinions WHERE id=?", (oid,)).fetchone()[0] or ""
    m = re.search(r"(\d{4})ND(\d+)\.md$", sp)
    if not m:
        return None
    p = PDF_ROOT / m.group(1) / f"{m.group(1)}ND{int(m.group(2))}.pdf"
    return p if p.exists() else None

cache = {}
def pdf_text(p):
    if p not in cache:
        try:
            cache[p] = " ".join(extract_text(str(p)).split())
        except Exception:
            cache[p] = ""
    return cache[p]

out = []
from collections import Counter
stat = Counter()
for r in rows:
    oid = int(r["citing_oid"])
    bad = r["nd_cite"] if r["class"] == "ND_DIGIT_FLIP" else r["nw_cite"]
    good = r["fix"].split(" -> ")[1]
    p = pdf_for(oid)
    if p is None:
        v = "NO_PDF"
    else:
        t = pdf_text(p)
        if not t:
            v = "PDF_UNREADABLE"
        else:
            has_good, has_bad = good in t, bad in t
            v = ("VERIFIED" if has_good and not has_bad else
                 "PDF_HAS_BAD" if has_bad and not has_good else
                 "BOTH" if has_good and has_bad else "NEITHER")
    stat[v] += 1
    out.append((r["citing_oid"], r["citing_date"], r["class"], bad, good, v, r["context"][:100]))

w = csv.writer(open("triage/flip-verification-2026-06-09.tsv", "w"), delimiter="\t", lineterminator="\n")
w.writerow(["citing_oid","citing_date","class","bad_cite","good_cite","pdf_verdict","context"])
w.writerows(out)
print(stat)
print(f"{len(set(o[0] for o in out if o[5]=='VERIFIED'))} opinions fully PDF-verifiable")

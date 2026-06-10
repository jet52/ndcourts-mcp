"""Corpus-wide parallel-pair consistency scan: find citation strings where a
'YYYY ND n' neutral cite and its adjacent N.W.2d/3d parallel resolve to
DIFFERENT opinions (or where one side doesn't resolve and the other does).
Detects OCR digit corruption in citing texts. Read-only."""
import csv, re, sqlite3
from collections import Counter

conn = sqlite3.connect("opinions.db")

# unique-resolution maps
def build(globpat):
    m, ambig = {}, set()
    for cite, oid in conn.execute("SELECT citation, opinion_id FROM citations WHERE citation GLOB ?", (globpat,)):
        if cite in m and m[cite] != oid:
            ambig.add(cite)
        m[cite] = oid
    return m, ambig

nd_map, nd_ambig = build("[0-9][0-9][0-9][0-9] ND *")
nw_map, nw_ambig = {}, set()
for pat in ("* N.W.2d *", "* N.W.3d *"):
    m, a = build(pat)
    nw_map.update(m); nw_ambig.update(a)

PAIR = re.compile(r"(\d{4} ND \d+)\s*,\s*(?:¶¶?\s*[\d\s,–—-]{1,16},\s*)?(\d+\s*N\.W\.[23]d\s*\d+)")

rows = []
n_pairs = n_ok = 0
for oid, name, date, text in conn.execute(
    "SELECT id, case_name, date_filed, text_content FROM opinions WHERE date_filed >= '1997-01-01'"
):
    if not text:
        continue
    for m in PAIR.finditer(text):
        nd, nw = m.group(1), " ".join(m.group(2).split())
        if nd in nd_ambig or nw in nw_ambig:
            continue
        nd_oid, nw_oid = nd_map.get(nd), nw_map.get(nw)
        if nd_oid is None and nw_oid is None:
            continue
        n_pairs += 1
        if nd_oid == nw_oid:
            n_ok += 1
            continue
        ctx = " ".join(text[max(0, m.start()-80):m.end()+10].split())
        rows.append((oid, name[:40], date, nd, nd_oid or "", nw, nw_oid or "", ctx[:160]))

w = csv.writer(open("triage/parallel-pair-mismatch-2026-06-09.tsv", "w"), delimiter="\t", lineterminator="\n")
w.writerow(["citing_oid","citing_name","citing_date","nd_cite","nd_oid","nw_cite","nw_oid","context"])
w.writerows(rows)
print(f"{n_pairs} pairs checked, {n_ok} consistent, {len(rows)} mismatched")
print(f"{len(set(r[0] for r in rows))} distinct citing opinions affected")
print(Counter(1 if r[4] and r[6] else 0 for r in rows), "(1=both resolve [cross-wired], 0=one side unresolved)")

"""Subclassify parallel-pair mismatches:
  ND_DIGIT_FLIP   printed neutral is 1-digit off the true neutral of the NW cite's case
  NW_DIGIT_FLIP   printed NW cite is 1-digit off a true parallel of the neutral's case
  DB_NO_PARALLEL  neutral resolves; its case has NO N.W. parallel in citations (our gap
                  or pre-NW3d gap) and printed NW doesn't resolve
  OTHER           none of the above (regex artifact, court typo, deeper tangle)"""
import csv, re, sqlite3
from collections import Counter

conn = sqlite3.connect("opinions.db")
rows = list(csv.DictReader(open("triage/parallel-pair-mismatch-2026-06-09.tsv"), delimiter="\t"))

def cites_of(oid):
    return [c for (c,) in conn.execute("SELECT citation FROM citations WHERE opinion_id=?", (oid,))]

def digit_diff(a, b):
    if len(a) != len(b):
        return 99
    return sum(1 for x, y in zip(a, b) if x != y)

out = []
for r in rows:
    nd, nw = r["nd_cite"], r["nw_cite"]
    nd_oid = int(r["nd_oid"]) if r["nd_oid"] else None
    nw_oid = int(r["nw_oid"]) if r["nw_oid"] else None
    klass, fix = "OTHER", ""
    if nw_oid:
        true_nds = [c for c in cites_of(nw_oid) if re.fullmatch(r"\d{4} ND \d+", c)]
        best = min(true_nds, key=lambda c: digit_diff(nd, c), default=None)
        if best and digit_diff(nd, best) == 1:
            klass, fix = "ND_DIGIT_FLIP", f"{nd} -> {best}"
    if klass == "OTHER" and nd_oid:
        true_nws = [c for c in cites_of(nd_oid) if re.match(r"\d+ N\.W\.[23]d \d+$", c)]
        best = min(true_nws, key=lambda c: digit_diff(nw, c), default=None)
        if best and digit_diff(nw, best) == 1:
            klass, fix = "NW_DIGIT_FLIP", f"{nw} -> {best}"
        elif not true_nws and not nw_oid:
            klass = "DB_NO_PARALLEL"
    out.append((r["citing_oid"], r["citing_date"], nd, nw, klass, fix, r["context"][:120]))

w = csv.writer(open("triage/parallel-pair-classified-2026-06-09.tsv", "w"), delimiter="\t", lineterminator="\n")
w.writerow(["citing_oid","citing_date","nd_cite","nw_cite","class","fix","context"])
w.writerows(out)
c = Counter(o[4] for o in out)
print(c)
flip_opins = set(o[0] for o in out if o[4].endswith("DIGIT_FLIP"))
print(f"{len(flip_opins)} distinct citing opinions with >=1 digit flip")
other_opins = set(o[0] for o in out if o[4]=="OTHER")
print(f"{len(other_opins)} opinions with OTHER rows")

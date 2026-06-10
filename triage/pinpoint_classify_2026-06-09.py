"""Classify the 59 pinpoint flags by resolving the N.W.2d/3d parallel cite that
appears in the same citation string. If the parallel resolves to a DIFFERENT
opinion than the neutral cite, the citing text's neutral cite is corrupt
(or the parallel is) -> class MISMATCH. If same opinion -> the pincite itself
or our cited copy is the problem (class SAME). Read-only."""
import csv, re, sqlite3

conn = sqlite3.connect("opinions.db")
rows = list(csv.DictReader(open("triage/pinpoint-context-2026-06-09.tsv"), delimiter="\t"))

def resolve(cite):
    r = conn.execute("SELECT opinion_id FROM citations WHERE citation=?", (cite,)).fetchall()
    return [x[0] for x in r]

def meta(oid):
    return conn.execute(
        "SELECT case_name, date_filed, source_reporter FROM opinions WHERE id=?", (oid,)
    ).fetchone()

out = []
for r in rows:
    ctx = r["citing_context"]
    cite = r["cite"]
    # parallel regional cite following the neutral in the same string
    m = re.search(re.escape(cite) + r"[^|]{0,40}?(\d+)\s*N\.W\.(2|3)d\s*(\d+)", ctx)
    klass, true_oid, true_name, par = "NO_PARALLEL", "", "", ""
    if m:
        par = f"{m.group(1)} N.W.{m.group(2)}d {m.group(3)}"
        oids = resolve(par)
        if len(oids) == 1:
            true_oid = oids[0]
            tm = meta(true_oid)
            true_name = tm[0]
            klass = "SAME" if true_oid == int(r["cited_oid"]) else "MISMATCH"
        elif oids:
            klass = "PARALLEL_AMBIG"
    citing_src = meta(int(r["citing_oid"]))[2]
    out.append((r["citing_oid"], citing_src, cite, r["cited_oid"], r["cited_row_name"][:40],
                r["pin"], r["max"], klass, par, true_oid, true_name[:40]))

w = csv.writer(open("triage/pinpoint-classified-2026-06-09.tsv", "w"), delimiter="\t", lineterminator="\n")
w.writerow(["citing_oid","citing_src","cite","cited_oid","cited_row_name","pin","max",
            "class","parallel_cite","parallel_oid","parallel_name"])
w.writerows(out)
from collections import Counter
print(Counter(o[7] for o in out))
print(Counter(o[1] for o in out))

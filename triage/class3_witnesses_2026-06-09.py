"""Class-3 cluster analysis: for each PDF_HAS_BAD parallel P (held by opinion G
in our DB, but cited alongside neutral B by the court), count witnesses for
B-with-P vs G-with-P across the whole corpus, and check whether the citing
contexts name B's caption. Read-only."""
import csv, re, sqlite3
from collections import defaultdict

conn = sqlite3.connect("opinions.db")
rows = [r for r in csv.DictReader(open("triage/flip-verification-2026-06-09.tsv"), delimiter="\t")
        if r["pdf_verdict"] == "PDF_HAS_BAD" and r["class"] == "ND_DIGIT_FLIP"]

# cluster: (B_cite, G_cite) -> need P. Recover P from the classified mismatch rows.
cls = {(r["nd_cite"], r["fix"].split(" -> ")[1]): None
       for r in csv.DictReader(open("triage/parallel-pair-classified-2026-06-09.tsv"), delimiter="\t")
       if r["class"] == "ND_DIGIT_FLIP"}
pmap = defaultdict(set)
for r in csv.DictReader(open("triage/parallel-pair-mismatch-2026-06-09.tsv"), delimiter="\t"):
    pmap[r["nd_cite"]].add(r["nw_cite"])

bad_set = {r["bad_cite"] for r in rows}
clusters = {}
for r in rows:
    B, G = r["bad_cite"], r["good_cite"]
    for P in pmap.get(B, ()):
        clusters.setdefault((B, G, P), 0)

# corpus pass: count pairings neutral-with-P for B and G
PAIR = re.compile(r"(\d{4} ND \d+)\s*,\s*(?:¶¶?\s*[\d\s,–—-]{1,16},\s*)?(\d+\s*N\.W\.[23]d\s*\d+)")
counts = defaultdict(int)
targets = {b for (b, g, p) in clusters} | {g for (b, g, p) in clusters}
for (text,) in conn.execute("SELECT text_content FROM opinions WHERE date_filed >= '1997-01-01'"):
    if not text:
        continue
    for m in PAIR.finditer(text):
        nd = m.group(1)
        if nd in targets:
            counts[(nd, " ".join(m.group(2).split()))] += 1

def row_for(cite):
    r = conn.execute("SELECT o.id, o.case_name FROM opinions o JOIN citations c ON c.opinion_id=o.id WHERE c.citation=?", (cite,)).fetchone()
    return r if r else (None, "?")

print(f"{len(clusters)} (B,G,P) clusters")
out = []
for (B, G, P) in sorted(clusters):
    b_oid, b_name = row_for(B)
    g_oid, g_name = row_for(G)
    bp, gp = counts.get((B, P), 0), counts.get((G, P), 0)
    # does B already have P?
    has = conn.execute("SELECT 1 FROM citations WHERE opinion_id=? AND citation=?", (b_oid, P)).fetchone() if b_oid else None
    out.append((B, b_oid, b_name[:34], P, bp, G, g_oid, g_name[:34], gp, "B-has-P" if has else ""))
w = csv.writer(open("triage/class3-clusters-2026-06-09.tsv", "w"), delimiter="\t", lineterminator="\n")
w.writerow(["B_cite","B_oid","B_name","P","witnesses_B+P","G_cite","G_oid","G_name","witnesses_G+P","note"])
w.writerows(out)
for o in out:
    print(o)

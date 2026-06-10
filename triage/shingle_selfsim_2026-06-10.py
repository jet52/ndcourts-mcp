"""Audit check #6 proper: body-duplication detector via shingle
self-similarity — covers the pre-1997 markerless texts the stored-twice
sweep (which keyed on [¶N] restarts / ## Opinion headers) could not see.

For every opinion, split the body into word 8-shingles and measure the
fraction that occur more than once. A body stored twice scores ~0.5+;
ordinary opinions with quoted blocks score well under 0.15. Flag >= 0.30
with length >= 4000 chars. Read-only -> triage/shingle-selfsim-2026-06-10.tsv
"""
import csv, re, sqlite3
from collections import Counter

conn = sqlite3.connect("file:opinions.db?mode=ro", uri=True)
out = []
n = 0
for oid, name, date, sp, text in conn.execute(
        "SELECT id, case_name, date_filed, source_path, text_content FROM opinions"):
    n += 1
    body = re.sub(r"\s+", " ", text)
    words = body.split()
    if len(words) < 600:
        continue
    shingles = Counter(" ".join(words[i:i+8]) for i in range(0, len(words) - 8, 2))
    total = sum(shingles.values())
    dup = sum(c for c in shingles.values() if c > 1)
    ratio = dup / total if total else 0.0
    if ratio >= 0.30:
        out.append((oid, name[:60], date, sp, len(text), round(ratio, 3)))
out.sort(key=lambda r: -r[5])
w = csv.writer(open("triage/shingle-selfsim-2026-06-10.tsv", "w"), delimiter="\t", lineterminator="\n")
w.writerow(["oid", "case_name", "date_filed", "source_path", "len", "dup_ratio"])
w.writerows(out)
print(f"scanned {n}; flagged {len(out)} >= 0.30 dup-ratio -> triage/shingle-selfsim-2026-06-10.tsv")
for r in out[:15]:
    print("  ", r)

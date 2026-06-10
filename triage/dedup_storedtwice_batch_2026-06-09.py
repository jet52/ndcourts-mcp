"""Corpus-wide stored-twice dedup (the 563-candidate sweep).

Gates per opinion:
  1. exactly two '## Opinion' headers
  2. copy1 (before the 2nd header) has contiguous [¶1..N], no letter-OCR markers
  3. copy1 max == doc-wide max marker
  4. shingle-jaccard(copy1 body, copy2) >= 0.5  (copy2 is a duplicate, not an
     appended rehearing/companion — those are held, never deleted)
Gate-failures -> hold list TSV. Changelog stores full old text. Dry-run default.
"""
import re, sqlite3, sys, csv
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ndcourts_mcp.db import log_change, log_provenance
from ndcourts_mcp.multisource_diff import normalize_words, shingles, jaccard

BATCH = "dedup-storedtwice-2026-06-09"
REFS = Path.home() / "refs/nd/opin"
MARK = re.compile(r"\[¶\s*(\d+)\]")
BADMARK = re.compile(r"\[(?:IF|If|lf|1f)\s*(\d+)\]")
apply = "--apply" in sys.argv
conn = sqlite3.connect("opinions.db")

n = 0
held = []
cands = []
for oid, name, text in conn.execute(
    "SELECT id, case_name, text_content FROM opinions WHERE text_content LIKE '%[¶%'"):
    nums = [int(x) for x in MARK.findall(text)]
    if len(nums) < 6:
        continue
    restart = any(nums[i] == 1 and nums[i-1] >= 4 and max(nums[:i]) >= 4
                  for i in range(2, len(nums) - 3))
    if not restart and text.count("\n## Opinion") < 2:
        continue
    cands.append((oid, name, text))
print(f"{len(cands)} candidates")

for oid, name, text in cands:
    hdrs = [m.start() for m in re.finditer(r"(?m)^## Opinion", text)]
    if len(hdrs) != 2:
        held.append((oid, name[:40], f"{len(hdrs)} '## Opinion' headers")); continue
    keep, drop = text[:hdrs[1]].rstrip() + "\n", text[hdrs[1]:]
    knums = [int(x) for x in MARK.findall(keep)]
    if not knums or knums != list(range(1, max(knums) + 1)):
        held.append((oid, name[:40], "copy1 not contiguous")); continue
    if BADMARK.search(keep):
        held.append((oid, name[:40], "letter-OCR marker in copy1")); continue
    if max(knums) != max(int(x) for x in MARK.findall(text)):
        held.append((oid, name[:40], f"copy1 max ¶{max(knums)} < doc max")); continue
    # similarity: copy1 body (from its own '## Opinion') vs copy2
    body1 = keep[hdrs[0]:]
    j = jaccard(shingles(normalize_words(body1)), shingles(normalize_words(drop)))
    if j < 0.5:
        held.append((oid, name[:40], f"jaccard {j:.2f} — copy2 may be distinct content")); continue
    n += 1
    if apply:
        conn.execute("UPDATE opinions SET text_content=? WHERE id=?", (keep, oid))
        log_change(conn, BATCH, oid, "text_content", text,
                   f"dropped appended OCR duplicate copy ({len(drop)} chars after the 2nd '## Opinion'); "
                   f"kept clean copy ¶1..{max(knums)}; jaccard {j:.2f}",
                   authority="opinion body stored twice (clean copy + CL/NW2d OCR copy); "
                             "4-gate batch surgery, triage/dedup_storedtwice_batch_2026-06-09.py")
        sp = conn.execute("SELECT source_path FROM opinions WHERE id=?", (oid,)).fetchone()[0]
        if sp:
            p = Path(sp) if sp.startswith("/") else REFS / sp
            if p.exists() and p.read_text() == text:
                p.write_text(keep)

if apply:
    log_provenance(conn, "dedup-storedtwice-batch",
                   command="triage/dedup_storedtwice_batch_2026-06-09.py --apply",
                   rows_affected=n, notes=f"batch {BATCH}; {n} duplicate OCR copies dropped (4-gate)")
    conn.commit()
w = csv.writer(open("triage/storedtwice-held-2026-06-09.tsv", "w"), delimiter="\t", lineterminator="\n")
w.writerow(["oid", "case_name", "reason"]); w.writerows(held)
print(f"{'APPLIED' if apply else 'DRY RUN'}: {n} dedups; {len(held)} held -> triage/storedtwice-held-2026-06-09.tsv")
from collections import Counter
print(Counter(h[2].split(' —')[0].split(' ¶')[0] for h in held))

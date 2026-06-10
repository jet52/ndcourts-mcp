"""Classify para_continuity GAP flags by probable cause + fix route.

For each gap (missing ¶n between found markers), inspect the text between the
surrounding markers for:
  CORRUPT_TOKEN    a bracketed token that contains the missing number but not a
                   clean pilcrow ([112], [T12], [(12], [¶l2], {¶ 12] ...)
  NO_MARKER_TEXT   the inter-marker span is long (>1.6x the doc's median
                   paragraph) => paragraph text likely present, marker absent
  TEXT_MISSING     span is short => the paragraph(s) are genuinely absent
Also records source_reporter, PDF availability, era. Read-only.
"""
import csv, re, sqlite3, statistics
from collections import Counter
from pathlib import Path

conn = sqlite3.connect("opinions.db")
MARK = re.compile(r"\[¶\s*(\d+)\]")
PDF_ROOT = Path.home() / "refs/nd/opin/pdfs"

rows = [r for r in csv.DictReader(open("triage/audit-para-continuity-2026-06-09.tsv"), delimiter="\t")
        if "GAP:" in r["issues"]]
print(f"{len(rows)} GAP opinions")

out = []
for r in rows:
    oid = int(r["oid"])
    text, srep, sp, date = conn.execute(
        "SELECT text_content, source_reporter, source_path, date_filed FROM opinions WHERE id=?",
        (oid,)).fetchone()
    toks = [(m.start(), m.end(), int(m.group(1))) for m in MARK.finditer(text)]
    nums = [t[2] for t in toks]
    # paragraph length baseline
    spans = [toks[i+1][0] - toks[i][1] for i in range(len(toks)-1)
             if toks[i+1][2] == toks[i][2] + 1]
    med = statistics.median(spans) if spans else 800
    # find gaps along the main ascending chain
    causes = []
    prev = None
    for i, (s, e, n) in enumerate(toks):
        if prev is not None and n > prev[2] + 1 and n <= prev[2] + 30:
            missing = list(range(prev[2] + 1, n))
            seg = text[prev[1]:s]
            cause = None
            for mnum in missing:
                pat = re.compile(r"\[[^\]\n]{0,8}" + str(mnum) + r"[^\]\n]{0,4}\]")
                cand = [c.group() for c in pat.finditer(seg) if "¶ " + str(mnum) + "]" not in c.group()
                        and f"¶{mnum}]" not in c.group()]
                if cand:
                    cause = ("CORRUPT_TOKEN", cand[0][:20]); break
            if cause is None:
                expected = med * (len(missing) + 1)
                if len(seg) > expected * 0.9:
                    cause = ("NO_MARKER_TEXT", f"{len(seg)}ch for {len(missing)+1} ¶s")
                else:
                    cause = ("TEXT_MISSING", f"{len(seg)}ch, missing ¶{missing[0]}" +
                             (f"-{missing[-1]}" if len(missing) > 1 else ""))
            causes.append((f"¶{missing[0]}" + (f"-{missing[-1]}" if len(missing)>1 else ""), *cause))
        if prev is None or n >= prev[2]:
            prev = (s, e, n)
    if not causes:
        continue
    m = re.search(r"(\d{4})ND(\d+)\.md$", sp or "")
    has_pdf = bool(m) and (PDF_ROOT / m.group(1) / f"{m.group(1)}ND{int(m.group(2))}.pdf").exists()
    main_cause = Counter(c[1] for c in causes).most_common(1)[0][0]
    out.append((oid, r["case_name"][:36], date, srep, has_pdf, len(causes), main_cause,
                "; ".join(f"{g}:{c}({d})" for g, c, d in causes[:4])))

w = csv.writer(open("triage/para-gap-classified-2026-06-09.tsv", "w"), delimiter="\t", lineterminator="\n")
w.writerow(["oid","case_name","date","source_reporter","has_pdf","n_gaps","main_cause","gap_detail"])
w.writerows(out)
print(Counter(o[6] for o in out))
print("\nby source_reporter x cause:")
for (sr, c), n in sorted(Counter((o[3], o[6]) for o in out).items()):
    print(f"  {sr:>14} {c:<16} {n}")
print("\nPDF availability for TEXT_MISSING:", Counter(o[4] for o in out if o[6]=="TEXT_MISSING"))

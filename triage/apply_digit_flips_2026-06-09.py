"""Apply the visually-verified digit-flip corrections (70 of 72 candidates;
every crop in triage/flipverify/ was read against the printed glyphs).

REJECTED (DB correct, PDF text layer wrong — ToUnicode errors):
  * 16419 ¶18 31->41 (print: N.D.C.C. § 31-11-06)
  * 16699 ¶16 09->01 (print: N.D.C.C. § 9-09-06)

COURT TYPOS PRESERVED VERBATIM (print verified; DB text must match print
even though the printed cite is bibliographically wrong):
  * 16184 ¶9 834->835 + 636->836 (print: "2013 ND 137, 835 N.W.2d 836" for
    Hoffman, whose true parallel is 834 N.W.2d 636)
  * 16917 ¶15 294->194 (print: "795 N.W.2d 194" for Johnson v. Hovland,
    whose true parallel is 795 N.W.2d 294 per CL pagination)

Safety: pass-1 guaranteed the db_token does not occur ANYWHERE in the PDF's
¶ body, so every occurrence in the DB ¶ is a flip. We still require the
standalone-occurrence count in the DB ¶ to equal the number of verified
candidate rows for that (oid, ¶, token) group; otherwise skip + report.
On-disk markdown patched in step. Dry-run default; --apply writes."""
import csv, re, sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ndcourts_mcp.db import log_change, log_provenance

BATCH = "digit-flips-pdfverified-2026-06-09"
REFS = Path.home() / "refs/nd/opin"
MARK = re.compile(r"\[\s*¶\s*(\d+)\s*\]")
REJECT = {(16419, 18, "31", "41"), (16699, 16, "09", "01")}
apply = "--apply" in sys.argv
conn = sqlite3.connect("opinions.db")

cands = list(csv.DictReader(open("triage/digit-flip-candidates-2026-06-09.tsv"), delimiter="\t"))
groups = {}
for r in cands:
    key = (int(r["oid"]), int(r["para"]), r["db_token"], r["pdf_token"])
    if key in REJECT:
        continue
    groups[key] = groups.get(key, 0) + 1

def para_span(text, n):
    toks = [(m.start(), m.end(), int(m.group(1))) for m in MARK.finditer(text)]
    for j, (s, e, num) in enumerate(toks):
        if num == n:
            return e, (toks[j + 1][0] if j + 1 < len(toks) else len(text))
    return None

n_fix = n_skip = 0
by_oid = {}
for (oid, para, db_tok, pdf_tok), cnt in sorted(groups.items()):
    by_oid.setdefault(oid, []).append((para, db_tok, pdf_tok, cnt))

skips, applied = [], []
for oid, fixes in sorted(by_oid.items()):
    text, sp = conn.execute(
        "SELECT text_content, source_path FROM opinions WHERE id=?", (oid,)).fetchone()
    new = text
    oid_log = []
    for para, db_tok, pdf_tok, cnt in fixes:
        span = para_span(new, para)
        if not span:
            skips.append((oid, para, db_tok, "no ¶ span")); continue
        s, e = span
        body = new[s:e]
        pat = re.compile(r"(?<!\d)" + re.escape(db_tok) + r"(?!\d)")
        occ = len(pat.findall(body))
        if occ != cnt:
            skips.append((oid, para, db_tok, f"occurrences {occ} != verified {cnt}")); continue
        new = new[:s] + pat.sub(pdf_tok, body) + new[e:]
        oid_log.append((para, db_tok, pdf_tok, cnt))
    if not oid_log:
        continue
    n_fix += sum(c for _, _, _, c in oid_log)
    applied.append((oid, oid_log))
    if apply:
        conn.execute("UPDATE opinions SET text_content=? WHERE id=?", (new, oid))
        log_change(conn, BATCH, oid, "text_content.digit_flip",
                   "; ".join(f"¶{p}: {a}×{c}" for p, a, b, c in oid_log),
                   "; ".join(f"¶{p}: {b}×{c}" for p, a, b, c in oid_log),
                   authority="analyzer-OCR digit flip; printed glyphs verified against court PDF "
                             "render (triage/flipverify/); PDF-side token absent guard")
        p = REFS / sp
        if p.exists():
            md = p.read_text()
            md2 = md
            for para, db_tok, pdf_tok, cnt in oid_log:
                span = para_span(md2, para)
                if not span:
                    continue
                s, e = span
                body = md2[s:e]
                pat = re.compile(r"(?<!\d)" + re.escape(db_tok) + r"(?!\d)")
                if len(pat.findall(body)) == cnt:
                    md2 = md2[:s] + pat.sub(pdf_tok, body) + md2[e:]
            if md2 != md:
                p.write_text(md2)

print(f"{'APPLIED' if apply else 'DRY RUN'}: {n_fix} token fixes in {len(applied)} opinions; {len(skips)} skips")
for oid, lg in applied[:10]:
    print(f"  oid{oid}: " + "; ".join(f"¶{p} {a}->{b}×{c}" for p, a, b, c in lg))
for s in skips:
    print("  SKIP", s)
if apply:
    log_provenance(conn, "digit-flips-pdfverified",
                   command="triage/apply_digit_flips_2026-06-09.py --apply",
                   rows_affected=len(applied),
                   notes=f"batch {BATCH}; {n_fix} digit-flip tokens fixed in {len(applied)} opinions; "
                         "2 candidates rejected (PDF text-layer ToUnicode errors); "
                         "2 court typos preserved verbatim (16184, 16917)")
    conn.commit()

"""Fix the 226 opinions with SUBSTANTIVE missing paragraphs (worklist
triage/text-missing-measured-2026-06-09.tsv) — the prime carriers of the
unaudited non-citation digit-flip exposure.

Per opinion, two paths:

1. FULL RE-EXTRACT (preferred): replace the body with a fresh pdfminer
   extraction from the court PDF (same anchor-swap as
   scripts/reextract_pdfminer_2026-06-09.py). Besides restoring the missing
   paragraphs this wipes any latent analyzer-OCR digit flips wholesale.
   Gates (all must hold, else fall through to path 2):
     * body anchor found in BOTH current text and PDF extraction
     * no OCR artifact chars in the new text
     * new [¶N] sequence contiguous 1..max
     * every ¶ number present in the CURRENT text is present in the new
       text (nothing the DB has can be lost)
     * current body has no stitched '## ' sections (e.g. '## On Rehearing'
       restitched from archive HTML — content a PDF may lack)
     * len(new) >= 0.9 * len(current) (shrink guard)

2. SURGICAL SPLICE: splice each missing ¶ verbatim from the PDF
   immediately before the next present marker (the sig-splice method,
   prose allowed). Page-footer digit lines at \x0c breaks and TRAILING
   bare digit/roman lines are stripped; form feeds removed.

Dry-run default; --apply writes text_content + on-disk markdown (logged).
"""
import csv, re, sqlite3, sys
from pathlib import Path
from pdfminer.high_level import extract_text
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ndcourts_mcp.db import log_change, log_provenance

BATCH = "substantive-missing-2026-06-09"
REFS = Path.home() / "refs/nd/opin"
MARK = re.compile(r"\[\s*¶\s*(\d+)\s*\]")
ANCHOR = re.compile(r"(?m)^(Filed .*by Clerk of Supreme Court|IN THE SUPREME COURT|IN THE COURT OF APPEALS)")
ART = set("¡¿■£„")
apply = "--apply" in sys.argv
conn = sqlite3.connect("opinions.db")

rows = list(csv.DictReader(open("triage/text-missing-measured-2026-06-09.tsv"), delimiter="\t"))
by_oid = {}
for r in rows:
    by_oid.setdefault(int(r["oid"]), []).append(r)
work = {o: rs for o, rs in by_oid.items() if any(x["class"] == "SUBSTANTIVE" for x in rs)}

def marker_nums(text):
    return [int(m.group(1)) for m in MARK.finditer(text)]

def try_reextract(cur, pdf_text):
    mp = ANCHOR.search(cur); mb = ANCHOR.search(pdf_text)
    if not mp or not mb:
        return None, "no-anchor"
    if re.search(r"(?m)^## ", cur[mp.start():]):
        return None, "stitched-sections"
    new = cur[:mp.start()].rstrip() + "\n\n" + pdf_text[mb.start():].strip() + "\n"
    if any(c in new for c in ART):
        return None, "artifacts-remain"
    nums = marker_nums(new)
    if not nums or nums != list(range(1, max(nums) + 1)):
        return None, "seq-gap"
    cur_nums = set(marker_nums(cur))
    if not cur_nums <= set(nums):
        return None, f"would-lose ¶{sorted(cur_nums - set(nums))[:5]}"
    if len(new) < 0.9 * len(cur):
        return None, f"shrink {len(cur)}->{len(new)}"
    return new, "ok"

def pdf_para_body(pdf_text, n):
    ptoks = [(m.start(), m.end(), int(m.group(1))) for m in MARK.finditer(pdf_text)]
    for j, (s, e, num) in enumerate(ptoks):
        if num == n:
            end = ptoks[j + 1][0] if j + 1 < len(ptoks) else len(pdf_text)
            return pdf_text[e:end]
    return None

def clean_splice_body(raw):
    # remove page-footer pattern: blank, bare digits, blank, formfeed
    raw = re.sub(r"\n\s*\d+\s*\n\s*\x0c", "\n", raw)
    raw = raw.replace("\x0c", "\n")
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    # trailing bare digit / roman lines are page artifacts or the NEXT
    # paragraph's section heading (already in the DB text)
    while lines and (re.fullmatch(r"\d+", lines[-1]) or re.fullmatch(r"[IVXLC]+", lines[-1])):
        lines.pop()
    return "\n".join(lines)

def splice(cur, n, body, spaced):
    toks = [(m.start(), m.end(), int(m.group(1))) for m in MARK.finditer(cur)]
    nums = {t[2] for t in toks}
    if n in nums:
        return None, "marker already present"
    if not any(p < n for p in nums) or not any(p > n for p in nums):
        return None, "not flanked"
    nxt = min((t for t in toks if t[2] > n), key=lambda t: t[2])
    return cur[:nxt[0]] + f"{spaced}{n}] {body}\n\n" + cur[nxt[0]:], None

n_re = n_sp = n_hold = 0
holds, sp_detail = [], []
for i, (oid, rs) in enumerate(sorted(work.items())):
    cur, sp = conn.execute(
        "SELECT text_content, source_path FROM opinions WHERE id=?", (oid,)).fetchone()
    m = re.search(r"(\d{4})ND(\d+)\.md$", sp or "")
    if not m:
        holds.append((oid, f"unexpected source_path {sp}")); n_hold += 1; continue
    pdf = Path.home() / f"refs/nd/opin/pdfs/{m.group(1)}/{m.group(1)}ND{int(m.group(2))}.pdf"
    if not pdf.exists():
        holds.append((oid, "no PDF")); n_hold += 1; continue
    try:
        pdf_text = extract_text(str(pdf))
    except Exception as ex:
        holds.append((oid, f"pdf error {str(ex)[:40]}")); n_hold += 1; continue

    new, why = try_reextract(cur, pdf_text)
    if new is not None:
        n_re += 1
        if apply:
            conn.execute("UPDATE opinions SET text_content=? WHERE id=?", (new, oid))
            log_change(conn, BATCH, oid, "text_content",
                       f"analyzer body missing ¶s {sorted(int(r['missing_para']) for r in rs if r['class']!='PDF_LACKS_MARKER')}",
                       f"pdfminer full re-extract from {pdf.name}",
                       authority="court PDF re-extraction (pdfminer); old/new marker-set and length gated")
            p = REFS / sp
            if p.parent.exists():
                p.write_text(new, encoding="utf-8")
        continue

    # splice path
    re_why = why
    spaced = "[¶ " if re.search(r"\[¶ \d", cur) else "[¶"
    todo = sorted(int(r["missing_para"]) for r in rs if r["class"] != "PDF_LACKS_MARKER")
    done, failed = [], []
    newcur = cur
    for n in todo:
        raw = pdf_para_body(pdf_text, n)
        if raw is None:
            failed.append((n, "pdf lacks marker")); continue
        body = clean_splice_body(raw)
        if not body:
            failed.append((n, "empty body")); continue
        nx, swhy = splice(newcur, n, body, spaced)
        if nx is None:
            failed.append((n, swhy)); continue
        newcur = nx
        done.append((n, body))
    if not done:
        holds.append((oid, f"reextract: {re_why}; splice: {failed}")); n_hold += 1; continue
    n_sp += 1
    sp_detail.append((oid, re_why, [n for n, _ in done], failed))
    if apply:
        conn.execute("UPDATE opinions SET text_content=? WHERE id=?", (newcur, oid))
        log_change(conn, BATCH, oid, "text_content.splice_para",
                   f"missing ¶s {todo}",
                   " || ".join(f"{spaced}{n}] {b}" for n, b in done),
                   authority=f"paragraphs spliced verbatim from court PDF {pdf.name}"
                             + (f"; unresolved: {failed}" if failed else ""))
        p = REFS / sp
        if p.exists():
            md = p.read_text()
            md2 = md
            for n, b in done:
                nx, _ = splice(md2, n, b, spaced)
                if nx:
                    md2 = nx
            if md2 != md:
                p.write_text(md2)
    if (i + 1) % 50 == 0:
        print(f"...{i+1}/{len(work)}")

print(f"{'APPLIED' if apply else 'DRY RUN'}: full-reextract={n_re} spliced={n_sp} held={n_hold} (of {len(work)})")
if sp_detail:
    print("SPLICE-PATH (reextract reason; spliced ¶s; failures):")
    for oid, why, ok, failed in sp_detail:
        print(f"  oid{oid}: {why}; ¶{ok}" + (f"; FAILED {failed}" if failed else ""))
if holds:
    print("HOLDS:")
    for oid, why in holds:
        print(f"  oid{oid}: {why}")
if apply:
    log_provenance(conn, "substantive-missing", command="triage/fix_substantive_missing_2026-06-09.py --apply",
                   rows_affected=n_re + n_sp,
                   notes=f"batch {BATCH}; {n_re} full pdfminer re-extracts, {n_sp} surgical splices")
    conn.commit()

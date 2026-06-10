"""NO_MARKER_TEXT gaps: our text contains the paragraph but lost its [¶N]
marker. Fix: take the missing ¶'s opening words from the court PDF, find them
uniquely in our gap segment at a paragraph boundary, insert the marker.
Gates: PDF has the marker; opener found exactly once inside the gap segment;
insertion lands at a paragraph-initial position. Dry-run default."""
import csv, re, sqlite3, sys
from pathlib import Path
from pdfminer.high_level import extract_text
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ndcourts_mcp.db import log_change, log_provenance

BATCH = "para-marker-restore-2026-06-09"
REFS = Path.home() / "refs/nd/opin"
MARK = re.compile(r"\[¶\s*(\d+)\]")
apply = "--apply" in sys.argv
conn = sqlite3.connect("opinions.db")
rows = [r for r in csv.DictReader(open("triage/para-gap-classified-2026-06-09.tsv"), delimiter="\t")
        if r["main_cause"] == "NO_MARKER_TEXT"]
n_op = n_fix = 0
held = []
for r in rows:
    oid = int(r["oid"])
    text, sp = conn.execute("SELECT text_content, source_path FROM opinions WHERE id=?", (oid,)).fetchone()
    m = re.search(r"(\d{4})ND(\d+)\.md$", sp or "")
    pdf = Path.home() / f"refs/nd/opin/pdfs/{m.group(1)}/{m.group(1)}ND{int(m.group(2))}.pdf" if m else None
    if not pdf or not pdf.exists():
        held.append((oid, "no PDF")); continue
    try:
        pt = extract_text(str(pdf))
    except Exception:
        held.append((oid, "pdf error")); continue
    ptoks = [(mm.start(), mm.end(), int(mm.group(1))) for mm in MARK.finditer(pt)]
    pmap = {}
    for j, (s, e, num) in enumerate(ptoks):
        end = ptoks[j+1][0] if j+1 < len(ptoks) else len(pt)
        pmap.setdefault(num, pt[e:end].strip())
    toks = [(mm.start(), mm.end(), int(mm.group(1))) for mm in MARK.finditer(text)]
    spaced = "[¶ " if re.search(r"\[¶ \d", text) else "[¶"
    fixes = []
    prev = None
    for s, e, num in toks:
        if prev is not None and prev[2] + 1 < num <= prev[2] + 30:
            seg_start, seg_end = prev[1], s
            for missing in range(prev[2] + 1, num):
                body = pmap.get(missing)
                if not body:
                    continue
                opener = " ".join(body.split()[:6])
                if len(opener) < 15:
                    continue
                # find opener in the gap segment, whitespace-tolerant
                pat = re.compile(r"\s+".join(re.escape(w) for w in opener.split()))
                hits = [h for h in pat.finditer(text, seg_start, seg_end)]
                if len(hits) != 1:
                    continue
                pos = hits[0].start()
                if text[max(0, pos - 2):pos] != "\n\n" and text[max(0, pos - 1):pos] != "\n":
                    continue
                fixes.append((pos, missing))
        if prev is None or num >= prev[2]:
            prev = (s, e, num)
    if not fixes:
        held.append((oid, "opener not located")); continue
    new = text
    for pos, missing in sorted(fixes, reverse=True):
        new = new[:pos] + f"{spaced}{missing}] " + new[pos:]
    n_op += 1; n_fix += len(fixes)
    if apply:
        conn.execute("UPDATE opinions SET text_content=? WHERE id=?", (new, oid))
        log_change(conn, BATCH, oid, "text_content.marker", None,
                   "; ".join(f"{spaced}{x}] inserted" for _, x in fixes),
                   authority="paragraph text present but marker lost; insertion point located by the "
                             "court PDF's ¶-opening words (unique match at paragraph boundary)")
        if sp:
            p = Path(sp) if sp.startswith("/") else REFS / sp
            if p.exists() and p.read_text() == text:
                p.write_text(new)
if apply:
    log_provenance(conn, "para-marker-restore", command="triage/fix_no_marker_text_2026-06-09.py --apply",
                   rows_affected=n_op, notes=f"batch {BATCH}; {n_fix} markers inserted in {n_op} opinions")
    conn.commit()
print(f"{'APPLIED' if apply else 'DRY RUN'}: {n_fix} markers / {n_op} opinions; {len(held)} held")
from collections import Counter
print(Counter(h[1] for h in held))

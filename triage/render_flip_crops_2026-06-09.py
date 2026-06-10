"""Render visual-verification crops for the digit-flip candidates.

For each candidate, locate the PDF-side token via the text layer
(page.search_for), expand the rect, and render a 3x crop PNG. The crop
shows the PRINTED glyphs, independent of the text layer — the arbiter
when DB and text-layer disagree. Output triage/flipverify/<n>_<oid>_p<para>_
<db>-vs-<pdf>.png + manifest.tsv. Read-only."""
import csv, re, sqlite3
from pathlib import Path
import fitz

conn = sqlite3.connect("opinions.db")
out_dir = Path("triage/flipverify")
out_dir.mkdir(exist_ok=True)
cands = list(csv.DictReader(open("triage/digit-flip-candidates-2026-06-09.tsv"), delimiter="\t"))

manifest = []
for idx, r in enumerate(cands):
    oid = int(r["oid"])
    sp = conn.execute("SELECT source_path FROM opinions WHERE id=?", (oid,)).fetchone()[0]
    m = re.search(r"(\d{4})ND(\d+)\.md$", sp)
    pdf = Path.home() / f"refs/nd/opin/pdfs/{m.group(1)}/{m.group(1)}ND{int(m.group(2))}.pdf"
    doc = fitz.open(str(pdf))
    # search string: pdf token plus trailing context words (same line odds)
    post = r["context"].split("]", 1)[1] if "]" in r["context"] else ""
    post_words = re.sub(r"[^A-Za-z0-9 .,$()§¶-]", "", post.replace("...", "")).strip()
    needles = [f'{r["pdf_token"]}{post[:8]}'.strip(), r["pdf_token"]]
    hit = None
    for needle in needles:
        for pno in range(doc.page_count):
            page = doc[pno]
            rects = page.search_for(needle)
            if len(rects) >= 1:
                hit = (pno, rects[0], needle)
                break
        if hit:
            break
    if not hit:
        manifest.append((idx, oid, r["para"], r["db_token"], r["pdf_token"], "NOT_FOUND", ""))
        continue
    pno, rect, needle = hit
    page = doc[pno]
    clip = fitz.Rect(max(0, rect.x0 - 170), max(0, rect.y0 - 18),
                     min(page.rect.x1, rect.x1 + 170), min(page.rect.y1, rect.y1 + 18))
    pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), clip=clip)
    fn = f"{idx:02d}_{oid}_p{r['para']}_{r['db_token']}-vs-{r['pdf_token']}.png"
    pix.save(str(out_dir / fn))
    manifest.append((idx, oid, r["para"], r["db_token"], r["pdf_token"], "RENDERED", fn))

w = csv.writer(open(out_dir / "manifest.tsv", "w"), delimiter="\t", lineterminator="\n")
w.writerow(["idx", "oid", "para", "db_token", "pdf_token", "status", "file"])
w.writerows(manifest)
from collections import Counter
print(Counter(m[5] for m in manifest))

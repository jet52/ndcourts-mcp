"""Fix OCR-mangled ¶ markers found by gap classification ([IT n], [1n], [f n],
[IIn], [¶'n], [t n], [$\\P n$], bare [n], ...). Gate: the token must contain
EXACTLY the missing number, sit between the gap's flanking markers, and for
bare-digit tokens be paragraph-initial and outside footnote context."""
import csv, re, sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ndcourts_mcp.db import log_change, log_provenance

BATCH = "para-marker-ocr-variants-2026-06-09"
REFS = Path.home() / "refs/nd/opin"
MARK = re.compile(r"\[¶\s*(\d+)\]")
apply = "--apply" in sys.argv
conn = sqlite3.connect("opinions.db")
oids = sorted({int(r["oid"]) for r in csv.DictReader(open("triage/para-gap-classified-2026-06-09.tsv"), delimiter="\t")
               if "CORRUPT_TOKEN" in r["main_cause"] + r["gap_detail"]})
n_op = n_fix = 0
samples = []
for oid in oids:
    text, sp = conn.execute("SELECT text_content, source_path FROM opinions WHERE id=?", (oid,)).fetchone()
    toks = [(m.start(), m.end(), int(m.group(1))) for m in MARK.finditer(text)]
    spaced = "[¶ " if re.search(r"\[¶ \d", text) else "[¶"
    fixes = []
    prev = None
    for s, e, num in toks:
        if prev is not None and prev[2] + 1 < num <= prev[2] + 30:
            seg_start = prev[1]
            seg = text[seg_start:s]
            for missing in range(prev[2] + 1, num):
                pat = re.compile(r"\[[^\]\n]{0,8}?" + str(missing) + r"[^\]\n0-9]{0,4}\]")
                for c in pat.finditer(seg):
                    tok = c.group()
                    if re.fullmatch(r"\[¶\s*\d+\]", tok):
                        continue  # already clean
                    if re.search(r"\d", tok.replace(str(missing), "", 1)):
                        continue  # other digits present — not this marker
                    abs_s = seg_start + c.start()
                    if re.fullmatch(r"\[\s*%d\s*\]" % missing, tok):
                        # bare [n]: must be paragraph-initial, not footnote context
                        if text[max(0, abs_s - 2):abs_s] != "\n\n":
                            continue
                        ctx = text[max(0, abs_s - 250):abs_s]
                        if "NOTES" in ctx or "Footnote" in ctx or "footnote" in ctx:
                            continue
                    fixes.append((abs_s, seg_start + c.end(), tok, f"{spaced}{missing}]"))
                    break
                else:
                    continue
                break
        if prev is None or num >= prev[2]:
            prev = (s, e, num)
    if not fixes:
        continue
    new = text
    for s, e, bad, good in sorted(fixes, reverse=True):
        new = new[:s] + good + new[e:]
    n_op += 1; n_fix += len(fixes)
    if len(samples) < 12:
        samples.append(f"oid{oid}: " + ", ".join(f"{b!r}->{g}" for _, _, b, g in fixes[:3]))
    if apply:
        conn.execute("UPDATE opinions SET text_content=? WHERE id=?", (new, oid))
        log_change(conn, BATCH, oid, "text_content.marker",
                   "; ".join(b for _, _, b, _ in fixes), "; ".join(g for _, _, _, g in fixes),
                   authority="OCR-mangled ¶ marker; token holds exactly the missing number between "
                             "the gap's flanking markers (footnote-guarded for bare digits)")
        if sp:
            p = Path(sp) if sp.startswith("/") else REFS / sp
            if p.exists():
                md = p.read_text(); md2 = md
                for _, _, bad, good in fixes:
                    md2 = md2.replace(bad, good, 1)
                if md2 != md:
                    p.write_text(md2)
for s in samples: print("  ", s)
print(f"{'APPLIED' if apply else 'DRY RUN'}: {n_fix} markers in {n_op} opinions")
if apply:
    log_provenance(conn, "para-marker-ocr-variants", command="triage/fix_marker_variants_2026-06-09.py --apply",
                   rows_affected=n_op, notes=f"batch {BATCH}; {n_fix} OCR-mangled markers recovered (gap-gated)")
    conn.commit()

"""Fix ¶ markers OCR'd as letters: '[IF n]', '[lf n]', '[1f n]' -> the document's
own marker style ('[¶n]' or '[¶ n]'). Gate: the recovered number must fill a gap
in (or extend) the existing [¶N] sequence. Dry-run default."""
import re, sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ndcourts_mcp.db import log_change, log_provenance

BATCH = "para-marker-ocr-letters-2026-06-09"
REFS = Path.home() / "refs/nd/opin"
BAD = re.compile(r"\[(?:IF|lf|1f|If)\s*(\d+)\]")
GOOD = re.compile(r"\[¶\s*(\d+)\]")
apply = "--apply" in sys.argv
conn = sqlite3.connect("opinions.db")
n_op = n_fix = 0
held = []
for oid, name, date, text in conn.execute(
    "SELECT id, case_name, date_filed, text_content FROM opinions WHERE "
    "text_content GLOB '*[[]IF [0-9]*' OR text_content GLOB '*[[]IF[0-9]*' "
    "OR text_content GLOB '*[[]lf [0-9]*' OR text_content GLOB '*[[]1f [0-9]*' OR text_content GLOB '*[[]If [0-9]*'"):
    good_nums = [int(m) for m in GOOD.findall(text)]
    if not good_nums:
        held.append((oid, name, "no [¶N] markers at all")); continue
    spaced = "[¶ " if re.search(r"\[¶ \d", text) else "[¶"
    expected = set(range(1, max(good_nums) + 12)) - set(good_nums)
    new, fixes = text, []
    for m in BAD.finditer(text):
        num = int(m.group(1))
        if num in expected and num not in good_nums:
            fixes.append((m.group(0), f"{spaced}{num}]"))
        else:
            held.append((oid, name, f"{m.group(0)} doesn't fill a gap (max ¶{max(good_nums)})"))
    if not fixes:
        continue
    for bad, good in fixes:
        new = new.replace(bad, good, 1)
    n_op += 1; n_fix += len(fixes)
    print(f"oid{oid} {name[:36]} ({date}): " + ", ".join(f"{b}->{g}" for b, g in fixes))
    if apply:
        conn.execute("UPDATE opinions SET text_content=? WHERE id=?", (new, oid))
        log_change(conn, BATCH, oid, "text_content.marker",
                   "; ".join(b for b, g in fixes), "; ".join(g for b, g in fixes),
                   authority="¶ marker OCR'd as letters; recovered number fills the [¶N] sequence gap")
        sp = conn.execute("SELECT source_path FROM opinions WHERE id=?", (oid,)).fetchone()[0]
        if sp:
            p = Path(sp) if sp.startswith("/") else REFS / sp
            if p.exists():
                md = p.read_text(); md2 = md
                for bad, good in fixes:
                    md2 = md2.replace(bad, good, 1)
                if md2 != md:
                    p.write_text(md2)
if apply:
    log_provenance(conn, "para-marker-ocr-letters", command="triage/fix_if_markers_2026-06-09.py --apply",
                   rows_affected=n_op, notes=f"batch {BATCH}; {n_fix} markers in {n_op} opinions")
    conn.commit()
print(f"\n{'APPLIED' if apply else 'DRY RUN'}: {n_fix} markers / {n_op} opinions; {len(held)} held:")
for h in held: print("  ", h)

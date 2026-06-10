"""Drop the appended OCR duplicate copy from stored-twice opinions.

Structure (verified): frontmatter + '# Title' header + '## Opinion' #1 +
CLEAN copy (contiguous [¶1..N], zero letter-OCR markers) + '## Opinion' #2 +
OCR copy (star pagination, [If N] markers). Surgery: truncate at the second
'## Opinion'. Gates: exactly 2 headers; clean copy contiguous 1..N; N == the
highest marker anywhere in the doc; zero bad markers in the kept copy.
Changelog stores the full old text (revertible). Dry-run default."""
import re, sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ndcourts_mcp.db import log_change, log_provenance

BATCH = "dedup-storedtwice-2026-06-09"
REFS = Path.home() / "refs/nd/opin"
OIDS = [12344,12536,12564,12608,12634,12669,12684,12734,12970,13360,13367,13538,
        14091,14511,14544,14657,14897,14951,15155,15171,16262,16880,16963]
MARK = re.compile(r"\[¶\s*(\d+)\]")
BADMARK = re.compile(r"\[(?:IF|If|lf|1f)\s*(\d+)\]")
apply = "--apply" in sys.argv
conn = sqlite3.connect("opinions.db")
n = 0
for oid in OIDS:
    text, sp, name = conn.execute(
        "SELECT text_content, source_path, case_name FROM opinions WHERE id=?", (oid,)).fetchone()
    hdrs = [m.start() for m in re.finditer(r"(?m)^## Opinion", text)]
    if len(hdrs) != 2:
        print(f"oid{oid}: {len(hdrs)} '## Opinion' headers — SKIP"); continue
    keep, drop = text[:hdrs[1]].rstrip() + "\n", text[hdrs[1]:]
    knums = [int(x) for x in MARK.findall(keep)]
    all_nums = [int(x) for x in MARK.findall(text)] + [int(x) for x in BADMARK.findall(text)]
    ok_contig = knums == list(range(1, max(knums) + 1)) if knums else False
    ok_max = max(knums) == max(all_nums) if knums else False
    ok_clean = not BADMARK.search(keep)
    if not (ok_contig and ok_max and ok_clean):
        print(f"oid{oid}: GATE FAIL contig={ok_contig} max={ok_max} clean={ok_clean} "
              f"(kept ¶1..{max(knums) if knums else 0}, doc max {max(all_nums)})")
        continue
    print(f"oid{oid} {name[:40]}: keep {len(keep)}ch ¶1..{max(knums)}, drop {len(drop)}ch OCR copy")
    if apply:
        conn.execute("UPDATE opinions SET text_content=? WHERE id=?", (keep, oid))
        log_change(conn, BATCH, oid, "text_content", text,
                   f"dropped appended OCR duplicate copy ({len(drop)} chars after the 2nd '## Opinion'); "
                   f"kept clean copy ¶1..{max(knums)}",
                   authority="opinion body stored twice (clean analyzer copy + CL/NW2d OCR copy with star "
                             "pagination and letter-OCR'd ¶ markers); 13240-Johnson class")
        if sp:
            p = Path(sp) if sp.startswith("/") else REFS / sp
            if p.exists() and p.read_text() == text:
                p.write_text(keep)
        n += 1
if apply:
    log_provenance(conn, "dedup-storedtwice", command="triage/dedup_storedtwice_2026-06-09.py --apply",
                   rows_affected=n, notes=f"batch {BATCH}; {n} duplicate OCR copies dropped")
    conn.commit()
print(f"\n{'APPLIED' if apply else 'DRY RUN'}: {n}")

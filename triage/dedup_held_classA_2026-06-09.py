"""Class A of the 41 held: copy1 contiguous 1..N; copy2's out-of-range marker
numbers must each be a 1-digit edit of an in-range number (digit flips);
jaccard >= 0.55. Same drop-copy2 surgery."""
import re, sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ndcourts_mcp.db import log_change, log_provenance
from ndcourts_mcp.multisource_diff import normalize_words, shingles, jaccard

BATCH = "dedup-storedtwice-2026-06-09"
REFS = Path.home() / "refs/nd/opin"
MARK = re.compile(r"\[¶\s*(\d+)\]")
BAD = re.compile(r"\[(?:IF|If|lf|1f)\s*(\d+)\]")
OIDS = [12360,12409,12752,13172,13368,13785,13975,14100,14115,14381,14841,14955,
        15020,15043,15270,15824,15926,16069,16077,16124,16188,16221,16245,
        16257,16462,16554,16795]
def flip_ok(n, top):
    s = str(n)
    for i in range(len(s)):
        for d in "0123456789":
            if d != s[i]:
                v = int(s[:i] + d + s[i+1:])
                if 1 <= v <= top:
                    return True
    return len(s) > 1 and 1 <= int(s[1:]) <= top  # dropped/added digit
apply = "--apply" in sys.argv
conn = sqlite3.connect("opinions.db")
n = 0
for oid in OIDS:
    text, sp, name = conn.execute(
        "SELECT text_content, source_path, case_name FROM opinions WHERE id=?", (oid,)).fetchone()
    hdrs = [m.start() for m in re.finditer(r"(?m)^## Opinion", text)]
    if len(hdrs) != 2:
        print(f"oid{oid}: hdrs={len(hdrs)} SKIP"); continue
    keep, drop = text[:hdrs[1]].rstrip() + "\n", text[hdrs[1]:]
    k = [int(x) for x in MARK.findall(keep)]
    if not k or k != list(range(1, max(k) + 1)) or BAD.search(keep):
        print(f"oid{oid}: copy1 not clean-contiguous SKIP"); continue
    top = max(k)
    excess = [x for x in (int(y) for y in MARK.findall(drop)) if x > top]
    if not all(flip_ok(x, top) for x in excess):
        print(f"oid{oid}: unexplainable excess markers {excess} SKIP"); continue
    j = jaccard(shingles(normalize_words(keep[hdrs[0]:])), shingles(normalize_words(drop)))
    if j < 0.55:
        print(f"oid{oid}: jaccard {j:.2f} SKIP"); continue
    print(f"oid{oid} {name[:36]}: keep ¶1..{top}, drop {len(drop)}ch (j={j:.2f}, excess={excess})")
    n += 1
    if apply:
        conn.execute("UPDATE opinions SET text_content=? WHERE id=?", (keep, oid))
        log_change(conn, BATCH, oid, "text_content", text,
                   f"dropped appended OCR duplicate ({len(drop)} chars); kept clean copy ¶1..{top}; "
                   f"jaccard {j:.2f}; copy2 excess markers {excess} are digit flips",
                   authority="stored-twice class, held-queue A: copy2 marker numbers digit-flipped above copy1 max")
        if sp:
            p = Path(sp) if sp.startswith("/") else REFS / sp
            if p.exists() and p.read_text() == text:
                p.write_text(keep)
if apply:
    log_provenance(conn, "dedup-storedtwice-heldA", command="triage/dedup_held_classA_2026-06-09.py --apply",
                   rows_affected=n, notes=f"batch {BATCH}; held-queue class A; {n} dropped")
    conn.commit()
print(f"\n{'APPLIED' if apply else 'DRY RUN'}: {n}/{len(OIDS)}")

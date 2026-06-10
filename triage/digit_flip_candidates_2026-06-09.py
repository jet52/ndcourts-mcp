"""Pass 2 over the digit-compare mismatches: isolate genuine digit-flip
candidates from formatting noise (star pagination, footnote markers,
footnote placement).

A candidate is a pair of same-length digit tokens (one in the DB ¶, one in
the PDF ¶) differing in EXACTLY one digit position, whose surrounding
non-digit context matches after whitespace normalization (±25 chars). The
context match makes this high-precision: star pages and footnote digits
have no matching context on the other side.

Output: triage/digit-flip-candidates-2026-06-09.tsv (oid, cite, para,
db_token, pdf_token, context). Read-only."""
import csv, re, sqlite3
from pathlib import Path
from pdfminer.high_level import extract_text

conn = sqlite3.connect("opinions.db")
MARK = re.compile(r"\[\s*¶\s*(\d+)\s*\]")
DIGITS = re.compile(r"\d+")

mism = list(csv.DictReader(open("triage/digit-compare-2026-06-09.tsv"), delimiter="\t"))
by_oid = {}
for r in mism:
    by_oid.setdefault(int(r["oid"]), []).append(int(r["para"]))

def para_map(text):
    toks = [(m.start(), m.end(), int(m.group(1))) for m in MARK.finditer(text)]
    out = {}
    for j, (s, e, n) in enumerate(toks):
        end = toks[j + 1][0] if j + 1 < len(toks) else len(text)
        out.setdefault(n, text[e:end])
    return out

def norm(s):
    return re.sub(r"\s+", " ", s)

def tokens_with_context(body, w=25):
    return [(m.group(), norm(body[max(0, m.start()-w):m.start()]),
             norm(body[m.end():m.end()+w]))
            for m in DIGITS.finditer(body)]

def flip(a, b):
    return len(a) == len(b) and sum(x != y for x, y in zip(a, b)) == 1

out = []
for i, (oid, paras) in enumerate(sorted(by_oid.items())):
    text, sp = conn.execute(
        "SELECT text_content, source_path FROM opinions WHERE id=?", (oid,)).fetchone()
    m = re.search(r"(\d{4})ND(\d+)\.md$", sp or "")
    pdf = Path.home() / f"refs/nd/opin/pdfs/{m.group(1)}/{m.group(1)}ND{int(m.group(2))}.pdf"
    try:
        pt = extract_text(str(pdf))
    except Exception:
        continue
    pt = re.sub(r"\n\s*\d+\s*\n\s*\x0c", "\n", pt)
    db_map, pdf_map = para_map(text), para_map(pt)
    for n in paras:
        if n not in db_map or n not in pdf_map:
            continue
        dt = tokens_with_context(db_map[n])
        pt_toks = tokens_with_context(pdf_map[n])
        pdf_set = {t[0] for t in pt_toks}
        for tok, pre, post in dt:
            if tok in pdf_set:
                continue  # same token exists somewhere in the PDF ¶
            for ptok, ppre, ppost in pt_toks:
                if ptok in {t[0] for t in dt}:
                    continue
                if flip(tok, ptok) and (pre[-12:] == ppre[-12:] or post[:12] == ppost[:12]):
                    out.append((oid, m.group(0)[:-3], n, tok, ptok,
                                f"...{pre[-30:]}[{tok}->{ptok}]{post[:30]}..."))
                    break
    if (i + 1) % 50 == 0:
        print(f"...{i+1}/{len(by_oid)}")

w = csv.writer(open("triage/digit-flip-candidates-2026-06-09.tsv", "w"), delimiter="\t", lineterminator="\n")
w.writerow(["oid", "cite", "para", "db_token", "pdf_token", "context"])
w.writerows(out)
print(f"{len(out)} flip candidates in {len({o[0] for o in out})} opinions "
      f"-> triage/digit-flip-candidates-2026-06-09.tsv")

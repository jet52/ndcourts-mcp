"""Triage the 59 pinpoint_range flags: pull citing-text context around each
cite and compare the cited-as name against the DB row holding that neutral
cite. Read-only."""
import csv, re, sqlite3, sys

conn = sqlite3.connect("opinions.db")
rows = list(csv.DictReader(open("triage/audit-pinpoint-range-2026-06-09.tsv"), delimiter="\t"))

def text(oid):
    r = conn.execute("SELECT text_content FROM opinions WHERE id=?", (oid,)).fetchone()
    return r[0] if r else ""

def meta(oid):
    return conn.execute("SELECT case_name, date_filed FROM opinions WHERE id=?", (oid,)).fetchone()

out = []
for r in rows:
    citing, cite, cited = int(r["citing_oid"]), r["cited_neutral_cite"], int(r["cited_oid"])
    t = text(citing)
    ctxs = []
    for m in re.finditer(re.escape(cite), t):
        a = max(0, m.start() - 110)
        ctx = " ".join(t[a:m.end() + 30].split())
        ctxs.append(ctx)
    name, date = meta(cited)
    cname, cdate = meta(citing)
    out.append((citing, cname, cite, cited, name, date, r["pincite_para"], r["max_marker_in_db"], " ||| ".join(ctxs[:2])))

w = csv.writer(open("triage/pinpoint-context-2026-06-09.tsv", "w"), delimiter="\t", lineterminator="\n")
w.writerow(["citing_oid","citing_name","cite","cited_oid","cited_row_name","cited_date","pin","max","citing_context"])
w.writerows(out)
print(f"{len(out)} rows -> triage/pinpoint-context-2026-06-09.tsv")

#!/usr/bin/env python3
"""Recover empty docket_number fields (priority TODO 2026-05-27).

Three changelog-logged operations, in order:
  1. MODERN 1997+ : read the ND-neutral markdown file, extract the caption
     docket (No./Nos. YYYYNNNN), year-validate vs date_filed. Store bare
     8-digit; consolidated cases comma-joined.
  2. GAP 1953-96  : where the court-archive filename docket == the body
     Civ./Cr. number (thousands-comma tolerant), store native 'Civ. NNNN' /
     'Cr. NNNN'. 11 Westlaw-sourced admin orders deferred (no docket).
  3. NORMALIZE    : every still-blank docket_number ('') -> NULL.

Authoritative source = the published opinion caption (markdown is court-PDF
derived). Run after a DB snapshot. Idempotent on re-run (only touches
empties / blank strings).
"""
import sqlite3, re, os, sys, datetime

DB = "opinions.db"
REFS = os.path.expanduser("~/refs/nd/opin")
BATCH = "recover-dockets-2026-05-27"
TS = datetime.datetime.now().isoformat(timespec="seconds")
APPLY = "--apply" in sys.argv

db = sqlite3.connect(DB)
c = db.cursor()

def log(oid, old, new, authority):
    c.execute("""INSERT INTO changelog(timestamp,batch,opinion_id,field,old_value,new_value,authority)
                 VALUES(?,?,?,?,?,?,?)""", (TS, BATCH, oid, "docket_number", old, new, authority))

def setdocket(oid, old, new, authority):
    if APPLY:
        c.execute("UPDATE opinions SET docket_number=? WHERE id=?", (new, oid))
        log(oid, old, new, authority)

# ---------- 1. MODERN 1997+ ----------
ncre = re.compile(r'(\d{4})\s+ND\s+(\d+)')
NUM = r'\d{8}'
cap = re.compile(r'\bNos?\.?\s*((?:%s)(?:\s*(?:&|,|;|and)\s*(?:No\.?\s*)?%s)*)' % (NUM, NUM))

def mdpath(oid):
    r = c.execute("""SELECT citation FROM citations WHERE opinion_id=? AND reporter='ND-neutral'
                     ORDER BY is_primary DESC LIMIT 1""", (oid,)).fetchone()
    if not r:
        return None
    m = ncre.search(r[0])
    if not m:
        return None
    y, n = m.group(1), m.group(2)
    return os.path.join(REFS, "markdown", y, f"{y}ND{n}.md")

modern = list(c.execute("""SELECT id,date_filed,docket_number FROM opinions
    WHERE (docket_number IS NULL OR trim(docket_number)='') AND date_filed>='1997-01-01'"""))
m_single = m_multi = m_fail = 0
for oid, df, old in modern:
    fy = int(df[:4]); p = mdpath(oid)
    if not p or not os.path.exists(p):
        m_fail += 1; print("MODERN-FAIL nofile", oid, df); continue
    txt = open(p, encoding="utf-8", errors="replace").read()
    m = cap.search(txt[:1500]) or cap.search(txt)
    if not m:
        m_fail += 1; print("MODERN-FAIL nomatch", oid, df); continue
    ds = re.findall(NUM, m.group(1))
    if not all(fy - 7 <= int(d[:4]) <= fy for d in ds):
        m_fail += 1; print("MODERN-FAIL yearbad", oid, df, ds); continue
    new = ", ".join(ds)
    setdocket(oid, old, new, "recovered from ND-neutral markdown caption; year-validated vs date_filed")
    if len(ds) == 1: m_single += 1
    else: m_multi += 1

# ---------- 2. GAP 1953-96 ----------
pathdig = re.compile(r'/(\d{3,7})\.(?:htm|html)$')
bodyre = re.compile(r'\b(Civil|Criminal|Civ|Cr|Crim)\.?\s*(?:No\.?|Nos\.?)?\s*([\d,]{2,8})', re.I)
TYPEMAP = {"civil": "Civ.", "civ": "Civ.", "criminal": "Cr.", "crim": "Cr.", "cr": "Cr."}

gap = list(c.execute("""SELECT id,date_filed,docket_number,source_path,text_content FROM opinions
    WHERE (docket_number IS NULL OR trim(docket_number)='')
    AND date_filed BETWEEN '1953-01-01' AND '1996-12-31'"""))
g_ok = g_defer = 0
for oid, df, old, sp, txt in gap:
    pm = pathdig.search(sp or "")
    bm = bodyre.search((txt or "")[:2500])
    if not (pm and bm):
        g_defer += 1; continue
    pnum = pm.group(1)
    bnum = bm.group(2).replace(",", "")
    if pnum != bnum:
        g_defer += 1; print("GAP-DEFER mismatch", oid, df, pnum, bnum); continue
    typ = TYPEMAP.get(bm.group(1).lower().rstrip("."), "Civ.")
    new = f"{typ} {pnum}"
    setdocket(oid, old, new, "recovered: court-archive filename docket == body caption No.; agree")
    g_ok += 1

# ---------- 3. NORMALIZE blank -> NULL ----------
blanks = c.execute("SELECT COUNT(*) FROM opinions WHERE docket_number=''").fetchone()[0]
if APPLY:
    # separate cursor: logging via c would invalidate the iterating SELECT
    rc = db.cursor()
    for (oid,) in rc.execute("SELECT id FROM opinions WHERE docket_number=''"):
        log(oid, "", None, "normalize empty-string docket to NULL")
    c.execute("UPDATE opinions SET docket_number=NULL WHERE docket_number=''")

print(f"\nMODERN: {m_single} single + {m_multi} consolidated recovered, {m_fail} fail")
print(f"GAP:    {g_ok} recovered, {g_defer} deferred")
print(f"NORMALIZE: {blanks} blank-string -> NULL")
print(f"APPLY={APPLY}")
if APPLY:
    db.commit()
    print("committed.")

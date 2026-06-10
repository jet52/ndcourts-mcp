"""Build the DB_NO_PARALLEL backfill candidate list.

Each row: citing opinion(s) print 'B_neutral, ..., P_nw' where B resolves to an
opinion with NO N.W. parallel and P resolves to nothing. Group by (B, P), count
distinct citing witnesses, and gate:
  - live re-check: B still lacks an N.W. parallel; P still unresolved
  - CONFLICT: B claimed with 2+ different P's -> hold all
  - SHARED: P claimed by 2+ B's (legit for summary-disposition table pages) -> mark
  - volume-window: B.date_filed within the corpus date window of P's volume
AUTO = >=2 witnesses, no conflict, window-ok. Everything else HOLD. Read-only.
"""
import csv, re, sqlite3, statistics
from collections import defaultdict

conn = sqlite3.connect("opinions.db")
rows = [r for r in csv.DictReader(open("triage/parallel-pair-classified-2026-06-09.tsv"), delimiter="\t")
        if r["class"] == "DB_NO_PARALLEL"]

groups = defaultdict(set)   # (B, P) -> set of citing oids
ctx = {}
for r in rows:
    key = (r["nd_cite"], r["nw_cite"])
    groups[key].add(r["citing_oid"])
    ctx.setdefault(key, r["context"])

# live helpers
def b_row(neutral):
    return conn.execute(
        "SELECT o.id, o.case_name, o.date_filed FROM opinions o JOIN citations c "
        "ON c.opinion_id=o.id WHERE c.citation=?", (neutral,)).fetchone()

def has_nw(oid):
    return conn.execute(
        "SELECT 1 FROM citations WHERE opinion_id=? AND citation LIKE '%N.W.%' LIMIT 1",
        (oid,)).fetchone() is not None

def p_resolved(p):
    return conn.execute("SELECT 1 FROM citations WHERE citation=? LIMIT 1", (p,)).fetchone() is not None

# volume date windows from existing citations
vol_dates = defaultdict(list)
for cite, date in conn.execute(
    "SELECT c.citation, o.date_filed FROM citations c JOIN opinions o ON o.id=c.opinion_id "
    "WHERE c.citation LIKE '%N.W.2d%' OR c.citation LIKE '%N.W.3d%'"):
    m = re.match(r"(\d+) N\.W\.([23])d", cite)
    if m and date:
        vol_dates[(m.group(1), m.group(2))].append(date)
vol_win = {}
for k, ds in vol_dates.items():
    ds.sort()
    vol_win[k] = (ds[0], ds[-1], len(ds))

def window_check(p, date):
    m = re.match(r"(\d+) N\.W\.([23])d", p)
    if not m or (m.group(1), m.group(2)) not in vol_win:
        return "NO_WINDOW"
    lo, hi, n = vol_win[(m.group(1), m.group(2))]
    import datetime
    d = datetime.date.fromisoformat
    if d(lo) - datetime.timedelta(days=120) <= d(date) <= d(hi) + datetime.timedelta(days=120):
        return "OK"
    return f"OUT[{lo}..{hi}]"

# conflicts
b_to_ps = defaultdict(set); p_to_bs = defaultdict(set)
for (B, P) in groups:
    b_to_ps[B].add(P); p_to_bs[P].add(B)

out = []
for (B, P), wits in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    br = b_row(B)
    if not br:
        out.append((B, "", "", P, len(wits), "GONE", "", "")); continue
    oid, name, date = br
    status, notes = "AUTO", []
    if has_nw(oid):
        status = "SKIP_HAS_NW"
    elif p_resolved(P):
        status = "SKIP_P_RESOLVED"
    else:
        if len(b_to_ps[B]) > 1:
            status = "HOLD"; notes.append(f"CONFLICT:{sorted(b_to_ps[B])}")
        w = window_check(P, date)
        if w != "OK":
            status = "HOLD"; notes.append(f"WINDOW:{w}")
        if len(p_to_bs[P]) > 1:
            notes.append(f"SHARED:{sorted(p_to_bs[P])}")
        if status == "AUTO" and len(wits) < 2:
            status = "HOLD_SINGLE"
    out.append((B, oid, name[:40], P, len(wits), status, ";".join(notes), ctx[(B, P)][:100]))

w = csv.writer(open("triage/backfill-parallel-candidates-2026-06-09.tsv", "w"), delimiter="\t", lineterminator="\n")
w.writerow(["neutral","oid","case_name","nw_cite","witnesses","status","notes","sample_context"])
w.writerows(out)
from collections import Counter
print(Counter(o[5] for o in out))
print("AUTO with SHARED note:", sum(1 for o in out if o[5]=="AUTO" and "SHARED" in o[6]))

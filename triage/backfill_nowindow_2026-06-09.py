"""Second AUTO tier: NO_WINDOW holds (whole N.W. volume absent from our
citations). Gate by volume-sequence interpolation: nearest known volumes
below/above bracket the candidate's date. >=2 witnesses, no conflict."""
import csv, datetime, re, sqlite3, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ndcourts_mcp.db import log_change, log_provenance

BATCH = "parallel-backfill-witnessed-2026-06-09"   # same batch, second tier
apply = "--apply" in sys.argv
conn = sqlite3.connect("opinions.db")

vol_dates = defaultdict(list)
for cite, date in conn.execute(
    "SELECT c.citation, o.date_filed FROM citations c JOIN opinions o ON o.id=c.opinion_id "
    "WHERE c.citation LIKE '%N.W.2d%' OR c.citation LIKE '%N.W.3d%'"):
    m = re.match(r"(\d+) N\.W\.([23])d", cite)
    if m and date:
        vol_dates[(m.group(2), int(m.group(1)))].append(date)
win = {k: (min(v), max(v)) for k, v in vol_dates.items() if len(v) >= 3}

def interp_ok(series, vol, date):
    lower = [k for k in win if k[0] == series and k[1] < vol]
    upper = [k for k in win if k[0] == series and k[1] > vol]
    d = datetime.date.fromisoformat
    lo = max(lower)[1] if lower else None
    hi = min(upper)[1] if upper else None
    lo_d = d(win[max(lower)][0]) - datetime.timedelta(days=180) if lower else None
    hi_d = d(win[min(upper)][1]) + datetime.timedelta(days=180) if upper else None
    dd = d(date)
    if lo_d and dd < lo_d: return False, f"date<{lo_d} (vol {lo} window)"
    if hi_d and dd > hi_d: return False, f"date>{hi_d} (vol {hi} window)"
    return True, f"brackets vol{lo}..vol{hi}"
n = 0
held = []
rows = [r for r in csv.DictReader(open("triage/backfill-parallel-candidates-2026-06-09.tsv"), delimiter="\t")
        if r["status"] == "HOLD" and "NO_WINDOW" in r["notes"] and "CONFLICT" not in r["notes"] and int(r["witnesses"]) >= 2]
print(f"{len(rows)} NO_WINDOW >=2-witness candidates")
for r in rows:
    oid, P = int(r["oid"]), r["nw_cite"]
    m = re.match(r"(\d+) N\.W\.([23])d", P)
    date = conn.execute("SELECT date_filed FROM opinions WHERE id=?", (oid,)).fetchone()[0]
    ok, why = interp_ok(m.group(2), int(m.group(1)), date)
    if not ok:
        held.append((r["neutral"], P, r["witnesses"], why)); continue
    if conn.execute("SELECT 1 FROM citations WHERE opinion_id=? AND (citation=? OR citation LIKE '%N.W.%')", (oid, P)).fetchone():
        continue
    if apply:
        conn.execute("INSERT INTO citations (opinion_id, citation, reporter, is_primary) VALUES (?,?,?,0)",
                     (oid, P, "NW3d" if "3d" in P else "NW2d"))
        shared = "SHARED" in r["notes"]
        log_change(conn, BATCH, oid, "citation.add", None, P,
                   authority=f"{r['witnesses']} independent court opinions print '{r['neutral']}, ..., {P}'; "
                             f"volume-sequence interpolation {why}"
                             + ("; shared summary-disposition table page" if shared else ""))
    n += 1
if apply:
    log_provenance(conn, "parallel-backfill-nowindow",
                   command="triage/backfill_nowindow_2026-06-09.py --apply",
                   rows_affected=n, notes=f"batch {BATCH} tier 2 (NO_WINDOW, interpolation-gated); {n} adds")
    conn.commit()
print(f"{'APPLIED' if apply else 'DRY RUN'}: {n} adds; {len(held)} interpolation-failed:")
for h in held[:10]: print("  ", h)

"""Apply the AUTO tier of the DB_NO_PARALLEL backfill: add witness-attested
N.W.2d/3d parallels (>=2 independent citing opinions, volume-window coherent,
no conflicting claim) to opinions that have no N.W. parallel. Additive only;
SHARED = summary-disposition table page (multiple opinions legitimately share
the N.W. page), noted in the authority string."""
import csv, re, sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ndcourts_mcp.db import log_change, log_provenance

BATCH = "parallel-backfill-witnessed-2026-06-09"
apply = "--apply" in sys.argv
conn = sqlite3.connect("opinions.db")
rows = [r for r in csv.DictReader(open("triage/backfill-parallel-candidates-2026-06-09.tsv"), delimiter="\t")
        if r["status"] == "AUTO"]
n = 0
for r in rows:
    oid, P, wit = int(r["oid"]), r["nw_cite"], r["witnesses"]
    if conn.execute("SELECT 1 FROM citations WHERE opinion_id=? AND citation=?", (oid, P)).fetchone():
        continue
    # safety: still no N.W. parallel on the row
    if conn.execute("SELECT 1 FROM citations WHERE opinion_id=? AND citation LIKE '%N.W.%'", (oid,)).fetchone():
        print(f"skip oid{oid}: gained an N.W. cite since build"); continue
    reporter = "NW3d" if "N.W.3d" in P else "NW2d"
    shared = "SHARED" in r["notes"]
    if apply:
        conn.execute("INSERT INTO citations (opinion_id, citation, reporter, is_primary) VALUES (?,?,?,0)",
                     (oid, P, reporter))
        auth = (f"{wit} independent court opinions print '{r['neutral']}, ..., {P}' "
                f"(parallel-pair witness backfill, triage/backfill-parallel-candidates-2026-06-09.tsv)"
                + ("; shared summary-disposition table page" if shared else ""))
        log_change(conn, BATCH, oid, "citation.add", None, P, authority=auth)
    n += 1
if apply:
    log_provenance(conn, "parallel-backfill-witnessed",
                   command="triage/apply_parallel_backfill_2026-06-09.py --apply",
                   rows_affected=n, notes=f"batch {BATCH}; {n} N.W. parallels added (AUTO tier)")
    conn.commit()
print(f"{'APPLIED' if apply else 'DRY RUN'}: {n} adds")

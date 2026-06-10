"""Add witness-attested N.W.2d parallels to 14 opinions that have no N.W.
parallel (class 3, strong one-sided clusters: >=2 independent court opinions
print 'B_cite, ..., P' and zero print the current holder with P). Additive
only — the current holder keeps P pending per-item verification (same-page
sharing is legitimate)."""
import sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ndcourts_mcp.db import log_change, log_provenance

BATCH = "parallel-add-witnessed-2026-06-09"
ADDS = [  # (oid, neutral, parallel, witnesses)
    (18360, "2000 ND 213", "622 N.W.2d 432", 6),
    (14162, "2004 ND 221", "691 N.W.2d 193", 2),
    (18714, "2009 ND 3",   "763 N.W.2d 799", 3),
    (18936, "2013 ND 113", "837 N.W.2d 159", 2),
    (19052, "2014 ND 99",  "859 N.W.2d 929", 2),
    (19143, "2016 ND 118", "881 N.W.2d 256", 2),
    (16963, "2017 ND 159", "897 N.W.2d 326", 3),
    (16972, "2017 ND 169", "898 N.W.2d 406", 12),
    (17422, "2019 ND 69",  "924 N.W.2d 87", 16),
    (19590, "2021 ND 126", "962 N.W.2d 400", 2),
    (17913, "2021 ND 216", "967 N.W.2d 778", 3),
    (17921, "2021 ND 239", "968 N.W.2d 134", 2),
    (18118, "2022 ND 233", "982 N.W.2d 864", 2),
    (18168, "2023 ND 57",  "988 N.W.2d 586", 5),
]
apply = "--apply" in sys.argv
conn = sqlite3.connect("opinions.db")
n = 0
for oid, neutral, par, wit in ADDS:
    exists = conn.execute("SELECT 1 FROM citations WHERE opinion_id=? AND citation=?", (oid, par)).fetchone()
    print(f"oid{oid} {neutral} += {par} ({wit} witnesses){' [exists]' if exists else ''}")
    if exists:
        continue
    if apply:
        conn.execute("INSERT INTO citations (opinion_id, citation, reporter, is_primary) VALUES (?,?,?,0)",
                     (oid, par, "NW2d"))
        log_change(conn, BATCH, oid, "citation.add", None, par,
                   authority=f"{wit} independent court opinions print '{neutral}, ..., {par}' "
                             f"(parallel-pair witness analysis, triage/class3-clusters-2026-06-09.tsv); "
                             f"row had no N.W. parallel")
        n += 1
if apply:
    log_provenance(conn, "parallel-add-witnessed", command="triage/apply_parallel_adds_2026-06-09.py --apply",
                   rows_affected=n, notes=f"batch {BATCH}; {n} witness-attested N.W.2d parallels added")
    conn.commit(); print(f"APPLIED {n}")

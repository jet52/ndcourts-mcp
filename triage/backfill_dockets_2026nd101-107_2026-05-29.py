#!/usr/bin/env python3
"""Backfill docket_number for 2026 ND 101-107.

These 7 opinions were ingested 2026-05-29 from freshly scraped court PDFs (after
the curl_cffi Cloudflare-bypass fix). merge_nd_metadata pulls dockets from
CourtListener cluster JSON, which doesn't exist yet for opinions this new, so
docket_number landed NULL even though the scraped <year>_opinions.json carries
the docket from the published listing.

Authority: ndcourts.gov opinion listing (scraped ~/refs/nd/opin/2026_opinions.json).
Fully revertible: python -m ndcourts_mcp.cleanup revert backfill-dockets-2026nd101-107-2026-05-29
"""
import json
import sqlite3

from ndcourts_mcp.db import DEFAULT_DB_PATH

BATCH = "backfill-dockets-2026nd101-107-2026-05-29"
AUTHORITY = "ndcourts.gov opinion listing (scraped 2026_opinions.json)"
JSON_PATH = "/Users/jerod/refs/nd/opin/2026_opinions.json"
TARGET_CITES = [f"2026 ND {n}" for n in range(101, 108)]

# Map neutral cite -> docket from the scraped listing metadata.
raw = json.load(open(JSON_PATH))
recs = raw if isinstance(raw, list) else list(raw.values())
docket_by_cite = {
    o.get("citation"): (o.get("docket_number") or "").strip()
    for o in recs
    if o.get("citation") in TARGET_CITES
}

c = sqlite3.connect(DEFAULT_DB_PATH)
c.row_factory = sqlite3.Row
updated = 0
for cite in TARGET_CITES:
    docket = docket_by_cite.get(cite)
    if not docket:
        print(f"  SKIP {cite}: no docket in JSON")
        continue
    row = c.execute(
        "SELECT o.id, o.docket_number, o.case_name "
        "FROM opinions o JOIN citations ct ON ct.opinion_id = o.id "
        "WHERE ct.citation = ?",
        (cite,),
    ).fetchone()
    if row is None:
        print(f"  SKIP {cite}: not found in DB")
        continue
    old = row["docket_number"]
    if old not in (None, ""):
        print(f"  SKIP {cite} (oid {row['id']}): already has docket {old!r}")
        continue
    c.execute("UPDATE opinions SET docket_number = ? WHERE id = ?", (docket, row["id"]))
    c.execute(
        "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value, authority) "
        "VALUES (?, ?, 'docket_number', ?, ?, ?)",
        (BATCH, row["id"], old, docket, AUTHORITY),
    )
    updated += 1
    print(f"  SET {cite} (oid {row['id']}, {row['case_name']}): {old!r} -> {docket}")

c.commit()
print(f"\nDone. {updated} dockets backfilled under batch {BATCH}.")

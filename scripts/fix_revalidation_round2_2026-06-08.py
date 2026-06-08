#!/usr/bin/env python3
"""Round-2 re-validation corrections (2026-06-08), conservative subset.

Applies ONLY the findings that survived scrutiny:
  - LIV (art LIV): restore the truncated tail of the enacted text (full §6(d)-(e),
    §7, §8) from sl1939; the stored "[TEXT TRUNCATED ... NOT in source]" note was
    false (the text IS in the session law). art LIV is the Board-of-Higher-Ed
    article the structural backlog (LXXVIII/XCVI/XC) depends on.
  - 13 records (XLIII-LXIII): replace the leaked placeholder authority
    "Amendment ratified undefined" with real session-law provenance, and backfill
    election_date where the session law states the approval/election date.

DELIBERATELY NOT changed:
  - effective_date on any record: the agents' "date mismatch" flags compared the
    session-law APPROVAL date to the stored EFFECTIVE date; the dataset convention
    is effective = approval + 30 days (e.g. amdt #2: 1898-11-08 -> 1898-12-08), so
    the stored effective_dates are correct.
  - #12 (§216): the agent's "substantive" flag was a FALSE POSITIVE from matching a
    later §216 amendment in the wrong volume (sl1911, "Approved Feb 24 1911"). The
    real 1909-proposed/1910-ratified text in sl1909 MATCHES the stored placeholder
    language; stored text is correct.
  - #1 / XXX / XXXVII: early-era findings on multiply-amended sections whose volume
    match is unverified -> deferred to the volume-corrected re-run (action 4).
"""
import json
from pathlib import Path

JSON = Path("/Users/jerod/code/ndcourts-mcp/data/constitution_amendments.json")
doc = json.loads(JSON.read_text())
recs = {r["number"]: r for r in doc["amendments"]}
log = []

# ---- LIV: restore truncated enacted text ----
r = recs["LIV"]; ch = r["changes"][0]
assert "[TEXT TRUNCATED" in ch["text"], "LIV: truncation marker not found"
head = ch["text"].split(" [TEXT TRUNCATED")[0]   # ends "...until the State Board of"
tail = (' Higher Education organizes as provided in Section 6 (a)." The appropriations for all '
"of said institutions shall be contained in one legislative measure.\n\n"
"(e) The said State Board of Higher Education shall have the control of the expenditure of the "
"funds belonging to, and allocated to such institutions and also those appropriated by the "
"legislature, for the institutions of higher education in this State; provided, however, that "
"funds appropriated by the legislature and specifically designated for any one or more of such "
"institutions, shall not be used for any other institution.\n\n"
"§ 7. (a) The State Board of Higher Education shall, as soon as practicable, appoint for a term "
"of not to exceed three (3) years, a State Commissioner of Higher Education, whose principal "
"office shall be at the State Capitol, in the City of Bismarck. Said Commissioner of Higher "
"Education shall be responsible to the State Board of Higher Education and shall be removable by "
"said board for cause.\n"
"(b) The State Commissioner of Higher Education shall be a graduate of some reputable college or "
"university, and who by training and experience is familiar with the problems peculiar to higher "
"education.\n"
"(c) Such Commissioner of Higher Education shall be the chief executive officer of said State "
"Board of Higher Education, and shall perform such duties as shall be prescribed by the board.\n\n"
"§ 8. This constitutional provision shall be self-executing and shall become effective without "
"the necessity of legislative action.")
ch["text"] = head + tail
log.append("LIV art LIV: restored truncated enacted tail (§6(d)-(e), §7, §8) from sl1939")

# ---- authority + election_date backfill (13 records) ----
# (number -> (authority, election_date or None)). effective_date untouched.
BF = {
 "XLIII": ("Article 43; Concurrent Resolution, 1925 Session Laws; approved June 30, 1926, 69,214 to 61,235.", "1926-06-30"),
 "XLIV":  ("Article 44; House Bill No. 341 (Joint Resolution), 1927 Session Laws; approved March 20, 1928, 63,568 to 37,284.", "1928-03-20"),
 "XLV":   ("Article 45; Chapter 97, 1929 Session Laws (Concurrent Resolution); approved June 25, 1930.", "1930-06-25"),
 "XLVI":  ("Article 46; Chapter 98, 1929 Session Laws (Concurrent Resolution); approved June 25, 1930.", "1930-06-25"),
 "XLVII": ("Article 47; submitted by initiative petition; approved November 8, 1932, 134,742 to 99,316.", "1932-11-08"),
 "XLVIII":("Chapter 84 (House Bill No. 216, State Affairs Committee), 1933 Session Laws; Concurrent Resolution amending Section 173 of Article 10.", None),
 "XLIX":  ("Chapter 83 (Senate Concurrent Resolution), 1933 Session Laws.", None),
 "L":     ("Article 50; submitted by Legislature; approved June 28, 1938, 95,700 to 76,051.", "1938-06-28"),
 "LI":    ("Article 51; submitted by initiative petition; approved June 28, 1938, 106,699 to 64,087.", "1938-06-28"),
 "LII":   ("Article 52; submitted by initiative petition; approved June 28, 1938, 86,822 to 78,206.", "1938-06-28"),
 "LIII":  ("Article 53; submitted by initiative petition; approved June 28, 1938, 83,140 to 75,818.", "1938-06-28"),
 "LIV":   ("Article 54; submitted by initiative petition; approved June 28, 1938, 93,156 to 71,448.", "1938-06-28"),
 "LXIII": ("Article 63; Chapter 348, 1951 Session Laws; approved June 24, 1952, 108,469 to 61,006.", "1952-06-24"),
}
for n, (auth, elec) in BF.items():
    r = recs[n]
    assert "undefined" in (r.get("authority") or "").lower(), f"{n}: expected placeholder authority"
    r["authority"] = auth
    if elec and not r.get("election_date"):
        r["election_date"] = elec
    sv = r.get("sources_verified") or []
    sv.append("Re-validated 2026-06-08 vs clean session-law text (round-2 workflow); authority backfilled from the enacted session law.")
    r["sources_verified"] = sv
log.append(f"authority backfill (placeholder -> session-law provenance) for {len(BF)} records: " + ", ".join(BF))

JSON.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
left = [r["number"] for r in doc["amendments"] if "undefined" in (r.get("authority") or "").lower()]
print("Applied:")
for l in log: print("  -", l)
print("remaining 'undefined' authority records:", left or "none")

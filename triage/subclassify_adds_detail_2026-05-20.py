"""Sub-classify the 927 ACCEPT_WL_ADDS_DETAIL rows into pattern buckets,
then pull a stratified 50-row sample for user review.

Output:
  triage/casenames-adds-detail-subclassified-2026-05-20.tsv
  triage/casenames-adds-detail-sample50-2026-05-20.tsv
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INPUT = REPO / "triage" / "casenames-ambig-review-classified-2026-05-20.tsv"
OUT_FULL = REPO / "triage" / "casenames-adds-detail-subclassified-2026-05-20.tsv"
OUT_SAMPLE = REPO / "triage" / "casenames-adds-detail-sample50-2026-05-20.tsv"

# Approximate sample target per sub-pattern (will adjust to total 50).
# Heavier sampling on common buckets so the user's response calibrates the
# common patterns; lighter on rare buckets.
SAMPLE_QUOTAS = {
    "LOCALITY_OF": 15,
    "ROLE_APPOSITIVE": 12,
    "PAREN_PARTY": 6,
    "ESTATE_REFRAME": 5,
    "MULTICASE_MISSED": 4,
    "LONG_PLEADING": 3,
    "DOCKET_METADATA": 2,
    "STATE_EXPANSION": 1,
    "OTHER": 5,
}


def subclassify(db: str, wl: str) -> str:
    """Return a sub-pattern label."""
    if len(wl) >= 100 and re.search(r"\b(?:Plaintiff|Defendant)s?\b", wl):
        return "LONG_PLEADING"
    # Docket / publication metadata, not party detail: "Filed Date",
    # "Rehearing Denied", trailing "Cr. 137", "No. 5118".
    if re.search(r"(?:Filed\s+\w+\.?\s+\d|Rehearing\s+Denied|"
                 r"\bNos?\.\s+\d{3,}|\bCr\.\s*\d)", wl):
        return "DOCKET_METADATA"
    if re.search(r"(?:Same\s+v\.|Heffner\s+v\.\s+Same|Appeal\s+of|\b[Ii]n\s+re\b|"
                 r"\([Tt]wo\s+cases\)|\bState\s+v\.\s+\S+\.\s+State\s+v\.)", wl):
        if not re.search(r"(?:Same\s+v\.|Appeal\s+of|\bIn\s+re|\bin\s+re)", db,
                         re.IGNORECASE):
            return "MULTICASE_MISSED"
    if re.search(r"\bEstate\b", wl) and "Estate" not in db:
        return "ESTATE_REFRAME"
    if re.search(r"\([^)]+(?:Intervener|Garnishee|Intervenor)[^)]*\)", wl):
        return "PAREN_PARTY"
    if re.search(r"\bState\s+of\s+[A-Z]", wl) and not re.search(r"\bState\s+of\s+[A-Z]", db):
        return "STATE_EXPANSION"
    # Locality "of <Place>" added in WL but not in DB anywhere.
    # Case-insensitive — wl_norm is often the .doc's all-caps form.
    wl_of = re.findall(r"\bof\s+[A-Za-z][A-Za-z'.\-]+(?:\s+[A-Za-z][A-Za-z'.\-]+)*"
                       r"(?:,\s*[A-Za-z][A-Za-z.]+\.?)?", wl, re.IGNORECASE)
    db_of = re.findall(r"\bof\s+[A-Za-z][A-Za-z'.\-]+(?:\s+[A-Za-z][A-Za-z'.\-]+)*"
                       r"(?:,\s*[A-Za-z][A-Za-z.]+\.?)?", db, re.IGNORECASE)
    if wl_of and len(wl_of) > len(db_of):
        return "LOCALITY_OF"
    # Role appositive: ", <TitleCase phrase>" appearing in WL but not DB.
    role_kw = (
        r"Atty\.?\s*Gen\.?|Sheriff|Mayor|Judge|Auditor|Treasurer|"
        r"Commissioner|Com'?rs?|Warden|Clerk|State'?s\s*Atty\.?|"
        r"Marshal|Trustee|Director|Governor|Magistrate|Examiner|"
        r"Receiver|Custodian|Department|Drain|Board|Court|"
        r"Members|Council|Hail|Insurance"
    )
    if re.search(rf",\s+(?:[A-Za-z][A-Za-z'.&\s-]+)?(?:{role_kw})", wl, re.IGNORECASE):
        # Confirm DB lacks the same appositive
        if not re.search(rf",\s+(?:[A-Za-z][A-Za-z'.&\s-]+)?(?:{role_kw})", db, re.IGNORECASE):
            return "ROLE_APPOSITIVE"
    return "OTHER"


def main() -> int:
    rows = []
    with INPUT.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            for k, v in list(r.items()):
                if isinstance(v, str):
                    r[k] = v.rstrip("\r")
            if r["verdict"] == "ACCEPT_WL_ADDS_DETAIL":
                rows.append(r)

    print(f"Sub-classifying {len(rows)} ACCEPT_WL_ADDS_DETAIL rows")
    for r in rows:
        r["subpattern"] = subclassify(r["db_name"], r["wl_norm"])

    cols = list(rows[0].keys())
    with OUT_FULL.open("w") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t",
                           extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    counts = Counter(r["subpattern"] for r in rows)
    print("\nSub-pattern breakdown:")
    for k in sorted(counts, key=lambda x: -counts[x]):
        print(f"  {k:<20} {counts[k]:>4}")

    # Stratified sample
    import random
    random.seed(2026)
    by_sub = defaultdict(list)
    for r in rows:
        by_sub[r["subpattern"]].append(r)
    sample = []
    for sub, quota in SAMPLE_QUOTAS.items():
        pool = by_sub.get(sub, [])
        if not pool:
            continue
        take = random.sample(pool, min(quota, len(pool)))
        sample.extend(take)
    print(f"\nSampled {len(sample)} rows -> {OUT_SAMPLE.relative_to(REPO)}")

    with OUT_SAMPLE.open("w") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t",
                           extrasaction="ignore")
        w.writeheader()
        for r in sample:
            w.writerow(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

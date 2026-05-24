"""Resolve date_filed discrepancies by adopting the COURT'S filing date
(ratified policy 2026-05-24): the court-archive "Filed" line (archive.ndcourts.gov,
1965-1997) or the bound N.D. Reports / Westlaw .doc date (<=1953) governs over
CourtListener's date_filed where they differ.

GUARD (symmetric): if the court source date differs from the column by more than
31 days in EITHER direction, it may be a rehearing/supplemental date, a misattributed
source, or an OCR/parse error (e.g. a 90-year jump, or many opinions collapsing to
one date) — those are HELD (written to a flags TSV) for manual review, not applied.
Only small gaps (<=31d, the filed-vs-decided/released band) are auto-adopted.

After --apply, run section10_resequence_2026-05-24.py to bring the synthetic
YYYY ND nnn cites back into date order.

Modes: --dry-run (default) | --apply.  .doc parsing is slow (~minutes).
"""
from __future__ import annotations
import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REFS = Path.home() / "refs" / "nd" / "opin"
sys.path.insert(0, str(REPO))
from ndcourts_mcp.db import DEFAULT_DB_PATH, get_connection, log_change  # noqa: E402

BATCH = "fix-date-court-filed-2026-05-24"
HOLDS = REPO / "triage" / "date-discrepancy-holds-2026-05-24.tsv"
GUARD_DAYS = 31

MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"])}
DOC_DATE = re.compile(r"^((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)\.?\s+(\d{1,2}),\s+(\d{4})\.?\s*$", re.I)
ARCH_FILED = re.compile(r"filed\"?>?\s*Filed\s+([A-Za-z]{3,9})\.?\s+(\d{1,2}),\s+(\d{4})", re.I)


def _mk(mon_word, d, y):
    mon = MONTHS.get(mon_word[:3].lower())
    if not mon:
        return None
    try:
        return date(int(y), mon, int(d)).isoformat()
    except ValueError:
        return None


def doc_date(p: Path):
    try:
        txt = subprocess.run(["textutil","-convert","txt","-stdout",str(p)],
                             capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return None
    for line in txt.splitlines()[:25]:
        m = DOC_DATE.match(line.strip())
        if m:
            return _mk(*m.groups())
    return None


def arch_date(p: Path):
    try:
        m = ARCH_FILED.search(p.read_text(errors="ignore"))
    except OSError:
        return None
    return _mk(*m.groups()) if m else None


def resolve(sp): return Path(sp) if sp.startswith("/") else REFS / sp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    conn = get_connection(DEFAULT_DB_PATH)

    # one court-source date per opinion: prefer court-archive (court's own site),
    # else the bound .doc. (eras are disjoint, but prefer archive if both.)
    rows = conn.execute(
        "SELECT o.id, o.date_filed, s.source_reporter, s.source_path "
        "FROM opinions o JOIN opinion_sources s ON s.opinion_id=o.id "
        "WHERE s.source_path LIKE '%.doc' OR s.source_reporter='court-archive'"
    ).fetchall()
    best = {}  # oid -> (col, kind, court_date)
    for r in sorted(rows, key=lambda r: 0 if r["source_reporter"] == "court-archive" else 1):
        if r["id"] in best:
            continue
        if r["source_reporter"] == "court-archive":
            cd, kind = arch_date(resolve(r["source_path"])), "archive"
        else:
            cd, kind = doc_date(resolve(r["source_path"])), "doc"
        if cd:
            best[r["id"]] = (r["date_filed"], kind, cd)

    adopt, hold = [], []
    for oid, (col, kind, cd) in best.items():
        if cd == col:
            continue
        gap = (date.fromisoformat(cd) - date.fromisoformat(col)).days
        if abs(gap) > GUARD_DAYS:  # large gap either way -> rehearing / misattribution / parse error
            hold.append((oid, col, cd, kind, gap))
        else:
            adopt.append((oid, col, cd, kind, gap))

    print(f"court-source dates parsed for {len(best)} opinions")
    print(f"ADOPT (court date governs) ... {len(adopt)}")
    print(f"HOLD  (court date later >31d, possible rehearing) ... {len(hold)}")
    by_kind = {}
    for _o,_c,_d,k,_g in adopt: by_kind[k] = by_kind.get(k,0)+1
    print(f"  adopt by source: {by_kind}")

    HOLDS.write_text("oid\tcolumn\tcourt_date\tsource\tgap_days\n" +
        "".join(f"{o}\t{c}\t{d}\t{k}\t{g}\n" for o,c,d,k,g in sorted(hold, key=lambda x:-x[4])))
    print(f"holds written -> {HOLDS.relative_to(REPO)}")

    if not args.apply:
        print("\nDRY-RUN. sample adoptions:")
        for o,c,d,k,g in sorted(adopt, key=lambda x: abs(x[4]))[:12]:
            print(f"  oid {o:>6}  {c} -> {d}  ({k}, {g:+d}d)")
        print("re-run with --apply.")
        return 0

    for oid, col, cd, kind, _g in adopt:
        conn.execute("UPDATE opinions SET date_filed=? WHERE id=?", (cd, oid))
        log_change(conn, BATCH, oid, "date_filed", col, cd,
                   authority=f"court filing date ({kind}) governs per 2026-05-24 policy")
    conn.commit()
    print(f"\nApplied {len(adopt)} date adoptions; {len(hold)} held. batch {BATCH}.")
    print("NEXT: run section10_resequence_2026-05-24.py --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

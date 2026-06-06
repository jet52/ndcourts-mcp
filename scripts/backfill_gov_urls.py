"""Backfill ndcourts.gov opinion_url for 1997+ opinions that lack one.

The merge pipeline only sets opinion_url when the scraper's JSON carried one;
~26 modern opinions were captured with opinion_url=None (or no JSON record at
all). This fetches each missing URL directly from ndcourts.gov's
citation-addressable opinion search and writes it back.

Mechanism: ndcourts.gov's opinion listing accepts cit1=<year>&citType=ND&cit2=<n>
to filter to a single neutral cite; the result row's button carries the
/supreme-court/opinions/<id> link. We reuse the scraper's nd_get (Cloudflare
impersonation) and parse_opinion_entries.

Run with --apply to write; default is a dry probe. Logs every change to the
changelog table per the project's data-change policy.
"""

import argparse
import re
import sqlite3
import sys
import time

# Reuse the scraper's Cloudflare-bypass HTTP layer + listing parser.
sys.path.insert(0, "/Users/jerod/code/scraper")
from scraper.nd_http import nd_get  # noqa: E402
from scraper.web_scraper import parse_opinion_entries  # noqa: E402

SEARCH = (
    "https://www.ndcourts.gov/supreme-court/opinions"
    "?topic=&author=&cit1={year}&citType=ND&cit2={num}"
    "&searchQuery=&trialJudge=&pageSize=100&sortOrder=1"
)


def find_targets(conn):
    """1997+ opinions with no opinion_url that have an ND-neutral cite."""
    return conn.execute(
        """
        SELECT o.id, o.date_filed, o.case_name,
               (SELECT citation FROM citations c
                WHERE c.opinion_id = o.id AND c.reporter = 'ND-neutral'
                LIMIT 1) AS neutral
        FROM opinions o
        WHERE o.date_filed >= '1997-01-01' AND o.opinion_url IS NULL
        ORDER BY o.date_filed
        """
    ).fetchall()


def _cite_num(cite):
    """Numeric (year, num) from a 'YYYY ND <digits>' string, else None.

    The site sometimes zero-pads the sequence number ('2021 ND 0216'), so we
    compare numerically rather than by exact string.
    """
    m = re.match(r"\s*(\d{4})\s+ND\s+0*(\d+)\s*$", cite or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def lookup_url(neutral, attempts=3):
    """Return (opinion_url, listing_name) for a 'YYYY ND N' cite, or (None, seen).

    Queries the citation-addressable search. Two complications, both handled:
      - the site zero-pads the sequence number inconsistently ('2021 ND 0216'),
        so we try both the bare and 4-digit-padded cit2 and match numerically;
      - the search is nondeterministic — the identical query intermittently
        returns an unrelated row — so we retry and only ever return on a
        verified numeric cite match (never a guess).
    """
    want = _cite_num(neutral)
    year, num = neutral.split(" ND ")
    variants = (num.strip(), f"{int(num):04d}")
    seen = []
    for _ in range(attempts):
        for cit2 in variants:
            entries = parse_opinion_entries(
                nd_get(SEARCH.format(year=year.strip(), num=cit2)).text, verbosity=0)
            for e in entries:
                if _cite_num(e.get("citation", "")) == want and e.get("opinion_url"):
                    return e["opinion_url"], e.get("case_name", "")
            if entries:
                seen = [e.get("citation") for e in entries]
            time.sleep(1)
    return None, seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="opinions.db")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    targets = find_targets(conn)
    print(f"{len(targets)} targets with an ND-neutral cite\n")

    results = []
    for t in targets:
        if not t["neutral"]:
            print(f"  oid {t['id']:6} {t['date_filed']}  SKIP (no neutral cite)  {t['case_name'][:40]}")
            continue
        try:
            url, info = lookup_url(t["neutral"])
        except Exception as e:
            print(f"  oid {t['id']:6} {t['neutral']:12} ERROR: {type(e).__name__}: {e}")
            time.sleep(1)
            continue
        if url:
            print(f"  oid {t['id']:6} {t['neutral']:12} -> {url}")
            print(f"           db_name={t['case_name'][:45]!r}  gov_name={info[:45]!r}")
            results.append((t["id"], t["neutral"], url))
        else:
            print(f"  oid {t['id']:6} {t['neutral']:12} NOT FOUND (listing cites: {info})")
        time.sleep(1)  # be polite to the server

    print(f"\n{len(results)} URLs resolved.")

    if args.apply and results:
        for oid, neutral, url in results:
            conn.execute("UPDATE opinions SET opinion_url = ? WHERE id = ?", (url, oid))
            conn.execute(
                """INSERT INTO changelog (batch, opinion_id, field, old_value, new_value, authority)
                   VALUES ('backfill-gov-urls-2026-06-06', ?, 'opinion_url', NULL, ?, ?)""",
                (oid, url, f"ndcourts.gov citation search ({neutral})"),
            )
        conn.commit()
        print(f"Applied {len(results)} updates + changelog rows.")
    elif not args.apply:
        print("(dry run — pass --apply to write)")
    conn.close()


if __name__ == "__main__":
    main()

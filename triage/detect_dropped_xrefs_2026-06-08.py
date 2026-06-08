#!/usr/bin/env python3
"""Detect dropped statutory cross-references in statutes.db (TODO PL-1).

Surfacing case: N.D.C.C. § 29-15-21(3) had a full clause dropped at a section
cross-reference (batch ndcc-fix-29-15-21-subsec3-2026-06-08). A heuristic sweep
on 2026-06-08 found the bug is systematic: ~607 hits across ~555 sections.

Signature: the `ingest_statutes.py` PDF extraction drops the NUMBER of a section
cross-reference (and sometimes adjacent runs / bleeds the target's heading in),
leaving a bare "section"/"subsection" with no number after a cross-ref preposition.
The drop begins at the cross-reference; § 29-15-21 swallowed a whole line, most
others drop just the number.

This is a TRIAGE detector — it only catches drops that leave an ungrammatical
seam. Clean number-for-number substitutions won't show up here; the definitive
check is a full re-extract-and-diff against the source PDFs (see TODO PL-1 §2).

Usage:
    python triage/detect_dropped_xrefs_2026-06-08.py [--db statutes.db]
                                                     [--context N] [--all]
                                                     [--csv out.csv]

By default prints a summary + a strided sample. --all prints every hit.
Read-only; never writes to the DB.
"""
import argparse
import csv
import re
import sqlite3
import sys
from collections import Counter

# Cross-reference prepositions that REQUIRE a section number to follow
# "section"/"subsection". A demonstrative ref ("this section", "such subsection")
# is complete and uses a different preceding word, so it is excluded automatically.
XREF_PREP = {"under", "of", "in", "to", "by", "with", "and", "or", "pursuant"}

# Spelled-out numbers — a legit cross-ref or land description ("section twenty-nine").
NUMWORDS = set(
    "one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty "
    "fifty sixty seventy eighty ninety hundred".split()
)

# Known false-positive tokens following the ref word:
#   land descriptions: "section, township, range, county"
#   road term:         "section line"
#   property-tax:      "part of section, and ..." -> next word "line"/"and" near "part"
FP_NEXT = {"township", "range", "county", "line"}


def find_hits(conn, context):
    rows = conn.execute(
        """SELECT p.citation, pv.id, pv.text_content
             FROM provisions p
             JOIN provision_versions pv ON pv.id = p.current_version_id
            WHERE p.corpus = 'ndcc'"""
    ).fetchall()

    word_re = re.compile(r"\S+")

    def norm(w):
        return w.strip().lower().strip(".,;:()'\"")

    hits = []
    for citation, vid, txt in rows:
        if not txt:
            continue
        toks = [(m.group(), m.start()) for m in word_re.finditer(txt)]
        low = [norm(w) for w, _ in toks]
        for i, w in enumerate(low):
            if w not in ("section", "subsection"):
                continue
            prev = low[i - 1] if i > 0 else ""
            nxt = low[i + 1] if i + 1 < len(low) else ""
            if prev not in XREF_PREP:
                continue                          # demonstrative / non-xref context
            if nxt and nxt[0].isdigit():
                continue                          # numbered cross-ref = fine
            if nxt in NUMWORDS or nxt in FP_NEXT:
                continue                          # spelled number / known FP
            start = toks[i][1]
            ctx = txt[max(0, start - context):start + context].replace("\n", " ")
            hits.append((citation, vid, prev, nxt, ctx))
    return hits, len(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="statutes.db")
    ap.add_argument("--context", type=int, default=55,
                    help="chars of context on each side (default 55)")
    ap.add_argument("--all", action="store_true",
                    help="print every hit (default: strided ~55-row sample)")
    ap.add_argument("--csv", help="write all hits to this CSV path")
    args = ap.parse_args(argv)

    conn = sqlite3.connect(args.db)
    hits, n_scanned = find_hits(conn, args.context)
    conn.close()

    sections = sorted({h[0] for h in hits})
    print(f"scanned {n_scanned} current ndcc sections")
    print(f"dropped-xref hits: {len(hits)}  across {len(sections)} distinct sections")
    print("by preceding word:", Counter(h[2] for h in hits).most_common())

    if args.csv:
        with open(args.csv, "w", newline="") as fh:
            wri = csv.writer(fh)
            wri.writerow(["citation", "version_id", "prev", "next", "context"])
            wri.writerows(hits)
        print(f"wrote {len(hits)} rows to {args.csv}")

    print()
    sample = hits if args.all else hits[:: max(1, len(hits) // 55)]
    for citation, vid, prev, nxt, ctx in sample:
        print(f"{citation:20s} [{prev}|{nxt}] …{ctx}…")
    if not args.all and len(sample) < len(hits):
        print(f"\n(showing {len(sample)} of {len(hits)}; use --all or --csv for the full set)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

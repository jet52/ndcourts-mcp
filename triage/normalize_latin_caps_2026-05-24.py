"""Normalize Latin-phrase capitalization in case_name (2026-05-24).

Rule (user-directed): relational Latin phrases ("in re", "ex rel.", "ex parte")
carry NO internal capital letter — the only capital allowed is the very first
letter of the whole case title. So:
  mid-title  -> fully lowercase ("State Ex Rel." -> "State ex rel.")
  title-start -> capitalize only the first letter ("In Re Smith" -> "In re Smith")

Scope of this batch (the unambiguous errors):
  ex rel    : always normalized (incl. all-caps "EX REL" and stray "ex. rel")
  ex parte  : always normalized (all 4 are already correct -> no-op)
  in re     : ONLY when at title-start. Mid-title / parenthetical "(In re ...)"
              are HELD (they are the Court's deliberate modern captions, e.g.
              "Peterson v. S.B. (In re Interest of S.B.)") pending a decision.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "opinions.db"
BATCH = "fix-casenames-latin-caps-2026-05-24"

PH = [
    ("ex rel", re.compile(r"\bex\.?\s+rel\b", re.I), "ex rel", "always"),
    ("ex parte", re.compile(r"\bex\s+parte\b", re.I), "ex parte", "always"),
    ("in re", re.compile(r"\bin\s+re\b", re.I), "in re", "start_only"),
]


def normalize(name: str) -> str:
    new = name
    for _, rx, canon, mode in PH:
        def repl(m, canon=canon, mode=mode):
            at_start = m.start() == 0
            if mode == "start_only" and not at_start:
                return m.group(0)  # hold mid-title / parenthetical "In re"
            return (canon[0].upper() + canon[1:]) if at_start else canon
        new = rx.sub(repl, new)
    return new


def held_paren(name: str) -> bool:
    """A mid-title 'In re' (parenthetical court caption) we are NOT touching."""
    for m in re.finditer(r"\bin\s+re\b", name, re.I):
        seg = name[m.start():m.end()]
        if m.start() != 0 and seg != "in re":
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    conn = sqlite3.connect(DB)
    rows = [(r[0], r[1]) for r in conn.execute(
        "SELECT id, case_name FROM opinions WHERE case_name IS NOT NULL")]

    changes, held = [], []
    for oid, name in rows:
        nn = normalize(name)
        if nn != name:
            changes.append((oid, name, nn))
        if held_paren(name):
            held.append((oid, name))

    print(f"case_names to normalize: {len(changes)}  |  held (parenthetical 'In re'): {len(held)}")
    seen = Counter()
    for oid, o, n in changes:
        tag = "ex rel" if o.lower().count("ex") and re.search(r"\bex\.?\s+rel", o, re.I) and not re.search(r"\bex\.?\s+rel", n) is False else "mix"
        if seen[tag] < 6:
            seen[tag] += 1
            print(f"  {oid}: {o!r} -> {n!r}")

    if args.apply:
        cur = conn.cursor()
        for oid, o, n in changes:
            cur.execute("UPDATE opinions SET case_name=? WHERE id=?", (n, oid))
            cur.execute("INSERT INTO changelog (batch,opinion_id,field,old_value,new_value)"
                        " VALUES (?,?, 'case_name', ?, ?)", (BATCH, oid, o, n))
        conn.commit()
        print(f"\nApplied {len(changes)} normalization(s).")
        print(f"  revert: python -m ndcourts_mcp.cleanup revert {BATCH}")
    else:
        print("\nDry-run. Re-run with --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

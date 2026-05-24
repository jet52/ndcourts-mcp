"""Follow-up Latin-caps normalization (2026-05-24), per user decisions:
  (1) DELETE a trailing "(In re ...)" parenthetical from the 15 modern
      consolidated captions (e.g. "Peterson v. S.B. (In re Interest of S.B.)"
      -> "Peterson v. S.B."). Only parentheticals containing "In re" are removed
      — legitimate parentheticals ("(... Intervener)") are left intact.
  (2) Fix the 8 stray-period "et. al" -> "et al".
  ("Habeas Corpus": user chose to keep — no change.)
"""
from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "opinions.db"
BATCH = "fix-casenames-latin-caps-followup-2026-05-24"

PAREN_INRE = re.compile(r"\s*\([^)]*\bin re\b[^)]*\)", re.I)
ET_AL = re.compile(r"\bet\.\s+al\b", re.I)


def normalize(name: str) -> str:
    new = name
    if PAREN_INRE.search(new):
        # collapse whitespace ONLY to close the gap left by removing the paren
        new = re.sub(r"\s{2,}", " ", PAREN_INRE.sub("", new)).strip()
    new = ET_AL.sub("et al", new)
    return new


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    conn = sqlite3.connect(DB)
    rows = [(r[0], r[1]) for r in conn.execute(
        "SELECT id, case_name FROM opinions WHERE case_name IS NOT NULL")]

    paren, etal = [], []
    for oid, name in rows:
        nn = normalize(name)
        if nn == name:
            continue
        (paren if PAREN_INRE.search(name) else etal).append((oid, name, nn))

    print(f"paren deletions: {len(paren)}   et.al fixes: {len(etal)}")
    print("\n[DELETE '(In re ...)' parenthetical]")
    for oid, o, n in paren:
        print(f"  {oid}: {o!r}\n       -> {n!r}")
    print("\n[et. al -> et al]")
    for oid, o, n in etal:
        print(f"  {oid}: {o!r} -> {n!r}")

    if args.apply:
        cur = conn.cursor()
        for oid, o, n in paren + etal:
            cur.execute("UPDATE opinions SET case_name=? WHERE id=?", (n, oid))
            cur.execute("INSERT INTO changelog (batch,opinion_id,field,old_value,new_value)"
                        " VALUES (?,?, 'case_name', ?, ?)", (BATCH, oid, o, n))
        conn.commit()
        print(f"\nApplied {len(paren) + len(etal)} change(s). revert: python -m ndcourts_mcp.cleanup revert {BATCH}")
    else:
        print("\nDry-run. Re-run with --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

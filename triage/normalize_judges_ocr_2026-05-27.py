"""Normalize OCR-garbled justice surnames in opinions.judges.

The pre-1953 OCR'd N.W.-reporter opinions carry heavily garbled justice
names in the `judges` panel field (e.g. ``Biedzell``/``Bikdzell`` for
``Birdzell``, ``Cheistianson`` for ``Christianson``, ``Yandewalle`` for
``VandeWalle``). This maps each garbled token back to its canonical
justice surname, gated on:

  * edit distance <= 2 to a UNIQUE nearest canonical justice (ties skipped),
  * era overlap: the garble's appearance-years fall within the target
    justice's actual corpus era (derived from years their canonical name
    appears as author / exact judges-token) +/- 10y. Era is derived from
    the corpus, NOT justices.py hard dates, because justices sit as
    surrogates outside their elected term (see feedback_surrogate_judges).
  * the token is not in DOUBTFUL (real distinct surnames / real words that
    could be legitimate surrogate district judges, e.g. Pedersen, Gross,
    Norris) -- those are quarantined for second-source / human review.

Usage: python triage/normalize_judges_ocr_2026-05-27.py [--apply]
"""
from __future__ import annotations
import argparse, sqlite3, sys
from collections import defaultdict
from ndcourts_mcp.justices import JUSTICES
from ndcourts_mcp.db import get_connection, log_change, log_provenance

BATCH = "normalize-judges-ocr-2026-05-27"

# Real surnames / real words near a justice name -> NOT auto-normalized.
DOUBTFUL = {
    "pedersen", "peterson", "paulsen", "knudsen", "spaulding", "spauding",
    "gross", "gloss", "norris", "brothers", "buhr", "sands", "said", "sad",
    "levin", "neuman", "newman", "newmann", "race", "trace", "grade", "making",
    "mating", "holt", "burk", "robison", "berry", "bird", "good", "loss",
    "ace", "luke", "puke", "wigen", "vande", "gel", "knudsen", "sands",
}


def _garbage(t: str) -> bool:
    """An OCR-signature token that cannot be a real surname."""
    if any(ord(ch) > 127 for ch in t):           # diacritic
        return True
    if any(ch in "-'. 0123456789" for ch in t):  # hyphen/apostrophe/digit/space
        return True
    import re as _re
    if _re.search(r"[a-z][A-Z]", t):              # internal caps: BueKE
        return True
    if not any(ch in "aeiouy" for ch in t.lower()):  # no vowel: Bcrr
        return True
    return False


def lev(a: str, b: str) -> int:
    a, b = a.lower(), b.lower()
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def build(conn):
    canon = sorted({k.split("_")[0] for k, _, _, _ in JUSTICES})
    canon_lower = {c.lower(): c for c in canon}

    era = defaultdict(lambda: [9999, 0])
    def note(name, yr):
        cl = (name or "").strip().lower()
        if cl in canon_lower:
            cn = canon_lower[cl]
            era[cn][0] = min(era[cn][0], yr)
            era[cn][1] = max(era[cn][1], yr)
    for author, yr in conn.execute(
            "SELECT author, CAST(substr(date_filed,1,4) AS INT) FROM opinions "
            "WHERE author IS NOT NULL AND date_filed IS NOT NULL"):
        note(author, yr)
    tokyears = defaultdict(list)
    for j, yr in conn.execute(
            "SELECT judges, CAST(substr(date_filed,1,4) AS INT) FROM opinions "
            "WHERE judges IS NOT NULL AND trim(judges)!='' AND date_filed IS NOT NULL"):
        for t in j.replace(";", ",").split(","):
            t = t.strip()
            if not t:
                continue
            tokyears[t].append(yr)
            note(t, yr)

    mapping, doubtful, skipped = {}, [], []
    for tok, yrs in tokyears.items():
        cl = tok.lower()
        if cl in canon_lower:
            continue  # already canonical
        dists = sorted((lev(tok, c2), c2) for c2 in canon)
        d, best = dists[0]
        d2 = dists[1][0]
        n = len(yrs)
        if cl in DOUBTFUL:
            doubtful.append((tok, n, best, d, "real-surname/word")); continue
        if d > 2:
            skipped.append((tok, n, best, d, "dist>2")); continue
        if d2 == d:
            doubtful.append((tok, n, best, d, f"tie with {dists[1][1]}")); continue
        # short justice names collide with real words at dist>=2 -> require an
        # OCR signature; long names (>=7) are safe at dist<=2.
        if len(best) < 7 and not _garbage(tok):
            doubtful.append((tok, n, best, d, "short-name clean match")); continue
        e = era.get(best)
        if not e or e[0] > e[1]:
            doubtful.append((tok, n, best, d, "no-era")); continue
        tmin, tmax = min(yrs), max(yrs)
        if tmin < e[0] - 10 or tmax > e[1] + 10:
            doubtful.append((tok, n, best, d,
                             f"era off (tok {tmin}-{tmax} vs {best} {e[0]}-{e[1]})")); continue
        mapping[tok] = best
    return mapping, doubtful, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="opinions.db")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    conn = get_connection(args.db)
    conn.row_factory = sqlite3.Row
    mapping, doubtful, skipped = build(conn)

    by_just = defaultdict(int)
    for v in mapping.values():
        by_just[v] += 1
    print(f"NORMALIZE: {len(mapping)} garbled tokens -> {len(by_just)} justices")
    for j, n in sorted(by_just.items(), key=lambda x: -x[1]):
        print(f"    {j:14} <- {n} variants")
    print(f"DOUBTFUL (quarantined for review): {len(doubtful)}")
    print(f"SKIPPED (dist>2, not garbage): {len(skipped)}")

    # apply to rows
    rows = conn.execute(
        "SELECT id, judges FROM opinions WHERE judges IS NOT NULL AND trim(judges)!=''"
    ).fetchall()
    changed = 0
    for r in rows:
        toks = [t.strip() for t in r["judges"].replace(";", ",").split(",")]
        new, seen = [], set()
        hit = False
        for t in toks:
            nt = mapping.get(t, t)
            if nt != t:
                hit = True
            if nt and nt.lower() not in seen:
                seen.add(nt.lower()); new.append(nt)
        if hit:
            newval = ", ".join(new)
            if newval != r["judges"]:
                changed += 1
                if args.apply:
                    log_change(conn, BATCH, r["id"], "judges", r["judges"], newval,
                               authority="OCR justice-name normalization (era-gated)")
                    conn.execute("UPDATE opinions SET judges=? WHERE id=?",
                                 (newval, r["id"]))
    print(f"\nrows whose judges field changes: {changed}")
    if args.apply:
        log_provenance(conn, operation="normalize_judges_ocr",
                       command=" ".join(sys.argv), rows_affected=changed,
                       notes=f"batch={BATCH}; {len(mapping)} garble tokens normalized")
        conn.commit()
        print("APPLIED.")
    else:
        print("(dry-run; pass --apply to write)")
    # dump doubtful for the review file
    with open("triage/judges-ocr-doubtful-2026-05-27.md", "w") as f:
        f.write("# Doubtful judges-name tokens (NOT auto-normalized) — need 2nd source / human review\n\n")
        f.write("Tokens near a justice surname but plausibly a real distinct name "
                "(surrogate district judge?) or an ambiguous/era-mismatched match.\n\n")
        f.write("| token | count | nearest justice | dist | reason |\n|---|---:|---|---:|---|\n")
        for tok, n, best, d, why in sorted(doubtful, key=lambda x: (-x[1], x[0])):
            f.write(f"| `{tok}` | {n} | {best} | {d} | {why} |\n")
    print("doubtful list -> triage/judges-ocr-doubtful-2026-05-27.md")


if __name__ == "__main__":
    main()

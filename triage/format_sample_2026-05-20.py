"""Format the 48-row sample for user review, grouped by sub-pattern.

Each row shows: oid, current DB, proposed Westlaw-bound (title-cased).
"""
from __future__ import annotations

import csv
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INPUT = REPO / "triage" / "casenames-adds-detail-sample50-2026-05-20.tsv"


def norm_unicode(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("’", "'").replace("‘", "'")
    s = re.sub(r"[̀-ͯ]", "", s)
    return s


def smart_titlecase(s: str) -> str:
    s = norm_unicode(s)
    lowercase_tokens = {"v.", "v", "ex", "rel.", "rel", "and", "of", "the",
                        "in", "re", "et", "al.", "for", "to", "&"}
    out = []
    for word in s.split(" "):
        wl = word.lower()
        if wl in lowercase_tokens and out:
            out.append(wl); continue
        mm = re.match(r"^(Mc|Mac)([A-Z]+)(.*)$", word)
        if mm and mm.group(2):
            pre, body, tail = mm.groups()
            first, rest = body[0], body[1:]
            tail = tail.title()
            tail = re.sub(r"'S(?=\W|$)", "'s", tail)
            tail = re.sub(r"'Rs(?=\W|$)", "'rs", tail)
            out.append(f"{pre}{first}{rest.lower()}{tail}"); continue
        if word.isupper() and len(word) > 1:
            if re.fullmatch(r"[A-Z]\.(?:[A-Z]\.)+", word):
                out.append(word); continue
            mm2 = re.match(r"^(Mc|Mac)([A-Z])([A-Z]+)(.*)$", word)
            if mm2:
                pre, first, rest, tail = mm2.groups()
                tail = tail.title()
                tail = re.sub(r"'S(?=\W|$)", "'s", tail)
                tail = re.sub(r"'Rs(?=\W|$)", "'rs", tail)
                out.append(f"{pre}{first}{rest.lower()}{tail}"); continue
            om = re.match(r"^O'([A-Z])([A-Z]*)(.*)$", word)
            if om:
                first, rest, tail = om.groups()
                tail = tail.title()
                out.append(f"O'{first}{rest.lower()}{tail}"); continue
            titled = word.title()
            titled = re.sub(r"'S(?=\W|$)", "'s", titled)
            titled = re.sub(r"'Rs(?=\W|$)", "'rs", titled)
            out.append(titled)
        else:
            out.append(word)
    return " ".join(out)


def main() -> int:
    rows = list(csv.DictReader(INPUT.open(), delimiter="\t"))
    for r in rows:
        for k, v in list(r.items()):
            if isinstance(v, str):
                r[k] = v.rstrip("\r")
    grouped = defaultdict(list)
    for r in rows:
        grouped[r["subpattern"]].append(r)
    seq = 1
    for sub in ("LOCALITY_OF", "ROLE_APPOSITIVE", "PAREN_PARTY",
                "ESTATE_REFRAME", "MULTICASE_MISSED", "LONG_PLEADING",
                "DOCKET_METADATA", "STATE_EXPANSION", "OTHER"):
        bucket = grouped.get(sub, [])
        if not bucket:
            continue
        print(f"\n### {sub}  ({len(bucket)} sampled)")
        for r in bucket:
            proposed = smart_titlecase(r["wl_norm"])
            print(f"\n[{seq:>2}] oid {r['opinion_id']} (vol {r['volume']})")
            print(f"     DB:    {r['db_name']}")
            print(f"     -> WL: {proposed}")
            seq += 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

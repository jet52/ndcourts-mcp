"""Apply LOCALITY_OF / ROLE_APPOSITIVE / PAREN_PARTY ACCEPTs to opinions.

Reads triage/casenames-adds-detail-subclassified-2026-05-20.tsv.
Pulls rows with subpattern in {LOCALITY_OF, ROLE_APPOSITIVE, PAREN_PARTY},
title-cases the Westlaw caption with the corrected smart_titlecase
(handles Mc/Mac mixed-case, 's possessive, 'rs/'r abbreviations,
strips residual Cr/Civ docket markers + trailing pipes/commas),
applies under batch fix-casenames-vol16-79-detail-2026-05-20.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from ndcourts_mcp.db import DEFAULT_DB_PATH, get_connection  # noqa: E402

INPUT = REPO / "triage" / "casenames-adds-detail-subclassified-2026-05-20.tsv"
BATCH = "fix-casenames-vol16-79-detail-2026-05-20"
ACCEPT_SUBPATTERNS = {"LOCALITY_OF", "ROLE_APPOSITIVE", "PAREN_PARTY"}


def norm_unicode(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"')
    s = re.sub(r"[̀-ͯ]", "", s)
    return s


_DOCKET_TAIL = re.compile(
    r"\s*\.?\s*(?:Cr|Civ|Crim)\.?(?:\s+(?:No\.\s*)?\d+[A-Za-z]?\.?)?\s*\|?\s*$",
    re.IGNORECASE,
)
_NO_TAIL = re.compile(r"\s*\.?\s*Nos?\.\s*\d+[A-Za-z]?\.?\s*$", re.IGNORECASE)
_PIPE_TAIL = re.compile(r"\s*\|\s*$")
_TRAIL_COMMA = re.compile(r",\s*$")
_COURT_PREFIX = re.compile(
    r"^\s*Supreme\s+Court\s+of\s+North\s+Dakota\s*[,.]?\s*",
    re.IGNORECASE,
)


def clean_residue(s: str) -> str:
    """Strip Cr/Civ docket markers, trailing pipes, dangling commas,
    and a 'Supreme Court of North Dakota,' prefix the .doc parser
    occasionally captures from the court header line."""
    s = _COURT_PREFIX.sub("", s)
    for _ in range(4):
        prev = s
        s = _DOCKET_TAIL.sub("", s).rstrip()
        s = _NO_TAIL.sub("", s).rstrip()
        s = _PIPE_TAIL.sub("", s).rstrip()
        s = _TRAIL_COMMA.sub("", s).rstrip()
        if s == prev:
            break
    return s


def smart_titlecase(s: str) -> str:
    """Title-case a caption, preserving connectives and abbreviations."""
    s = norm_unicode(s)
    lowercase_tokens = {"v.", "v", "ex", "rel.", "rel", "and", "of", "the",
                        "in", "re", "et", "al.", "for", "to", "&"}
    out = []
    for word in s.split(" "):
        wl = word.lower()
        if wl in lowercase_tokens and out:
            out.append(wl)
            continue
        # Mixed-case Mc/Mac (e.g. "McKEE'S")
        mm = re.match(r"^(Mc|Mac)([A-Z]+)(.*)$", word)
        if mm and mm.group(2):
            pre, body, tail = mm.groups()
            first, rest = body[0], body[1:]
            tail = tail.title()
            tail = re.sub(r"'S(?=\W|$)", "'s", tail)
            tail = re.sub(r"'Rs(?=\W|$)", "'rs", tail)
            tail = re.sub(r"'R(?=\W|$)", "'r", tail)
            tail = re.sub(r"'N(?=\W|$)", "'n", tail)
            tail = re.sub(r"'D(?=\W|$)", "'d", tail)
            tail = re.sub(r"'T(?=\W|$)", "'t", tail)
            out.append(f"{pre}{first}{rest.lower()}{tail}")
            continue
        if word.isupper() and len(word) > 1:
            if re.fullmatch(r"[A-Z]\.(?:[A-Z]\.)+", word):
                out.append(word)
                continue
            mm2 = re.match(r"^(Mc|Mac)([A-Z])([A-Z]+)(.*)$", word)
            if mm2:
                pre, first, rest, tail = mm2.groups()
                tail = tail.title()
                tail = re.sub(r"'S(?=\W|$)", "'s", tail)
                tail = re.sub(r"'Rs(?=\W|$)", "'rs", tail)
                tail = re.sub(r"'R(?=\W|$)", "'r", tail)
                out.append(f"{pre}{first}{rest.lower()}{tail}")
                continue
            om = re.match(r"^O'([A-Z])([A-Z]*)(.*)$", word)
            if om:
                first, rest, tail = om.groups()
                tail = tail.title()
                tail = re.sub(r"'S(?=\W|$)", "'s", tail)
                out.append(f"O'{first}{rest.lower()}{tail}")
                continue
            titled = word.title()
            titled = re.sub(r"'S(?=\W|$)", "'s", titled)
            titled = re.sub(r"'Rs(?=\W|$)", "'rs", titled)
            titled = re.sub(r"'R(?=\W|$)", "'r", titled)
            titled = re.sub(r"'N(?=\W|$)", "'n", titled)
            titled = re.sub(r"'D(?=\W|$)", "'d", titled)
            titled = re.sub(r"'T(?=\W|$)", "'t", titled)
            out.append(titled)
        else:
            out.append(word)
    final = " ".join(out)
    # Replace ". Atty." / ". Gen." separator after "ex rel. Name." with ","
    # ("State ex rel. McCue. Atty. Gen." -> "State ex rel. McCue, Atty. Gen.")
    final = re.sub(r"(\bex\s+rel\.\s+\S+?)\.\s+(?=Atty\.|Gen\.|Sheriff|"
                   r"Mayor|Auditor|Treasurer)", r"\1, ", final)
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--sample", type=int, default=0,
                        help="Print first N proposed updates and exit.")
    args = parser.parse_args()

    rows = []
    with INPUT.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            for k, v in list(r.items()):
                if isinstance(v, str):
                    r[k] = v.rstrip("\r")
            if r["subpattern"] in ACCEPT_SUBPATTERNS:
                rows.append(r)

    by_sub = Counter(r["subpattern"] for r in rows)
    print(f"Applying {len(rows)} rows under batch '{BATCH}'")
    for k in sorted(by_sub):
        print(f"  {k:<20} {by_sub[k]}")

    conn = get_connection(DEFAULT_DB_PATH)
    cur = conn.cursor()
    applied = skipped = 0
    for i, r in enumerate(rows):
        oid = int(r["opinion_id"])
        existing = cur.execute(
            "SELECT case_name FROM opinions WHERE id = ?", (oid,)
        ).fetchone()
        if not existing:
            print(f"  oid {oid}: missing, skipping")
            skipped += 1
            continue
        cleaned = clean_residue(r["wl_norm"])
        new = smart_titlecase(cleaned)
        # Final cleanup: collapse double spaces
        new = re.sub(r"\s{2,}", " ", new).strip()
        if existing["case_name"] == new:
            skipped += 1
            continue
        if args.sample and i < args.sample:
            print(f"  oid {oid:>6}  [{r['subpattern']}]  {existing['case_name']!r}  ->  {new!r}")
        if args.apply:
            cur.execute(
                "UPDATE opinions SET case_name = ? WHERE id = ?", (new, oid)
            )
            cur.execute(
                "INSERT INTO changelog (batch, opinion_id, field, old_value, "
                "new_value) VALUES (?, ?, 'case_name', ?, ?)",
                (BATCH, oid, existing["case_name"], new),
            )
            applied += 1

    if args.apply:
        conn.commit()
        print(f"\nApplied {applied} update(s); skipped {skipped}.")
        print(f"  revert: python -m ndcourts_mcp.cleanup revert {BATCH}")
    else:
        sample_n = args.sample or 0
        print(f"\nDry-run: would update ~{len(rows) - skipped} rows.")
        if sample_n:
            print(f"(showed first {sample_n})")
        print(f"Run with --apply to commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Auto-detect authors from opinion text for opinions with junk/garbled author values.

Scans for patterns like "LASTNAME, J.", "LASTNAME, C. J.", "LASTNAME, District Judge."
near the start of the opinion body, then matches against known justices.

Usage:
    python -m ndcourts_mcp.auto_author [--apply] [--batch NAME] [--db PATH]
"""

import argparse
import re
from pathlib import Path

from .db import DEFAULT_DB_PATH, get_connection
from .justices import JUSTICES, KNOWN_LAST_NAMES

# Build a set of canonical last names for matching
_CANONICAL = {}
for key, full_name, start, end in JUSTICES:
    last = key.split("_")[0]
    _CANONICAL[last.lower()] = last

# Known surrogate judges (not elected justices but who sat by assignment)
_SURROGATES = {
    "pollock": "Pollock",
    "templeton": "Templeton",
    "swenson": "Swenson",
    "mckenna": "McKenna",
    "miller": "Miller",
    "cole": "Cole",
    "wolfe": "Wolfe",
    "cooley": "Cooley",
    "kneeshaw": "Kneeshaw",
    "pugh": "Pugh",
    "broderick": "Broderick",
    "thom": "Thom",
    "ilvedson": "Ilvedson",
    "gronna": "Gronna",
    "beede": "Beede",
    "louser": "Louser",
    "wigen": "Wigen",
    "redetzke": "Redetzke",
    "nelson": "Nelson",
    "amundson": "Amundson",
}

BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
RESET = "\033[0m"

# Pattern: LASTNAME, J. or LASTNAME, C. J. or LASTNAME, District Judge.
# Appears near the start of the opinion body (after the header/syllabus)
_AUTHOR_PAT = re.compile(
    r"^([A-Z][A-Za-zÀ-ÿí]+(?:\s[A-Z][a-z]+)?)"  # Last name, possibly two words
    r",\s*"
    r"(?:C\.\s*J|Ch\.\s*J|J|District Judge|Dist(?:\.|rict)?\s*Judge)"
    r"\.",
    re.MULTILINE,
)


def _extract_author_from_text(text: str) -> str | None:
    """Try to find 'LASTNAME, J.' in opinion text and resolve to a known justice."""
    # Search in the first 3000 chars after any "---" frontmatter
    body = text
    fm_end = text.find("---", 4)
    if fm_end > 0:
        body = text[fm_end + 3:]

    # Look in first 3000 chars of body
    search_area = body[:3000]

    matches = _AUTHOR_PAT.findall(search_area)
    for name in matches:
        name = name.strip()
        low = name.lower()

        # Direct match to known justice
        if low in _CANONICAL:
            return _CANONICAL[low]

        # Check surrogates
        if low in _SURROGATES:
            return _SURROGATES[low]

        # Fuzzy: try matching OCR-garbled names
        # e.g., "Fisií" → "Fisk" — require 4+ char prefix match and similar length
        for canon_low, canon in _CANONICAL.items():
            if len(low) >= 4 and len(canon_low) >= 4:
                if low[:4] == canon_low[:4] and abs(len(low) - len(canon_low)) <= 1:
                    return canon
        for surr_low, surr in _SURROGATES.items():
            if len(low) >= 4 and len(surr_low) >= 4:
                if low[:4] == surr_low[:4] and abs(len(low) - len(surr_low)) <= 1:
                    return surr

    return None


def find_fixable_opinions(db_path: Path) -> list[dict]:
    """Find opinions with bad authors where we can detect the real author from text."""
    conn = get_connection(db_path)

    # Get all known justice last names
    valid_authors = set(_CANONICAL.values()) | set(_SURROGATES.values())

    # Find opinions with non-justice authors
    rows = conn.execute(
        "SELECT id, case_name, date_filed, author, text_content FROM opinions "
        "WHERE author IS NOT NULL ORDER BY date_filed"
    ).fetchall()

    fixable = []
    for row in rows:
        row = dict(row)
        if row["author"] in valid_authors:
            continue

        detected = _extract_author_from_text(row["text_content"])
        if detected:
            fixable.append({
                "id": row["id"],
                "case_name": row["case_name"],
                "date_filed": row["date_filed"],
                "old_author": row["author"],
                "new_author": detected,
            })

    conn.close()
    return fixable


def main():
    parser = argparse.ArgumentParser(description="Auto-detect authors from opinion text")
    parser.add_argument("--apply", action="store_true", help="Apply corrections")
    parser.add_argument("--batch", default="auto-author", help="Changelog batch name")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()

    fixable = find_fixable_opinions(args.db)

    if not fixable:
        print("No fixable opinions found.")
        return

    # Group by old_author → new_author for summary
    corrections: dict[tuple[str, str], list] = {}
    for f in fixable:
        key = (f["old_author"], f["new_author"])
        corrections.setdefault(key, []).append(f)

    print(f"{BOLD}Auto-detected author corrections:{RESET}\n")
    for (old, new), opinions in sorted(corrections.items(), key=lambda x: -len(x[1])):
        print(f"  {YELLOW}{old}{RESET} → {CYAN}{new}{RESET}  ({len(opinions)} opinions)")
        if len(opinions) <= 5:
            for op in opinions:
                print(f"    {DIM}{op['date_filed']} {op['case_name']}{RESET}")

    print(f"\n{BOLD}Total: {len(fixable)} corrections across {len(corrections)} author mappings{RESET}")

    if args.apply:
        conn = get_connection(args.db)
        for f in fixable:
            conn.execute(
                "INSERT INTO changelog (batch, opinion_id, field, old_value, new_value) "
                "VALUES (?, ?, 'author', ?, ?)",
                (args.batch, f["id"], f["old_author"], f["new_author"]),
            )
            conn.execute(
                "UPDATE opinions SET author = ? WHERE id = ?",
                (f["new_author"], f["id"]),
            )
        conn.commit()
        conn.close()
        print(f"\n{CYAN}Applied {len(fixable)} corrections.{RESET}")
    else:
        print(f"\n{DIM}Dry run. Use --apply to commit changes.{RESET}")


if __name__ == "__main__":
    main()

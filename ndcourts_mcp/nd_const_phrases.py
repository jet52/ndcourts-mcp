"""Quote -> provision table for the North Dakota Constitution.

Many older ND opinions (esp. pre-1981, before the constitution was renumbered
from flat sections into articles) reference a constitutional provision by
*quoting its text* rather than citing a section. A citation parser misses
those. This table maps distinctive verbatim clause fragments to the provision
they belong to, so an opinion that merely quotes a clause can still be
attributed to the right section.

Provenance / how this was built (so it stays auditable and regenerable):
  * Each provision's MODERN article/§ was derived from the corpus itself, not
    from memory: among post-1981 opinions that quote a fragment, we tallied the
    captured ``N.D. Const. art. X, § Y`` cites co-occurring in the same opinion;
    the dominant cite is the mapping. (Renumbering note: the same clause that an
    1890s opinion cited as a flat "§ 13" the court today cites as art. I, § 12 —
    we map to the MODERN provision, which is what the co-occurrence yields.)
  * Each fragment's exact wording was taken verbatim from how ND opinions quote
    it (e.g. § 1's verb is "acquiring", not "obtaining"; the open-courts clause's
    distinctive "in his lands, goods, person or reputation").
  * ``federal_overlap`` flags fragments that also appear in the U.S.
    Constitution (4th/5th/6th/8th/14th Amendments). For those, a consumer should
    require ND context in the opinion (see ``ND_CONTEXT_MARKERS``) before
    attributing the ND provision, or record BOTH.

Confidence tiers:
  high  ND-distinctive wording AND a clean dominant co-occurring cite.
  med   correct provision but the fragment is short / federally shared / low-n.

To regenerate/verify: re-run the co-occurrence analysis (post-1981 opinions
quoting the fragment vs. their captured ``constitution`` text_citations) and the
verbatim snippet pull against the corpus.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ConstPhrase:
    phrase: str          # verbatim fragment, lowercased, single-spaced
    provision: str       # canonical modern cite
    tier: str            # "high" | "med"
    federal_overlap: str | None  # parallel U.S. provision, if the wording is shared
    note: str


# Phrases that, if a federally-overlapping clause, need ND context to attribute
# the *state* provision rather than (or in addition to) the federal one.
ND_CONTEXT_MARKERS = (
    "n.d. const", "n. d. const", "north dakota constitution",
    "constitution of north dakota", "constitution of this state",
    "state constitution", "our constitution", "organic law", "fundamental law",
    "declaration of rights", "bill of rights",
)

# --- Article I, Declaration of Rights ---
PHRASE_TABLE: tuple[ConstPhrase, ...] = (
    # § 1 — inherent/inalienable rights (incl. right to keep and bear arms, added 1984)
    ConstPhrase("equally free and independent", "N.D. Const. art. I, § 1", "high", None,
                "opening of the inalienable-rights clause"),
    ConstPhrase("acquiring, possessing and protecting property and reputation",
                "N.D. Const. art. I, § 1", "high", None,
                "'reputation' is ND-distinctive (U.S. has no analog)"),
    ConstPhrase("pursuing and obtaining safety and happiness", "N.D. Const. art. I, § 1",
                "high", None, "close of the inalienable-rights enumeration"),
    ConstPhrase("keep and bear arms", "N.D. Const. art. I, § 1", "high",
                "U.S. Const. amend. II", "ND places the arms right in art. I § 1 (1984)"),

    # § 3 — religious liberty
    ConstPhrase("free exercise and enjoyment of religious", "N.D. Const. art. I, § 3",
                "med", "U.S. Const. amend. I", "low-n; confirm ND context"),

    # § 4 — speech, press, assembly
    ConstPhrase("peaceably to assemble", "N.D. Const. art. I, § 4", "med",
                "U.S. Const. amend. I", "low-n; confirm ND context"),

    # § 8 — searches and seizures
    ConstPhrase("unreasonable searches and seizures", "N.D. Const. art. I, § 8", "high",
                "U.S. Const. amend. IV", "very common; dominant ND cite is § 8 (n=135, 81%)"),

    # § 9 — open courts / remedy by due process (distinctive ND wording)
    ConstPhrase("courts shall be open", "N.D. Const. art. I, § 9", "high", None,
                "open-courts clause"),
    ConstPhrase("in his lands, goods, person or reputation", "N.D. Const. art. I, § 9",
                "high", None, "highly distinctive open-courts phrasing"),
    ConstPhrase("every man for any injury done him", "N.D. Const. art. I, § 9", "high", None,
                "open-courts clause"),
    ConstPhrase("remedy by due process of law", "N.D. Const. art. I, § 9", "high", None,
                "the § 9 remedy clause — NOT the generic 14th-Am. due-process phrase"),

    # § 11 — bail, fines, punishment (ND says 'cruel OR unusual')
    ConstPhrase("excessive bail", "N.D. Const. art. I, § 11", "med", "U.S. Const. amend. VIII",
                "confirm ND context"),
    ConstPhrase("cruel or unusual punishments", "N.D. Const. art. I, § 11", "high",
                "U.S. Const. amend. VIII", "ND uses 'or' (U.S. 8th Am. says 'and')"),

    # § 12 — rights of the accused (speedy/public trial, self-incrimination, double jeopardy)
    ConstPhrase("twice put in jeopardy", "N.D. Const. art. I, § 12", "med",
                "U.S. Const. amend. V", "double jeopardy; confirm ND context"),
    ConstPhrase("witness against himself", "N.D. Const. art. I, § 12", "med",
                "U.S. Const. amend. V", "self-incrimination; confirm ND context"),
    ConstPhrase("speedy and public trial", "N.D. Const. art. I, § 12", "med",
                "U.S. Const. amend. VI", "old flat § 13 -> modern art. I § 12"),

    # § 13 — trial by jury
    ConstPhrase("right of trial by jury shall be secured", "N.D. Const. art. I, § 13",
                "high", None, "ND jury-trial guarantee"),

    # § 16 — eminent domain (ND distinctively adds 'or damaged')
    ConstPhrase("taken or damaged for public use", "N.D. Const. art. I, § 16", "high",
                "U.S. Const. amend. V", "'or damaged' is ND-distinctive (U.S. 5th: 'taken' only)"),
    ConstPhrase("without just compensation", "N.D. Const. art. I, § 16", "med",
                "U.S. Const. amend. V", "shared takings phrasing; confirm ND context"),

    # --- Article VIII, Education ---
    ConstPhrase("uniform system of free public schools", "N.D. Const. art. VIII, § 2", "med",
                None, "education clause; § 1/§ 2 split in co-occurrence — verify section"),
)

# Documented NON-mappings: fragments that look constitutional but are NOT
# reliable ND fingerprints. Kept here so the exclusion rationale is auditable.
EXCLUDED = {
    "obligation of contracts":
        "ambiguous — old ND opinions quoting this are usually quoting U.S. Const. "
        "art. I, § 10; ND also has a contracts clause, so attribution needs context",
    "privileges or immunities of citizens of the united states":
        "U.S. Const. amend. XIV — not a ND provision",
    "due process of law":
        "too generic; dominated by U.S. Const. amend. XIV. Use the § 9 form "
        "'remedy by due process of law' instead",
    "equal protection":
        "too generic; U.S. Const. amend. XIV. ND's analog is the special-privileges/"
        "uniform-operation clause (art. I, §§ 21-22) with different wording",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).lower()


def match(text: str, require_nd_context: bool = True):
    """Yield (provision, phrase, federal_overlap) for each ND-const clause quoted.

    For federally-overlapping fragments, when ``require_nd_context`` is True the
    match is only emitted if the text also carries a ND-constitution marker
    (so a bare 4th-Amendment discussion isn't attributed to ND art. I § 8).
    """
    norm = _norm(text)
    has_nd_ctx = any(m in norm for m in ND_CONTEXT_MARKERS)
    seen: set[tuple[str, str]] = set()
    for cp in PHRASE_TABLE:
        if cp.phrase not in norm:
            continue
        if cp.federal_overlap and require_nd_context and not has_nd_ctx:
            continue
        key = (cp.provision, cp.phrase)
        if key in seen:
            continue
        seen.add(key)
        yield cp.provision, cp.phrase, cp.federal_overlap

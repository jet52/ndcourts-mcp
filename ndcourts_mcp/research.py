"""Pure helpers for the human-research tools.

Westlaw-style Boolean/proximity → FTS5 translation, statutory/rule authority
normalization, and salient-term extraction for related-opinion search. No DB
access; ``server.py`` holds the ``@mcp.tool()`` wrappers.
"""

import re

# --- Westlaw-style Boolean / proximity → FTS5 -------------------------------

# Approximation note (surfaced to callers): FTS5 has no sentence or paragraph
# unit, so /s and /p map to token-distance NEAR windows.
PROX_S = 20  # /s  same sentence  ≈ within 20 tokens
PROX_P = 50  # /p  same paragraph ≈ within 50 tokens

_BOOL_WORDS = {"AND", "OR", "NOT"}

_TOKEN_RE = re.compile(
    r"""
      "(?P<phrase>[^"]*)"        # "quoted phrase"
    | /(?P<prox>s|p|\d+)         # proximity: /s /p /N
    | (?P<amp>&)
    | (?P<pipe>\|)
    | (?P<pct>%)
    | (?P<word>[^\s&|%/"]+)      # a bare word
    """,
    re.X | re.I,
)


def _word_to_fts(w: str) -> str:
    """Westlaw truncation ! → FTS5 prefix *; drop unsupported bare wildcards."""
    w = w.replace("!", "*")
    # FTS5 only supports a trailing prefix '*'; collapse any others and a lone '*'.
    w = re.sub(r"\*+", "*", w)
    if w == "*":
        return ""
    # A '*' only has meaning at the end in FTS5.
    if "*" in w and not w.endswith("*"):
        w = w.replace("*", "")
    return w


def translate_boolean(query: str) -> tuple[str, list[str]]:
    """Translate a Westlaw-style query to an FTS5 MATCH expression.

    Supported: ``&`` (AND), ``|`` / ``OR`` (OR), ``%`` / ``NOT`` (BUT NOT),
    ``/N`` (within N tokens → NEAR/N), ``/s`` (same sentence ≈ NEAR/20),
    ``/p`` (same paragraph ≈ NEAR/50), ``!`` truncation (→ prefix ``*``), and
    ``"quoted phrases"``. Returns ``(fts_query, notes)``.
    """
    notes: list[str] = []
    items: list[tuple[str, object]] = []  # (kind, value) ; prox value is int K
    for m in _TOKEN_RE.finditer(query):
        if m.group("phrase") is not None:
            items.append(("term", f'"{m.group("phrase").strip()}"'))
        elif m.group("prox") is not None:
            p = m.group("prox").lower()
            k = PROX_S if p == "s" else PROX_P if p == "p" else int(p)
            items.append(("prox", k))
        elif m.group("amp"):
            items.append(("op", "AND"))
        elif m.group("pipe"):
            items.append(("op", "OR"))
        elif m.group("pct"):
            items.append(("op", "NOT"))
        else:
            w = m.group("word")
            if w.upper() in _BOOL_WORDS:
                items.append(("op", w.upper()))
            else:
                fts = _word_to_fts(w)
                if fts:
                    items.append(("term", fts))

    has_prox = any(k == "prox" for k, _ in items)
    has_s = False
    has_p = False
    for k, v in items:
        if k == "prox" and v == PROX_S:
            has_s = True
        if k == "prox" and v == PROX_P:
            has_p = True

    out: list[str] = []
    i = 0
    while i < len(items):
        kind, val = items[i]
        if kind == "term":
            run_terms = [val]
            run_k: list[int] = []
            j = i + 1
            while (j + 1 < len(items) and items[j][0] == "prox"
                   and items[j + 1][0] == "term"):
                run_k.append(items[j][1])  # type: ignore[arg-type]
                run_terms.append(items[j + 1][1])
                j += 2
            if len(run_terms) > 1:
                out.append(f"NEAR({' '.join(run_terms)}, {max(run_k)})")
                i = j
            else:
                out.append(val)
                i += 1
        elif kind == "op":
            out.append(val)
            i += 1
        else:  # stray proximity op without two operands
            i += 1

    if has_s:
        notes.append(f"/s approximated as NEAR/{PROX_S} (no true sentence unit)")
    if has_p:
        notes.append(f"/p approximated as NEAR/{PROX_P} (no true paragraph unit)")
    return " ".join(out).strip(), notes


# --- statutory / court-rule authority normalization ------------------------

# Court-rule abbreviation aliases → canonical normalized prefix in the corpus.
_RULE_ALIASES = {
    "ndrcivp": "N.D.R.Civ.P.", "ndrcrimp": "N.D.R.Crim.P.",
    "ndrev": "N.D.R.Ev.", "ndrappp": "N.D.R.App.P.",
    "ndrctp": "N.D.R.Ct.", "ndrprofconduct": "N.D.R. Prof. Conduct",
    "frcivp": "Fed. R. Civ. P.", "frcrimp": "Fed. R. Crim. P.",
    "frevid": "Fed. R. Evid.", "frev": "Fed. R. Evid.",
    "frapp": "Fed. R. App. P.",
}

_SECTION_RE = re.compile(r"\b(\d+(?:\.\d+)?-\d+(?:-\d+(?:\.\d+)?)?)\b")
_RULE_NUM_RE = re.compile(r"\b(\d+(?:\.\d+)?)\b")


# --- case-citation extraction (for draft proofreading) ----------------------

# Only the reporter forms that resolve to in-corpus ND opinions — the only
# cites the citator can act on. Foreign cites can't be checked here anyway.
_CASE_CITE_RES = [
    re.compile(r"\b\d{4}\s+ND\s+\d+\b"),                       # neutral / synthetic
    re.compile(r"\b\d+\s+N\.\s?W\.\s?(?:2d|3d)?\s+\d+\b"),     # N.W. / N.W.2d / N.W.3d
    re.compile(r"\b\d+\s+N\.\s?D\.\s+\d+\b"),                  # official N.D. Reports
]


def normalize_cite_string(cite: str) -> str:
    """Collapse whitespace and edition spacing so a draft cite matches the DB
    form ('N.W. 2d' → 'N.W.2d', '2013  ND 169' → '2013 ND 169')."""
    c = re.sub(r"\s+", " ", cite.strip())
    return re.sub(r"(\.\s?[A-Z]\.)\s*(\d[a-z]+)", lambda m: m.group(0).replace(" ", ""), c)


def extract_case_cites(text: str) -> list[str]:
    """All distinct ND / N.W. / N.D. case-citation strings in ``text``,
    normalized to DB form, preserving first-seen order."""
    seen: dict[str, None] = {}
    for pat in _CASE_CITE_RES:
        for m in pat.finditer(text):
            seen.setdefault(normalize_cite_string(m.group(0)), None)
    return list(seen)


def normalize_authority(query: str) -> dict:
    """Parse a statute/rule reference into a match spec against text_citations.

    Returns ``{kind, token, exact}`` where ``kind`` is 'statute' | 'court_rule'
    | None, ``token`` is the section/rule number to match on a token boundary,
    and ``exact`` is a best-effort canonical normalized string (or None)."""
    q = query.strip()
    low = q.lower().replace(" ", "").replace(".", "")

    # Court rule? (contains "r." rule-set or an alias, or the word "rule")
    rule_prefix = None
    for alias, canon in _RULE_ALIASES.items():
        if alias in low:
            rule_prefix = canon
            break
    if rule_prefix or re.search(r"\brule\b", q, re.I) or re.search(r"\.R\.", q):
        m = _RULE_NUM_RE.search(q)
        token = m.group(1) if m else None
        exact = f"{rule_prefix} {token}" if rule_prefix and token else None
        return {"kind": "court_rule", "token": token, "exact": exact}

    # Statute (N.D.C.C.)?
    m = _SECTION_RE.search(q)
    if m:
        sec = m.group(1)
        groups = sec.split("-")
        if len(groups) == 2:  # title-chapter → chapter cite
            exact = f"N.D.C.C. ch. {sec}"
        else:
            exact = f"N.D.C.C. § {sec}"
        return {"kind": "statute", "token": sec, "exact": exact}

    return {"kind": None, "token": None, "exact": None}


def authority_token_matches(normalized: str, token: str) -> bool:
    """True if ``normalized`` cites exactly ``token`` (boundary-safe).

    Guards against '1-02-02' matching '11-02-02': the token must be the final
    whitespace-delimited unit of the normalized cite."""
    return normalized.split()[-1] == token if normalized else False


# --- salient terms (related-opinion keyword half) ---------------------------

_STOPWORDS = {
    # generic
    "the", "a", "an", "and", "or", "but", "not", "of", "to", "in", "on", "for",
    "with", "as", "by", "at", "from", "is", "was", "were", "are", "be", "been",
    "this", "that", "these", "those", "it", "its", "he", "she", "they", "we",
    "his", "her", "their", "our", "which", "who", "whom", "whose", "had", "has",
    "have", "will", "would", "shall", "may", "must", "can", "could", "did",
    "does", "do", "no", "if", "then", "than", "there", "here", "such", "any",
    "all", "also", "only", "more", "most", "other", "some", "into", "under",
    "upon", "when", "where", "while", "because", "however",
    # legal boilerplate
    "court", "courts", "opinion", "opinions", "district", "supreme", "appeal",
    "appeals", "appellant", "appellee", "plaintiff", "defendant", "justice",
    "judge", "case", "cases", "north", "dakota", "state", "county", "law",
    "section", "argues", "argued", "held", "holding", "affirmed", "reversed",
    "remanded", "order", "judgment", "motion", "filed", "trial", "matter",
    "facts", "evidence", "rule", "see", "also", "id", "para", "syllabus",
}

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]{2,}")


def salient_terms(text: str, k: int = 12) -> list[str]:
    """Top content words of an opinion (frequency over a stopword filter)."""
    freq: dict[str, int] = {}
    for m in _WORD_RE.finditer(text):
        w = m.group(0).lower()
        if len(w) < 4 or w in _STOPWORDS:
            continue
        freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq, key=lambda w: (-freq[w], w))
    return ranked[:k]

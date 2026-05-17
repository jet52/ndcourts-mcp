# §6 deferred — borderline trio + multi-row clusters (2026-05-17)

Deferred from the `section6-handadj-2026-05-17` clean-14 merge pass. These
were held back deliberately: the clean tranche was simple 2-row pairs at
j≥0.55 with an unambiguous keep. The items below need a per-item human read
before any `merge_pair` — they are either same-caption/same-date with
suspiciously low text overlap (true-dup-with-stub vs lead+rehearing vs
distinct disposition is undecidable from jaccard alone) or >2-row clusters
that the pairwise keep policy can't safely resolve mechanically.

All oids verified present post-merge (corpus 20242). Jaccard = 4-word
shingle Jaccard of body text (frontmatter stripped).

## Borderline trio — same caption, same date, sub-threshold jaccard

Identical case_name + identical date_filed but low text overlap. Each is
either (a) a true dup where one row is an OCR stub, or (b) a lead opinion +
rehearing/disposition published at the same page, or (c) two distinct
dispositions. Must read both texts to classify; do NOT merge blind.

| cite | rows (both NW2d, cb1) | j | lean |
|---|---|---|---|
| 344 N.W.2d 489 | 9058 / 9059 *Anderson v. State* (1984-02-23) | 0.70 | probably true dup w/ OCR drift; closest to mergeable |
| 489 N.W.2d 885 | 11200 / 11201 *Dibble v. Backes* (1992-10-01) | 0.54 | Backes DUI-license companion; dup-with-stub vs lead+rehearing — read |
| 539 N.W.2d 869 | 12027 / 12028 *City of Dickinson v. Powell* (1995-11-30) | 0.39 | low overlap despite identical caption — likely two distinct dispositions, lean NOT a simple dup |

## Multi-row clusters — >2 rows share the cite

Pairwise keep policy can't resolve these mechanically; each needs a
cluster plan (which rows collapse, which survive as distinct page-mates).

### 57 N.W.2d 242 — 3-row true-dup cluster (1953-01-23)
- 12544 *United States v. State* — **westlaw** cb1  ← keep (authoritative bound text)
- 12545 *United States v. State* — NW2d cb1
- 12546 *In Re Heiden's Estate* — NW2d cb1

All-pairs j 0.85–0.92 → one probate opinion captioned both ways. Plan:
merge 12545→12544 and 12546→12544 (keep the Westlaw row per the
authoritative-text refinement). canonical_name needs the human caption
pass — `_canonical_name` would yield `Estate of Heiden`, but the reported
caption is `United States v. State` (a/k/a *In re Heiden's Estate*); pick
in the §1 case-name pass, don't guess here.

### 521 N.W.2d 643 — 4 rows: 2 dup pairs sharing a page (1994-09-13)
- Hosman pair: 11738 / 11740 *Hosman v. NDSU* — j=0.62 → true dup
- Ferris pair: 11739 / 11741 *Ferris v. ND Centennial Comm'n* — j=0.51 → borderline dup (read)
- Hosman ≠ Ferris (cross-j 0.20–0.32) → distinct page-mates, keep one survivor each

Plan: merge within each pair (Hosman: 11740→11738; Ferris: read then
11741→11739 if confirmed), end with 2 distinct survivors on the shared
page. Hosman pair is the safer of the two.

### 489 N.W.2d 886 — 4 rows: 2 borderline dup pairs sharing a page (1992-10-01)
- Woessner pair: 11202 / 11204 *Woessner v. Backes* — j=0.51
- Putney pair: 11203 / 11205 *Putney v. Backes* — j=0.47
- Woessner ≠ Putney (cross-j 0.12–0.21) → distinct page-mates

Backes DUI-license companion cases. Both internal pairs sub-0.55 — same
read-before-merge caveat as 489 N.W.2d 885. End with 2 distinct survivors.

## Related §6-blocked remainder (for audit completeness — not in scope here)

From the same 45 Westlaw-blocked set, also still open (tracked elsewhere):
- **9 distinct page-mates** (j<0.55, genuinely separate opinions sharing a
  N.W. page — e.g. `Calavera v. Vix`≠`Bauer v. Bauer`, `Moosbrugger`≠
  `Sletten`, `Hosman`≠`Ferris`). Must NOT merge; route each to its own
  Westlaw pull (category-A), not §6.
- **481 N.W.2d 225** *Disc. Bd. v. Johnson* 11076 — merged structurally in
  the clean-14 pass but the Westlaw doc held LOW_SIM (j≈0.004 vs survivor
  text); doc may be a different Johnson order. Manual.

## How to resume

1. Read both (all) texts per item; classify dup / lead+rehearing / distinct.
2. True dups → `merge_pair(keep, drop, canonical, apply=True, batch=...)`,
   keep = Westlaw row if exactly one side is `source_reporter='westlaw'`,
   else more `cited_by` (tie → longer text). canonical = `_canonical_name(keep)`.
3. Distinct page-mates → de-flag, route to own Westlaw pull.
4. Snapshot first (DELETE is snapshot-only revertible) → apply →
   `align_primary_source --apply` → invariants 0-regressed → 0-orphan-ref →
   `receive_westlaw` re-run to fill survivors with bound text.

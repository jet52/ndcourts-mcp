# Triage: 1,049 flagged from `court-archive-promote-2026-05-15`

Disposition of every opinion the court-archive promotion flagged instead
of auto-promoting. The flag worked: nothing was corrupted; this resolves
the ambiguity the length-ratio gate could not.

## Composition

| bucket | n | gate reason |
|---|--:|---|
| manual_outlier | 1,018 | length ratio outside [0.80, 2.50] (1,016 low, 2 high) |
| review_band | 11 | ratio in [0.80,0.95) ∪ (1.60,2.50] |
| shared_cite_ambiguous | 10 | two court pages share one N.W. cite (Type-Y) |
| noncl (modern) | 10 | non-CL primary diverges; cross-check only |

## manual_outlier root cause (the 1,018)

Re-bucketed with a **containment** signal — fraction of the court
text's 4-word shingles that appear in the DB body — plus a
caption-duplication test:

| sub-bucket | n | finding | disposition |
|---|--:|---|---|
| **CL self-duplication** | ~1,003 | DB `text_content` carries the SAME opinion duplicated (CL ingest artifact: repeated caption, unique-extra < 0.55). Court text is the single clean copy, ≥0.85 contained in the DB body. | **PROMOTE** — court is canonical; replacing the bloated DB body drops only duplicated content, no unique text. |
| clean/contained | ~8 | court ≥0.92 contained, residual is OCR drift | promote or trivial review |
| court-truncated | 7 | court archive page is itself incomplete (e.g. *Metcalf v. Security Int'l*, oid 7792 — court text ends mid-sentence "Judith asserts, on the"; DB ends properly "ERICKSTAD, C.J., … concur."). | **KEEP FLAGGED** — DB is the full opinion; do not promote. Also a court-archive scrape-quality item. |
| divergent | 2 | both substantial, neither contained | manual inspection |

Worked example — *Carlson v. Job Service* (oid 12191): DB body 72,689
chars with the caption duplicated; court text 20,880 chars, complete
(ends "…Mary Muehlen Maring"), fully contained in the DB. Ratio 0.29
blocked auto-promotion; containment shows the court text is the clean
canonical opinion and the DB is CL self-duplication.

## Finding beyond the flag

~1,003 gap-era CourtListener opinions have **self-duplicated body
text** — a concrete upstream CL data defect. Material for the deferred
CL-feedback objective; logged here as the authoritative record.

## Recommended disposition

1. **Promote the ~1,003 CL-self-duplication + ~8 clean-contained**
   under a new containment rule (see below) — court text is provably
   the clean canonical, no unique content lost.
2. **Keep the 7 court-truncated flagged**; sharpen note to
   `court-source-truncated`; add to a court-archive re-scrape list.
3. **2 divergent + 11 review_band + 10 shared_cite_ambiguous**: remain
   flagged for manual / §6-dup / Type-Y handling.

### Proposed containment rule (extends the approved promotion policy)

For a flagged low-ratio opinion whose primary is CL-origin: if the
court text's shingle-containment in the DB body ≥ 0.85 AND the DB body
shows the caption-duplication signature (first-8-words recur ≥ 2× and
unique-extra fraction < 0.55), promote `text_content` to the court
text. Containment ≥ 0.85 guarantees the court text is not a truncation
and the DB "extra" is duplicated, not a second distinct opinion — so
no unique content is lost. Same snapshot + changelog + invariants
discipline; same revert path.

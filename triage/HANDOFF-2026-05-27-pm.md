# HANDOFF — 2026-05-27 (PM session)

Self-contained handoff for a fresh agent. Authoritative trackers: `TODO-validation.md`
(★ PRIORITY TODO block at top) and `CHANGELOG-data.md` (newest at top). Supersedes the
AM `HANDOFF-2026-05-27.md` for current state.

## Current state
- Corpus **19,785** opinions (`opinions.db`, ~1.1 GB, NOT git-tracked). Use `.venv/bin/python`.
- Invariants **22 ok / 2 known-baseline / 0 regressed** (`python -m ndcourts_mcp.invariants`).
  Known baselines: `neutral_cite_uniqueness`=0, `nd_modern_paragraph_markers` (~85 short orders).
- `detect_cite_swap` **0 / 0 / 0**. `volume_date_check` = **11** (all quarantined, below).
- Neutral-cite sequences gap-free 1997–2026. Always snapshot before DB writes:
  `cp opinions.db opinions.db.bak-pre-<batch>-2026-05-27`.

## Git / release
- Branch `main`, HEAD **cf1c3af**. origin/main was pushed to `9ddaa2f` earlier; **commits since then are unpushed**: `4109c02`, `6f5d5b7`, `17ac9ef`, `cf1c3af`, plus this handoff/TODO commit. Push when the user OKs (public repo `jet52/ndcourts-mcp`).
- **Public release zip is STALE** — predates this session's corrections (Berger/McKinnon, the 8 juvenile merges, Klose, the 4,444-row judges normalization, volume-date fixes, 38 cite-dups, 149 docket recoveries). Regenerate via `scripts/make_release.sh --publish` when the user wants the public DB current.

## ★ Priority TODOs (full text in TODO-validation.md top)
1. **Docket completeness:** recover empty `docket_number` (1997+ = 465 recoverable) by **scanning each opinion BODY** for the caption docket + archive source-path + court PDF (reuse the `fix-docket-neutral-cite-2026-05-27` cross-validation method); normalize 4,910 blank-string dockets → NULL.
2. **`~/code/ctrack-fetch`:** `node ctrack-fetch.js` downloads authoritative ND Supreme Court opinion PDFs by docket from the cTrack portal — fetch court PDFs where we lack one (`pdfs/<year>/...`). Depends partly on #1 (needs dockets).

## What this PM session did (all committed)
1. **Compressed 84 backup DBs** 87 GB → 40 GB (zstd, in place).
2. **Court-archive pairing audit** — added report-only `fix_archive_pairings --reporter court-archive` (page-cardinality rule). Fixed **Berger/Goetz** mispairing (`court-archive/465/900255.htm` → Berger oid 20487); merged **McKinnon dup** 20472→7827.
3. **Post-1997 no-cite tail 11 → 3** — merged 8 anonymized juvenile/mental-health CL double-ingest dups into their neutral-cited CONFIDENTIAL twins (matched by child initials + date); reclassified 3 CA-docket summary-affirmance stubs (Ernst/In re Nb/In re Knh) to **Court of Appeals**. The 3 remaining are correctly cite-less COA.
4. **Filed acquired imagery** — N.D. Reports bound vols **4,5,6,8,11,12,15,25,26,46** → `N.D./<vol>/_bound-volume.pdf` (refs set now 1–21,23–27,34,41,44,46,47 = 31 vols); registered 8 N.W.2d shared-page photos as `NW-image` sources, incl. **789 N.W.2d 731 Table** (verified Delaney+Hoffner share it). Un-imaged inventory: `triage/shared-page-no-image-2026-05-27.md`.
5. **Two-column mis-extraction sweep** — fixed **Klose 2003 ND 39** (corrupted markdown was the nominal primary; served text was already the clean `NW2d/657/276.md` → repointed `source_reporter`/`source_path` to NW2d). Neset 1998 ND 206 already safe.
6. **Judges OCR normalization** — `triage/normalize_judges_ocr_2026-05-27.py`: 569 garble tokens → 32 canonical justices, **4,444 rows**. **255 quarantined** (`triage/judges-ocr-doubtful-2026-05-27.md`).
7. **`volume_date_check` detector** (new, `ndcourts_mcp/volume_date_check.py`) — 29 flags → **18 fixed** (8 dates incl. the swapped *Queen v. Martel* pair and *Schnellbach* 2007→2017; 11 stray wrong-era cite drops), **11 quarantined**.
8. **Citation-format scan** — removed 38 period-formatted neutral-cite duplicates (`2003 N.D. 144`→already-present `2003 ND 144`). Corpus citation formatting otherwise clean.
9. **Docket scan** — recovered **149** real dockets that had a neutral cite stored in the docket field; **7 quarantined**. All other docket formatting clean (era-consistent, no junk).

## Quarantine files awaiting 2nd-source / human review
- `triage/judges-ocr-doubtful-2026-05-27.md` — 255 tokens (VandeWalle fragments `Walle`/`Vande`, abbreviations `Dist`/`Place`, short-name garbles, real surnames that may be surrogate district judges).
- `triage/volume-date-quarantine-2026-05-27.md` — 11 (mostly pre-1953 rows whose date is likely wrong but not recoverable from served text).
- `triage/docket-neutral-cite-quarantine-2026-05-27.md` — 7 (source/body disagree or unrecoverable).

## Reusable detectors/tools built this session
- `ndcourts_mcp/volume_date_check.py` — report-only; **strong candidate to wire into the invariants dashboard**.
- `fix_archive_pairings --reporter court-archive` — report-only page-cardinality audit.
- `triage/normalize_judges_ocr_2026-05-27.py`, `triage/normalize`-style throwaways.

## Conventions / gotchas
- **Surrogate judges (IMPORTANT, in memory `feedback_surrogate_judges`):** justices appear in opinions OUTSIDE their elected term — district judges sit by assignment *before* joining (Tufte sat in a 2016 case pre-2017 term); retired justices keep serving *after* (finishing tenure cases / filling in for the disqualified). So `justices.py` start/end are NOT hard bounds; don't drop body-named justices on date, and don't "correct" tenures from authored-opinion spans. To find name errors, look for rare names edit-distance-close to a real justice (OCR typos) vs. legitimate surrogate district judges. `justices.py` does have real date errors (Paulson end →1983, Levine start →1985, etc.) but fixing them needs the user's domain confirmation — left untouched.
- **Shared N.W.2d "Table" pages:** multiple N.D.R.App.P. 35.1 summary dispositions share one reporter page; a shared parallel cite is NOT contamination — the **docket** is the discriminator (Ellis/Reimers, Berger/Goetz, Delaney/Hoffner).
- **After `merge_pair`, run `python -m ndcourts_mcp.align_primary_source --apply`** (primary `opinion_sources` flag can mismatch `opinions.source_reporter`).
- **Deleting a `citations` row can orphan its `is_primary` flag** → reassign primary to a surviving cite (hit in the volume-date batch; `citation_single_primary_per_opinion` invariant catches it).
- **git `index.lock` transient race** — the user's shell prompt/statusline runs `git` and briefly locks the index; if a commit fails on the lock, just retry (no stuck process).
- Scraper **misfiles by name** — trust the cite/docket INSIDE the document, not the filename/DB label.
- **Audit methodology (user-endorsed):** build a detector / stratified-sample → find an error pattern → **fix the clear ones, quarantine the ambiguous** for 2nd-source review; errors are era/source-specific.

## Brainstormed audit roadmap (not yet built)
Highest-leverage next detectors after volume↔date (done): **text_content ↔ primary-source-file integrity** (catches Klose-class primary-pointer lies), **case_name ↔ body-caption consistency** (catches Berger-in-Goetz wrong-pairings), era-aware **source-divergence sweep** (extend `multisource_diff`), and a **field-validity battery**. Source acquisition: re-extract the 1,043 modern ND-only court PDFs for an independent check; N.D. Reports bound images vols 48–79; reconcile ~120 un-ingested NW2d `.md`.

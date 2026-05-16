"""§6 duplicate-row merge engine.

CourtListener double-ingested many pre-Westlaw opinions under two
cluster_ids: a parties caption ("Loe v. Ovind", high cluster_id, CL
mis-defaulted author, full panel in `judges`, 0 inbound cites) and a
matter caption ("In re Estate of Brudevig", low cluster_id, correct
per-opinion author, thin `judges`, the inbound citations). Same cite,
same date, near-identical text. They are ONE opinion.

`merge_pair` collapses drop → keep best-of-breed:
  * keep.case_name  := canonical_name (caller-supplied, human-reviewed)
  * keep.judges     := the fuller of the two panels
  * keep.author     := keep's own; fall back to drop only if keep empty
  * text_content    := UNTOUCHED (the post-merge Westlaw receive re-run
                       installs the authoritative bound text; this pass
                       only dedups + re-points, never rewrites opinion
                       text — keeps the scope clean and reversible)
  * every opinion-referencing row (citations, opinion_sources,
    text_citations, cited_by both directions, changelog, review_flags,
    quality_scores, validation_status, westlaw_requests,
    cite_extract_progress, duplicate_candidates) re-pointed drop → keep
    with constraint-aware dedup; self-cites dropped
  * opinions row `drop` deleted (FTS stays correct via the AD/AU
    triggers; no manual FTS surgery)

Every mutation is logged to changelog under the batch; a final
log_provenance row records the run with a revert recipe. Snapshot +
invariants + dry-run discipline is the caller's responsibility (the
__main__ driver enforces dry-run default).
"""

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

from .db import DEFAULT_DB_PATH, get_connection, log_change, log_provenance
from .multisource_diff import jaccard, normalize_words, shingles

BATCH = f"section6-dedup-{date.today().isoformat()}"

# Two rows sharing a cite+date are the same opinion only if their text
# agrees this closely; below this they are distinct opinions on a
# shared reporter page and must NOT be merged.
_DUP_FLOOR = 0.55


def _panel_len(j: str | None) -> int:
    return len(re.findall(r"[A-Za-z]+", j or ""))


def _canonical_name(matter_name: str) -> str:
    """Conservative: only the unambiguous probate transform
    'In Re X's Estate' / 'In Re Estate of X' -> 'Estate of X' (current
    ND Supreme Court style). Every other matter caption is preserved
    verbatim — dedup must not impose a regex-guessed caption on
    juvenile/guardianship/will/disciplinary matters; authoritative
    re-captioning of those is a separate human pass."""
    s = matter_name.strip()
    m = re.match(r"In Re\s+(.+?)'s Estate$", s, re.I)
    if m:
        return f"Estate of {m.group(1).strip()}"
    m = re.match(r"In Re\s+Estate of\s+(.+)$", s, re.I)
    if m:
        return f"Estate of {m.group(1).strip()}"
    return s


def _dedup_simple(conn, table, col, keep, drop):
    """Re-point `col` drop->keep for a table with no uniqueness
    constraint (citations, opinion_sources, changelog)."""
    conn.execute(f"UPDATE {table} SET {col}=? WHERE {col}=?", (keep, drop))


def _repoint_unique(conn, table, col, keep, drop, uniq_cols):
    """Re-point drop->keep, deleting drop rows that would violate
    uniq_cols against an existing keep row."""
    others = ", ".join(c for c in uniq_cols if c != col)
    where_other = " AND ".join(
        f"d.{c}=k.{c}" for c in uniq_cols if c != col) or "1=1"
    conn.execute(
        f"DELETE FROM {table} WHERE {col}=? AND EXISTS "
        f"(SELECT 1 FROM {table} k WHERE k.{col}=? "
        f"AND {where_other.replace('d.', table + '.')})",
        (drop, keep))
    conn.execute(f"UPDATE {table} SET {col}=? WHERE {col}=?", (keep, drop))


def _move_pk_table(conn, table, keep, drop):
    """opinion_id is PK: keep keep's row; move drop's only if keep
    has none."""
    has_keep = conn.execute(
        f"SELECT 1 FROM {table} WHERE opinion_id=?", (keep,)).fetchone()
    if has_keep:
        conn.execute(f"DELETE FROM {table} WHERE opinion_id=?", (drop,))
    else:
        conn.execute(
            f"UPDATE {table} SET opinion_id=? WHERE opinion_id=?",
            (keep, drop))


def _fix_single_primary(conn, table, keep):
    rows = conn.execute(
        f"SELECT id, is_primary FROM {table} WHERE opinion_id=? "
        f"ORDER BY is_primary DESC, id", (keep,)).fetchall()
    if not rows:
        return
    conn.execute(f"UPDATE {table} SET is_primary=0 WHERE opinion_id=?",
                 (keep,))
    conn.execute(f"UPDATE {table} SET is_primary=1 WHERE id=?",
                 (rows[0]["id"],))


def merge_pair(conn, keep: int, drop: int, canonical_name: str,
               apply: bool, batch: str = BATCH) -> dict:
    k = conn.execute("SELECT case_name, judges, author FROM opinions "
                      "WHERE id=?", (keep,)).fetchone()
    d = conn.execute("SELECT case_name, judges, author FROM opinions "
                      "WHERE id=?", (drop,)).fetchone()
    if k is None or d is None:
        raise SystemExit(f"merge_pair: missing row keep={keep} drop={drop}")

    new_judges = (d["judges"] if _panel_len(d["judges"])
                  > _panel_len(k["judges"]) else k["judges"])
    new_author = k["author"] or d["author"]

    plan = {
        "keep": keep, "drop": drop,
        "name": f'{k["case_name"]!r} -> {canonical_name!r}',
        "judges": f'{k["judges"]!r} -> {new_judges!r}',
        "author": f'{k["author"]!r} -> {new_author!r}',
    }
    if not apply:
        return plan

    # --- re-point every opinion-referencing table ---
    for tbl, col in (("citations", "opinion_id"),
                     ("opinion_sources", "opinion_id"),
                     ("changelog", "opinion_id")):
        _dedup_simple(conn, tbl, col, keep, drop)
    _repoint_unique(conn, "text_citations", "opinion_id", keep, drop,
                    ["opinion_id", "normalized"])
    # cited_by: both directions, drop self-cites, respect the unique pair
    conn.execute("DELETE FROM cited_by WHERE cited_opinion_id=? "
                 "AND citing_opinion_id=?", (drop, keep))
    conn.execute("DELETE FROM cited_by WHERE cited_opinion_id=? "
                 "AND citing_opinion_id=?", (keep, drop))
    for col, other in (("cited_opinion_id", "citing_opinion_id"),
                       ("citing_opinion_id", "cited_opinion_id")):
        conn.execute(
            f"DELETE FROM cited_by WHERE {col}=? AND EXISTS "
            f"(SELECT 1 FROM cited_by c WHERE c.{col}=? "
            f"AND c.{other}=cited_by.{other})", (drop, keep))
        conn.execute(f"UPDATE cited_by SET {col}=? WHERE {col}=?",
                     (keep, drop))
    conn.execute("DELETE FROM cited_by WHERE cited_opinion_id="
                 "citing_opinion_id")

    for tbl in ("review_flags", "quality_scores", "validation_status",
                "westlaw_requests", "cite_extract_progress"):
        _move_pk_table(conn, tbl, keep, drop)

    # duplicate_candidates: resolve the pair, re-point stragglers
    conn.execute(
        "UPDATE duplicate_candidates SET reviewed=1, resolved_as='merged', "
        "reviewed_at=strftime('%Y-%m-%dT%H:%M:%S','now') "
        "WHERE (opinion_a=? AND opinion_b=?) OR (opinion_a=? AND "
        "opinion_b=?)", (keep, drop, drop, keep))
    for col in ("opinion_a", "opinion_b"):
        other = "opinion_b" if col == "opinion_a" else "opinion_a"
        conn.execute(
            f"DELETE FROM duplicate_candidates WHERE {col}=? AND "
            f"({other}=? OR EXISTS (SELECT 1 FROM duplicate_candidates c "
            f"WHERE c.{col}=? AND c.{other}=duplicate_candidates.{other}))",
            (drop, keep, keep))
        conn.execute(
            f"UPDATE duplicate_candidates SET {col}=? WHERE {col}=?",
            (keep, drop))
    conn.execute("DELETE FROM duplicate_candidates WHERE opinion_a="
                 "opinion_b")

    _fix_single_primary(conn, "citations", keep)
    _fix_single_primary(conn, "opinion_sources", keep)

    # --- best-of-breed metadata on the survivor; text untouched ---
    if canonical_name != k["case_name"]:
        log_change(conn, batch, keep, "case_name", k["case_name"],
                   canonical_name, authority=f"§6 merge drop={drop}")
    if new_judges != k["judges"]:
        log_change(conn, batch, keep, "judges", k["judges"], new_judges,
                   authority=f"§6 merge drop={drop}")
    if new_author != k["author"]:
        log_change(conn, batch, keep, "author", k["author"], new_author,
                   authority=f"§6 merge drop={drop}")
    conn.execute(
        "UPDATE opinions SET case_name=?, judges=?, author=? WHERE id=?",
        (canonical_name, new_judges, new_author, keep))

    # Attribute the merge-audit row to the SURVIVOR: a changelog row
    # keyed to `drop` would itself re-introduce an FK reference to the
    # row we are about to delete (changelog.opinion_id -> opinions.id,
    # NO ACTION).
    log_change(conn, batch, keep, "merge.absorbed",
               f'oid {drop} {d["case_name"]!r}', None,
               authority=f"§6 duplicate-row merge: {drop} -> {keep}")
    conn.execute("DELETE FROM opinions WHERE id=?", (drop,))
    return plan


def _jac(conn, a: int, b: int) -> float:
    ta = conn.execute("SELECT text_content FROM opinions WHERE id=?",
                       (a,)).fetchone()[0] or ""
    tb = conn.execute("SELECT text_content FROM opinions WHERE id=?",
                       (b,)).fetchone()[0] or ""
    return jaccard(shingles(normalize_words(ta)),
                   shingles(normalize_words(tb)))


def _build_pairs(conn) -> tuple[list, list]:
    """Today's 46 §6 candidates from the receive/clearwins triage:
    AMBIGUOUS cites with exactly two same-date NW2d rows, minus the
    16 already resolved this round.

    keep = the row carrying inbound cited_by edges (the established
    opinion other cases reference); drop = the cited_by=0 CL re-ingest.
    Tie on cited_by -> keep the lower cluster_id (original ingest).
    A pair only merges if text jaccard >= _DUP_FLOOR; otherwise it is
    two distinct opinions on a shared page -> flagged, never merged.
    Returns (clean_merges, flagged)."""
    done = {9208, 9209, 10043, 10044, 9241, 12694}
    cw = set()
    cwf = Path("triage/westlaw-queue-clearwins-2026-05-16.tsv")
    for ln in cwf.read_text().splitlines():
        if ln.startswith("CLEAR_WIN"):
            m = re.search(r"oid=(\d+)", ln)
            if m:
                cw.add(int(m.group(1)))

    def clean_cite(c):
        return re.sub(r"\s*\([^)]*\)\s*$", "",
                      re.sub(r"\s+", " ", c.strip())).strip()

    seen, clean, flagged = set(), [], []
    rep = Path("triage/westlaw-receive-2026-05-16.tsv").read_text()
    for line in rep.splitlines():
        f = line.split("\t")
        if f[0] != "AMBIGUOUS":
            continue
        cc = clean_cite(f[1])
        if cc in seen:
            continue
        seen.add(cc)
        cs = conn.execute(
            "SELECT o.id, o.case_name cn, o.cluster_id cl, "
            "(SELECT COUNT(*) FROM cited_by WHERE cited_opinion_id=o.id) cb "
            "FROM citations ci JOIN opinions o ON o.id=ci.opinion_id "
            "WHERE ci.citation=? ORDER BY o.id", (cc,)).fetchall()
        ids = {r["id"] for r in cs}
        if ids & (cw | done) or len(cs) != 2:
            continue
        a, b = cs
        # keep = more inbound citations; tie -> lower cluster_id
        if (a["cb"], -(a["cl"] or 0)) >= (b["cb"], -(b["cl"] or 0)):
            keep, drop = a, b
        else:
            keep, drop = b, a
        j = _jac(conn, keep["id"], drop["id"])
        if j < _DUP_FLOOR:
            flagged.append((cc, keep["id"], keep["cn"], drop["id"],
                            drop["cn"],
                            f"text jaccard {j:.2f} < {_DUP_FLOOR} — "
                            f"likely DISTINCT opinions on a shared page"))
            continue
        clean.append((cc, keep["id"], keep["cn"], drop["id"], drop["cn"]))
    return clean, flagged


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    conn = get_connection(args.db)
    clean, flagged = _build_pairs(conn)
    out = ["kind\tcite\tkeep\tdrop\tname_old->canonical\tdetail"]
    for cc, keep, kn, drop, dn in clean:
        canon = _canonical_name(kn)
        p = merge_pair(conn, keep, drop, canon, apply=args.apply)
        out.append(f"MERGE\t{cc}\t{keep}\t{drop}\t{kn!r} -> {canon!r}\t"
                   f'parties={dn!r}; {p["judges"]}; {p["author"]}')
    for cc, ai, an, bi, bn, why in flagged:
        out.append(f"NEEDS_DECISION\t{cc}\t{ai}\t{bi}\t"
                   f"{an!r} | {bn!r}\t{why}")
    rpt = Path("triage") / f"{BATCH}.tsv"
    rpt.write_text("\n".join(out), encoding="utf-8")
    if args.apply:
        log_provenance(
            conn, operation="section6_dedup",
            command="python -m ndcourts_mcp.merge_opinions --apply",
            rows_affected=len(clean),
            notes=(f"batch {BATCH}; merged {len(clean)} §6 duplicate "
                   f"pairs (pilot: today's 46-queue clean subset), "
                   f"{len(flagged)} left NEEDS_DECISION; revert via "
                   f"snapshot restore (row deletions are not "
                   f"changelog-revertible)"))
        conn.commit()
    print(f"=== §6 dedup: {'APPLIED' if args.apply else 'DRY RUN'} "
          f"(batch {BATCH}) ===")
    print(f"  clean merges     {len(clean)}")
    print(f"  needs_decision   {len(flagged)}")
    print(f"  report -> {rpt}")
    conn.close()


if __name__ == "__main__":
    main()

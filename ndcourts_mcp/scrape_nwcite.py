"""Scrape the court-sourced N.W.2d citation index at archive.ndcourts.gov.

`/opinions/cite/NWcite.htm` indexes N.W.2d volumes 139-925, each linking
to a per-volume page that lists opinions by reporter page, linking to the
court's own opinion HTML at `/court/opinions/<id>.htm`. This is a
court-sourced text — second only to the bound Westlaw N.D. Reports in
authority — and it is the missing PRE-1997 path that closes most of the
1953-1996 single-source gap (TODO-validation.md §2).

Scope reality (discovered, not assumed): `/court/opinions/<id>.htm`
serves only the OLDER opinions. Recent volumes' links 404 ("resource
... has been removed") because those opinions live in the modern
ndcourts.gov system already covered by scrape_archive / merge_nd_metadata.
The scraper detects the removed-resource sentinel and records those as
`not_in_archive` rather than erroring — the valuable yield is the
pre-1997 volumes where the HTML resolves.

This module is SCRAPE-ONLY. It writes a parallel court-sourced archive to
~/refs/nd/opin/court-archive/<nw2d-vol>/<id>.{htm,wpd,pdf} and a per-volume
manifest. Ingest + cross-check against existing rows is Phase 2b
(separate, so the download — which is slow and polite-rate-limited — is
decoupled from DB mutation).

Usage:
  python -m ndcourts_mcp.scrape_nwcite --list
  python -m ndcourts_mcp.scrape_nwcite --volume 139
  python -m ndcourts_mcp.scrape_nwcite --all [--max-volumes N] [--start-vol V]
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
from pathlib import Path

import httpx

from .db import DEFAULT_DB_PATH, get_connection, log_provenance

BASE_URL = "https://archive.ndcourts.gov"
COURT_ARCHIVE_DIR = Path.home() / "refs" / "nd" / "opin" / "court-archive"
REFS_ROOT = Path.home() / "refs" / "nd" / "opin"
NWCITE_INDEX = f"{BASE_URL}/opinions/cite/NWcite.htm"

REQUEST_DELAY = 0.3  # seconds; polite to a government archive

# A removed/relocated opinion returns this short body instead of a 404.
_GONE_SENTINEL = "resource you are looking for has been removed"

_VOL_LINK_RE = re.compile(r'href="/opinions/cite/(\d+)\.htm"')

# Volume-page entry. Two observed paren formats:
#   "(N.D. 1965)"     — older, year only, no neutral cite
#   "(2019 ND 90)"    — newer, carries a neutral cite
_ENTRY_RE = re.compile(
    r'<a href="/court/opinions/(\d+)\.htm">\s*'
    r'<large>\s*(\d+)\s*</large>\s*-\s*'
    r'(.+?)\s*</a>\s*<small>\s*\(([^)]+)\)',
    re.DOTALL | re.IGNORECASE,
)
_NEUTRAL_IN_PARENS = re.compile(r'(\d{4})\s+ND\s+(\d+)')
_YEAR_IN_PARENS = re.compile(r'N\.?D\.?\s+(\d{4})')
_DOC_HREF_RE = re.compile(r'href="([^"]+\.(?:wpd|pdf|doc))"', re.IGNORECASE)


def _fetch(client: httpx.Client, url: str) -> tuple[int, str]:
    time.sleep(REQUEST_DELAY)
    resp = client.get(url, follow_redirects=True, timeout=30)
    return resp.status_code, resp.text


def list_volumes(client: httpx.Client) -> list[int]:
    code, text = _fetch(client, NWCITE_INDEX)
    if code != 200:
        raise RuntimeError(f"NWcite index returned HTTP {code}")
    vols = sorted({int(v) for v in _VOL_LINK_RE.findall(text)})
    return vols


def parse_volume_page(text: str, volume: int) -> list[dict]:
    """Parse a `<vol> N.W.2d` page into opinion entries."""
    entries: list[dict] = []
    for m in _ENTRY_RE.finditer(text):
        oid, page, case_name, paren = m.groups()
        case_name = re.sub(r"\s+", " ", html.unescape(case_name)).strip()
        paren = paren.strip()
        neutral = None
        year = None
        nm = _NEUTRAL_IN_PARENS.search(paren)
        if nm:
            neutral = f"{nm.group(1)} ND {int(nm.group(2))}"
            year = int(nm.group(1))
        else:
            ym = _YEAR_IN_PARENS.search(paren)
            if ym:
                year = int(ym.group(1))
        entries.append({
            "archive_oid": oid,
            "nw_cite": f"{volume} N.W.2d {int(page)}",
            "nw_volume": volume,
            "nw_page": int(page),
            "neutral_cite": neutral,
            "year": year,
            "case_name": case_name,
            "opinion_url": f"{BASE_URL}/court/opinions/{oid}.htm",
        })
    return entries


def _grab_linked_docs(
    client: httpx.Client, page_html: str, vol_dir: Path, oid: str,
) -> list[str]:
    """Fetch any WordPerfect/PDF/doc files linked from the opinion page.
    Returns saved relative paths. Pre-1997 court HTML is usually text-only;
    this captures the exceptions where the court linked a source document."""
    saved: list[str] = []
    for href in set(_DOC_HREF_RE.findall(page_html)):
        url = href if href.startswith("http") else f"{BASE_URL}{href if href.startswith('/') else '/' + href}"
        ext = href.rsplit(".", 1)[-1].lower()
        try:
            time.sleep(REQUEST_DELAY)
            r = client.get(url, follow_redirects=True, timeout=30)
            if r.status_code != 200 or not r.content:
                continue
            dest = vol_dir / f"{oid}.{ext}"
            dest.write_bytes(r.content)
            saved.append(str(dest.relative_to(REFS_ROOT)))
        except httpx.HTTPError:
            continue
    return saved


def scrape_volume(
    client: httpx.Client, volume: int, archive_dir: Path,
) -> dict:
    code, index_html = _fetch(client, f"{BASE_URL}/opinions/cite/{volume}.htm")
    if code != 200:
        return {"volume": volume, "error": f"HTTP {code}", "entries": []}

    entries = parse_volume_page(index_html, volume)
    vol_dir = archive_dir / str(volume)
    vol_dir.mkdir(parents=True, exist_ok=True)
    (vol_dir / "_index.htm").write_text(index_html, encoding="utf-8")

    counts = {"fetched": 0, "cached": 0, "not_in_archive": 0, "errors": 0,
              "docs": 0}
    for e in entries:
        oid = e["archive_oid"]
        htm_path = vol_dir / f"{oid}.htm"
        if htm_path.exists():
            body = htm_path.read_text(encoding="utf-8", errors="replace")
            e["status"] = "cached"
            counts["cached"] += 1
        else:
            try:
                hc, body = _fetch(client, e["opinion_url"])
            except httpx.HTTPError as exc:
                e["status"] = f"error: {exc}"
                counts["errors"] += 1
                continue
            if hc != 200 or _GONE_SENTINEL in body[:300].lower():
                e["status"] = "not_in_archive"
                counts["not_in_archive"] += 1
                continue
            htm_path.write_text(body, encoding="utf-8")
            e["status"] = "fetched"
            counts["fetched"] += 1

        e["source_path"] = str(htm_path.relative_to(REFS_ROOT))
        docs = _grab_linked_docs(client, body, vol_dir, oid)
        if docs:
            e["doc_paths"] = docs
            counts["docs"] += len(docs)

    manifest = {"volume": volume, "counts": counts, "entries": entries}
    (vol_dir / "_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    ap.add_argument("--archive-dir", type=Path, default=COURT_ARCHIVE_DIR)
    ap.add_argument("--list", action="store_true",
                    help="List N.W.2d volumes in the index and exit")
    ap.add_argument("--volume", type=int, help="Scrape a single volume")
    ap.add_argument("--all", action="store_true",
                    help="Scrape every volume in the index")
    ap.add_argument("--start-vol", type=int, default=0,
                    help="With --all, skip volumes below this number")
    ap.add_argument("--max-volumes", type=int,
                    help="With --all, stop after this many volumes "
                         "(bounded test runs)")
    args = ap.parse_args()

    client = httpx.Client(
        headers={"User-Agent": "ndcourts-mcp/1.0 "
                 "(ND Supreme Court opinion database; court-archive mirror)"},
        timeout=30,
    )
    try:
        vols = list_volumes(client)
        if args.list:
            print(f"{len(vols)} N.W.2d volumes: {vols[0]}-{vols[-1]}")
            print(", ".join(map(str, vols)))
            return

        if args.volume:
            targets = [args.volume]
        elif args.all:
            targets = [v for v in vols if v >= args.start_vol]
            if args.max_volumes:
                targets = targets[: args.max_volumes]
        else:
            ap.error("Specify --list, --volume N, or --all")

        archive_dir = args.archive_dir
        archive_dir.mkdir(parents=True, exist_ok=True)
        totals = {"fetched": 0, "cached": 0, "not_in_archive": 0,
                  "errors": 0, "docs": 0}
        for v in targets:
            man = scrape_volume(client, v, archive_dir)
            if "error" in man:
                print(f"vol {v}: {man['error']}")
                continue
            c = man["counts"]
            for k in totals:
                totals[k] += c[k]
            print(f"vol {v:>3}: {len(man['entries']):>3} entries  "
                  f"fetched={c['fetched']} cached={c['cached']} "
                  f"not_in_archive={c['not_in_archive']} "
                  f"errors={c['errors']} docs={c['docs']}", flush=True)

        print(f"\nTOTAL  fetched={totals['fetched']} cached={totals['cached']} "
              f"not_in_archive={totals['not_in_archive']} "
              f"errors={totals['errors']} docs={totals['docs']}")

        conn = get_connection(args.db)
        log_provenance(
            conn,
            operation="scrape_nwcite",
            command="python -m ndcourts_mcp.scrape_nwcite",
            source_paths=f"{NWCITE_INDEX} (vols {targets[0]}-{targets[-1]})",
            rows_affected=totals["fetched"],
            notes=(f"court-sourced NW-cite mirror to court-archive/; "
                   f"fetched={totals['fetched']} cached={totals['cached']} "
                   f"not_in_archive={totals['not_in_archive']} "
                   f"docs={totals['docs']}; scrape-only, no DB ingest "
                   f"(Phase 2b)"),
        )
        conn.commit()
        conn.close()
    finally:
        client.close()


if __name__ == "__main__":
    main()

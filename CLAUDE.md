# ndcourts-mcp

MCP server providing access to North Dakota Supreme Court opinions (1889–present).

## Architecture

- **SQLite + FTS5** for full-text and metadata search
- **FastMCP** for the MCP server
- **~/refs/opin/** contains the source data (markdown opinions + CourtListener JSON metadata)

## Data sources

Opinions live under `~/refs/opin/{reporter}/`:
- `ND/` — neutral-cite opinions (1997–present), ~14K files, markdown with ¶ markers
- `NW2d/` — North Western Reporter 2d, ~12K files with paired .json metadata from CourtListener
- `NW/` — North Western Reporter 1st series, ~6K files with paired .json metadata

JSON metadata includes: cluster_id, case_name, case_name_full, date_filed, citations (parallel), judges, docket_number, absolute_url.

Many opinions exist in multiple reporters (e.g., both ND/ and NW2d/). The ingest pipeline should deduplicate by matching parallel citations from the JSON metadata.

## Dependencies

- Python 3.12+
- fastmcp
- sqlite3 (stdlib)

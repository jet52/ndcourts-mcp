# ndcourts-mcp

MCP server providing access to North Dakota Supreme Court opinions (1889–present). Built on SQLite with FTS5 full-text search, served via FastMCP.

## Current Capabilities

### MCP Tools (9 tools)

| Tool | Purpose |
|------|---------|
| `lookup_opinion` | Retrieve opinion by any citation (neutral, N.W.2d, N.W.) |
| `get_opinion_text` | Read opinion text in paginated chunks |
| `get_opinion_metadata` | Metadata-only lookup (no text) |
| `search_opinions` | Full-text search with date/author filters |
| `list_opinions_by_date` | Browse opinions by date range |
| `get_database_stats` | Corpus summary, top authors, by-decade counts |
| `get_voting_record` | Justice votes on a specific opinion |
| `get_justice_stats` | Authorship count, dissent rate for a justice |
| `search_by_case_type` | Filter by case type (criminal, civil, etc.) |

### Database

- **20,382 opinions** from 1890–2026
- **33,217 citation records** linking neutral cites, N.W.2d, and N.W. citations
- **Full-text search** via SQLite FTS5 with porter stemming
- **Changelog table** for auditable, revertible corrections

### Data Sources

| Source | Coverage | Data |
|--------|----------|------|
| CourtListener (NW) | ~6,000 opinions, 1890–1997 | Text + JSON metadata (case name, date, judges, citations) |
| CourtListener (NW2d) | ~12,200 opinions, 1941–present | Text + JSON metadata |
| ndcourts.gov scrape (ND) | ~7,150 opinions, 1997–present | Markdown text with ¶ markers |
| ndcourts.gov metadata | ~7,150 opinions, 1997–present | Case name, date, author, case type, highlight, voting record, justice panel, unanimity, ndcourts.gov URL |

### Data Corrections Applied

5,900+ corrections across 10 batches, all logged in the `changelog` table. See [CHANGELOG-data.md](CHANGELOG-data.md) for details.

- Case normalization (ALL CAPS → title case)
- OCR misread consolidation (Birdzell, Bronson, Bruce, Burke, Christianson, Fisk, etc.)
- Per curiam detection
- Full-name → last-name normalization for surrogates
- Manual review corrections via interactive tool

## Setup

```bash
# Create venv and install
python3 -m venv .venv
.venv/bin/pip install -e .

# Build the database (requires ~/refs/opin/)
.venv/bin/python3 -m ndcourts_mcp.ingest --rebuild

# Merge ndcourts.gov metadata (requires ~/refs/nd/opin/)
.venv/bin/python3 -m ndcourts_mcp.merge_nd_metadata

# Apply corrections
.venv/bin/python3 -m ndcourts_mcp.cleanup apply
```

### Claude Code Integration

Add to `~/.mcp.json`:

```json
{
  "mcpServers": {
    "ndcourts": {
      "type": "stdio",
      "command": "/path/to/.venv/bin/python",
      "args": ["-m", "ndcourts_mcp.server"],
      "cwd": "/path/to/ndcourts-mcp"
    }
  }
}
```

## CLI Tools

| Command | Purpose |
|---------|---------|
| `python -m ndcourts_mcp.ingest [--rebuild]` | Ingest opinions from ~/refs/opin/ |
| `python -m ndcourts_mcp.merge_nd_metadata` | Merge ndcourts.gov JSON metadata |
| `python -m ndcourts_mcp.cleanup apply [--dry-run]` | Apply pending corrections |
| `python -m ndcourts_mcp.cleanup revert <batch>` | Revert a correction batch |
| `python -m ndcourts_mcp.cleanup log` | Show changelog summary |
| `python -m ndcourts_mcp.review [--author X] [--min-count N] [--flagged]` | Interactive author review |

## Data Quality: Known Issues and Remaining Cleanup

### Author field (~580 opinions still need attention)

**Junk words as authors (~340 opinions).** CourtListener's parser extracted words from opinion text as "judges" for the older NW opinions. The author was derived from this bad data. Common examples: "Being", "Been", "Dist", "Any", "Action", "Account", "Below", "First", "Other". These should be set to NULL, but many can be recovered by detecting "LastName, J." lines in the opinion text using the review tool.

**Root cause:** Old NW opinions include a disqualification boilerplate at the end, e.g.:
> FISK, J., disqualified, and Hon, CHAS. A. POLLOCK, judge of the Third judicial district, sat by request.

CourtListener's parser treated the entire line as a comma-separated judge list, producing entries like "Chas", "Hon", "Pollock", "Third", "Request", "Dist".

**Single-count OCR noise (~140 opinions).** One-off garbled author values. Low priority — most can be auto-detected from text or set to NULL.

**"Chas" (8 opinions).** Fragment of "Chas. A. Pollock" or "Chas. Fisk" (Charles). Reviewed and corrected via manual review tool (2026-04-04).

### Judges field

**Pre-1997 judges data is largely unusable.** Same CourtListener parsing issue as the author field — the "judges" value is OCR fragments from opinion text, not a clean list of participating justices.

**Post-1997 opinions have clean data** from the ndcourts.gov metadata merge (`all_justices` and `voting_record` fields).

**Potential fix:** For opinions where we have the court composition dates (from `justices.py`), we could infer the default panel and note substitutions from disqualification lines in the text.

### Dates

**~5 opinions with placeholder dates.** ND-sourced opinions where the date couldn't be extracted and defaulted to YYYY-01-01.

### Case names

**Pre-1997 case names from CourtListener are generally good.** Some have OCR artifacts but are readable.

**Post-1997 case names from ndcourts.gov are clean.**

### Duplicate detection

Some opinions may exist under different citations without being linked. The ingest pipeline deduplicates by CourtListener `cluster_id` and by matching parallel citations, but edge cases may remain.

## Proposed: Interactive Data Browser

A terminal or web-based tool for browsing and spot-checking the database:

- Browse by date range, author, case type, or citation
- Side-by-side comparison of our data vs. source files
- Bulk export of citations for Westlaw Quick Check validation
- Ingest corrected data from Westlaw downloads to validate and fix OCR errors

### Westlaw Validation Workflow

1. Export a Word document with a list of citations from the database
2. Upload to Westlaw Quick Check — it resolves all citations and provides download links
3. Download the clean Westlaw opinion text
4. Diff against our OCR text to identify and correct errors
5. Use Westlaw metadata (case name, date, author, judges) to validate our fields

This is particularly valuable for the pre-1920 opinions where OCR quality is worst.

## Reference Files

| File | Purpose |
|------|---------|
| `ndcourts_mcp/justices.py` | All 52 elected justices (1889–present) with service dates |
| `CHANGELOG-data.md` | Human-readable log of every correction batch |

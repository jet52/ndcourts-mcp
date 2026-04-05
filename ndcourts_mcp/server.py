"""MCP server for North Dakota Supreme Court opinions."""

from pathlib import Path

from fastmcp import FastMCP

from .db import DEFAULT_DB_PATH, get_connection

mcp = FastMCP(
    "ndcourts",
    instructions=(
        "North Dakota Supreme Court opinion database (1889–present). "
        "Use lookup_opinion for citation-based retrieval, search_opinions for "
        "full-text search, and get_citing_opinions to find cases that cite a given opinion."
    ),
)

DB_PATH = DEFAULT_DB_PATH


def _opinion_summary(row) -> dict:
    """Format an opinion row as a summary dict (no full text)."""
    return {
        "id": row["id"],
        "case_name": row["case_name"],
        "case_name_full": row["case_name_full"],
        "date_filed": row["date_filed"],
        "author": row["author"],
        "per_curiam": bool(row["per_curiam"]),
        "docket_number": row["docket_number"],
        "judges": row["judges"],
        "court": row["court"],
    }


def _get_citations(conn, opinion_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT citation FROM citations WHERE opinion_id = ? ORDER BY is_primary DESC",
        (opinion_id,),
    ).fetchall()
    return [r["citation"] for r in rows]


@mcp.tool()
def lookup_opinion(citation: str) -> dict:
    """Look up an opinion by any citation (neutral cite, N.W.2d, N.W., etc.).

    Returns the full opinion text, metadata, and all known citations.
    Use this when you have a specific citation to retrieve.

    Args:
        citation: A legal citation like "2024 ND 156", "585 N.W.2d 129", etc.
    """
    conn = get_connection(DB_PATH)
    try:
        row = conn.execute(
            """SELECT o.* FROM opinions o
               JOIN citations c ON c.opinion_id = o.id
               WHERE c.citation = ?""",
            (citation.strip(),),
        ).fetchone()

        if not row:
            return {"error": f"No opinion found for citation: {citation}"}

        result = _opinion_summary(row)
        result["citations"] = _get_citations(conn, row["id"])
        result["text"] = row["text_content"]
        result["absolute_url"] = row["absolute_url"]
        return result
    finally:
        conn.close()


@mcp.tool()
def search_opinions(
    query: str,
    date_from: str | None = None,
    date_to: str | None = None,
    author: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Full-text search across all opinions.

    Returns matching opinions ranked by relevance with snippets.
    Use this to find opinions on a topic, legal issue, or factual pattern.

    Args:
        query: Search terms (supports AND, OR, NOT, quoted phrases).
        date_from: Filter to opinions filed on or after this date (YYYY-MM-DD).
        date_to: Filter to opinions filed on or before this date (YYYY-MM-DD).
        author: Filter by authoring justice's last name.
        limit: Maximum results to return (default 20, max 50).
    """
    limit = min(limit, 50)
    conn = get_connection(DB_PATH)
    try:
        sql = """
            SELECT o.*, snippet(opinions_fts, 1, '>>>', '<<<', '...', 40) as snippet,
                   rank
            FROM opinions_fts
            JOIN opinions o ON o.id = opinions_fts.rowid
            WHERE opinions_fts MATCH ?
        """
        params: list = [query]

        if date_from:
            sql += " AND o.date_filed >= ?"
            params.append(date_from)
        if date_to:
            sql += " AND o.date_filed <= ?"
            params.append(date_to)
        if author:
            sql += " AND o.author LIKE ?"
            params.append(f"%{author}%")

        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()

        results = []
        for row in rows:
            result = _opinion_summary(row)
            result["citations"] = _get_citations(conn, row["id"])
            result["snippet"] = row["snippet"]
            results.append(result)

        return results
    finally:
        conn.close()


@mcp.tool()
def get_opinion_metadata(citation: str) -> dict:
    """Get metadata for an opinion without the full text.

    Lighter than lookup_opinion — use when you just need case name,
    date, author, and citations without the full text.

    Args:
        citation: A legal citation like "2024 ND 156".
    """
    conn = get_connection(DB_PATH)
    try:
        row = conn.execute(
            """SELECT o.* FROM opinions o
               JOIN citations c ON c.opinion_id = o.id
               WHERE c.citation = ?""",
            (citation.strip(),),
        ).fetchone()

        if not row:
            return {"error": f"No opinion found for citation: {citation}"}

        result = _opinion_summary(row)
        result["citations"] = _get_citations(conn, row["id"])
        result["absolute_url"] = row["absolute_url"]
        return result
    finally:
        conn.close()


@mcp.tool()
def list_opinions_by_date(
    date_from: str,
    date_to: str,
    author: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List opinions filed within a date range.

    Returns opinions in reverse chronological order.

    Args:
        date_from: Start date (YYYY-MM-DD).
        date_to: End date (YYYY-MM-DD).
        author: Optional filter by authoring justice's last name.
        limit: Maximum results (default 50, max 200).
    """
    limit = min(limit, 200)
    conn = get_connection(DB_PATH)
    try:
        sql = """SELECT * FROM opinions
                 WHERE date_filed >= ? AND date_filed <= ?"""
        params: list = [date_from, date_to]

        if author:
            sql += " AND author LIKE ?"
            params.append(f"%{author}%")

        sql += " ORDER BY date_filed DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()

        results = []
        for row in rows:
            result = _opinion_summary(row)
            result["citations"] = _get_citations(conn, row["id"])
            results.append(result)

        return results
    finally:
        conn.close()


@mcp.tool()
def get_database_stats() -> dict:
    """Get summary statistics about the opinion database.

    Returns counts, date range, and top authors.
    """
    conn = get_connection(DB_PATH)
    try:
        total = conn.execute("SELECT COUNT(*) as n FROM opinions").fetchone()["n"]
        date_range = conn.execute(
            "SELECT MIN(date_filed) as earliest, MAX(date_filed) as latest FROM opinions"
        ).fetchone()
        citations_count = conn.execute(
            "SELECT COUNT(*) as n FROM citations"
        ).fetchone()["n"]

        top_authors = conn.execute(
            """SELECT author, COUNT(*) as n FROM opinions
               WHERE author IS NOT NULL
               GROUP BY author ORDER BY n DESC LIMIT 15"""
        ).fetchall()

        by_decade = conn.execute(
            """SELECT (CAST(substr(date_filed, 1, 3) AS INTEGER) * 10) || '0s' as decade,
                      COUNT(*) as n
               FROM opinions
               GROUP BY decade ORDER BY decade"""
        ).fetchall()

        return {
            "total_opinions": total,
            "total_citations": citations_count,
            "earliest": date_range["earliest"],
            "latest": date_range["latest"],
            "top_authors": [
                {"author": r["author"], "count": r["n"]} for r in top_authors
            ],
            "by_decade": [
                {"decade": r["decade"], "count": r["n"]} for r in by_decade
            ],
        }
    finally:
        conn.close()


def main():
    mcp.run()


if __name__ == "__main__":
    main()

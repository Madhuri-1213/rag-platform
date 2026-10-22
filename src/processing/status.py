from src.common.db import get_conn


def get_papers_to_process(limit: int) -> list[dict]:
    """Papers whose raw PDF is stored but not yet chunked (status = 'ingested')."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT paper_key, arxiv_id, version, title, authors, published_at, bronze_pdf_path
            FROM papers
            WHERE status = 'ingested'
            ORDER BY ingested_at, paper_key
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "paper_key": r[0],
            "arxiv_id": r[1],
            "version": r[2],
            "title": r[3],
            "authors": r[4] or [],
            "published_at": r[5].isoformat() if r[5] else None,
            "bronze_pdf_path": r[6],
        }
        for r in rows
    ]


def set_status(paper_keys: list[str], status: str) -> None:
    """Move papers to a new status: 'parsed' on success, 'failed' on error."""
    if not paper_keys:
        return
    with get_conn() as conn:
        conn.execute(
            "UPDATE papers SET status = %s WHERE paper_key = ANY(%s)", (status, paper_keys)
        )
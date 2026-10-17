from psycopg.types.json import Jsonb

from src.common.db import get_conn

INSERT_SQL = """
INSERT INTO papers (
  paper_key, arxiv_id, version, title, authors, abstract,
  published_at, updated_at, bronze_pdf_path, bronze_json_path
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (paper_key) DO NOTHING
"""


def existing_paper_keys(keys: list[str]) -> set[str]:
    """Which of these keys are already registered? Use it to skip re-downloading."""
    if not keys:
        return set()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT paper_key FROM papers WHERE paper_key = ANY(%s)", (keys,)
        ).fetchall()
    return {r[0] for r in rows}


def register_papers(papers: list[dict]) -> int:
    """Insert papers into the registry. Returns how many were NEW.

    Each dict needs: paper_key, arxiv_id, version, title, authors (list),
    abstract, published, updated, bronze_pdf_path, bronze_json_path.
    Re-registering a paper_key that already exists does nothing (idempotent).
    """
    inserted = 0
    with get_conn() as conn:
        for p in papers:
            cur = conn.execute(
                INSERT_SQL,
                (
                    p["paper_key"],
                    p["arxiv_id"],
                    p["version"],
                    p["title"],
                    Jsonb(p["authors"]),
                    p["abstract"],
                    p["published"],
                    p["updated"],
                    p["bronze_pdf_path"],
                    p["bronze_json_path"],
                ),
            )
            inserted += cur.rowcount  # 1 if inserted, 0 if it already existed
    return inserted
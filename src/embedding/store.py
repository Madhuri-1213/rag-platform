"""Reading and writing the pgvector table."""
from pgvector.psycopg import register_vector

from src.common.db import get_conn

UPSERT_SQL = """
INSERT INTO chunks (
  chunk_id, paper_key, arxiv_id, version, title, section, published_at, chunk_index,
  text, text_hash, n_words, bronze_pdf_path, chunk_strategy, pipeline_version,
  embedding, embedding_model, embed_key
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (chunk_id) DO UPDATE SET
  paper_key = EXCLUDED.paper_key, arxiv_id = EXCLUDED.arxiv_id, version = EXCLUDED.version,
  title = EXCLUDED.title, section = EXCLUDED.section, published_at = EXCLUDED.published_at,
  chunk_index = EXCLUDED.chunk_index, text = EXCLUDED.text, text_hash = EXCLUDED.text_hash,
  n_words = EXCLUDED.n_words, bronze_pdf_path = EXCLUDED.bronze_pdf_path,
  chunk_strategy = EXCLUDED.chunk_strategy, pipeline_version = EXCLUDED.pipeline_version,
  embedding = EXCLUDED.embedding, embedding_model = EXCLUDED.embedding_model,
  embed_key = EXCLUDED.embed_key, is_deleted = FALSE, updated_at = now()
"""

# When a newer version of a paper exists, the older versions' chunks stop appearing in search.
RETIRE_SQL = """
UPDATE chunks c SET is_deleted = TRUE, updated_at = now()
FROM (SELECT arxiv_id, max(version) AS max_v FROM chunks GROUP BY arxiv_id) m
WHERE c.arxiv_id = m.arxiv_id AND c.version < m.max_v AND NOT c.is_deleted
"""


def connect():
    """A Postgres connection that understands the vector type."""
    conn = get_conn()
    register_vector(conn)
    return conn


def existing_embed_keys(conn, chunk_ids: list[str]) -> dict[str, str]:
    """chunk_id -> embed_key for chunks already in the table (the embedding cache)."""
    if not chunk_ids:
        return {}
    rows = conn.execute(
        "SELECT chunk_id, embed_key FROM chunks WHERE chunk_id = ANY(%s)", (chunk_ids,)
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def upsert_chunks(conn, rows: list[dict], embedding_model: str) -> int:
    """Insert or update chunks that carry an 'embedding' and an 'embed_key'."""
    params = [
        (
            r["chunk_id"], r["paper_key"], r["arxiv_id"], r["version"], r["title"], r.get("section"),
            r.get("published_at"), r["chunk_index"], r["text"], r["text_hash"], r.get("n_words"),
            r.get("bronze_pdf_path"), r.get("chunk_strategy"), r["pipeline_version"],
            r["embedding"], embedding_model, r["embed_key"],
        )
        for r in rows
    ]
    with conn.cursor() as cur:
        cur.executemany(UPSERT_SQL, params)
    return len(params)


def retire_old_versions(conn) -> int:
    """Soft-delete chunks of paper versions that have a newer version. Returns how many."""
    return conn.execute(RETIRE_SQL).rowcount
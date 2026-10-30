"""Ask the vector store a question and print the closest chunks (a sanity check).

Run inside the Airflow container:
    docker compose exec airflow-scheduler python -m src.embedding.try_search "how do reward models help reinforcement learning"
"""
import sys
import time

from src.common.config import load_settings
from src.embedding.embedder import embed_query
from src.embedding.store import connect

SQL = """
SELECT arxiv_id, version, section, title, 1 - (embedding <=> %s) AS similarity, left(text, 220)
FROM chunks
WHERE NOT is_deleted
ORDER BY embedding <=> %s
LIMIT %s
"""


def main(question: str, k: int = 5) -> None:
    settings = load_settings()
    t0 = time.perf_counter()
    q = embed_query(question, settings.embedding_model)
    t1 = time.perf_counter()
    with connect() as conn:
        rows = conn.execute(SQL, (q, q, k)).fetchall()
    t2 = time.perf_counter()
    print(f"question: {question}")
    print(f"embedding the question: {1000 * (t1 - t0):.0f} ms   database search: {1000 * (t2 - t1):.0f} ms\n")
    for arxiv_id, version, section, title, sim, text in rows:
        print(f"{sim:.3f}  {arxiv_id}v{version} | {section or '-'} | {title[:70]}")
        print(f"        {text.replace(chr(10), ' ')}")


if __name__ == "__main__":
    main(" ".join(sys.argv[1:]) or "how do verifiers improve image generation")
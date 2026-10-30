"""How accurate is the HNSW index? Compare it with exact search at several ef_search values.

Run inside the Airflow container:
    docker compose exec airflow-scheduler python -m src.embedding.ef_test

HNSW is approximate: it is fast because it can miss a true nearest neighbour. ef_search is
the dial: higher = more accurate but slower. This takes 50 random chunks as queries, finds
their true top-10 neighbours with an exact scan, and reports how many of those HNSW finds.
"""
import random
import time

from src.embedding.store import connect

K = 10
N_QUERIES = 50
EF_VALUES = [10, 20, 40, 100]
SQL = """
SELECT chunk_id FROM chunks
WHERE NOT is_deleted AND chunk_id <> %s
ORDER BY embedding <=> %s
LIMIT %s
"""


def main() -> None:
    with connect() as conn:
        ids = [r[0] for r in conn.execute("SELECT chunk_id FROM chunks WHERE NOT is_deleted").fetchall()]
        random.seed(7)
        sample = random.sample(ids, min(N_QUERIES, len(ids)))
        vectors = {
            cid: conn.execute("SELECT embedding FROM chunks WHERE chunk_id = %s", (cid,)).fetchone()[0]
            for cid in sample
        }
        print(f"{len(ids)} active chunks; {len(sample)} random queries; top-{K} neighbours\n")

        # exact answers: switch the index off so Postgres scans every vector
        conn.execute("SET enable_indexscan = off")
        started = time.perf_counter()
        exact = {cid: [r[0] for r in conn.execute(SQL, (cid, v, K)).fetchall()] for cid, v in vectors.items()}
        exact_ms = 1000 * (time.perf_counter() - started) / len(vectors)
        conn.execute("RESET enable_indexscan")
        print(f"exact scan (no index): {exact_ms:.0f} ms per query\n")

        print("ef_search | recall@10 | avg ms per query")
        for ef in EF_VALUES:
            conn.execute(f"SET hnsw.ef_search = {int(ef)}")
            hits, times = 0, []
            for cid, v in vectors.items():
                t = time.perf_counter()
                got = [r[0] for r in conn.execute(SQL, (cid, v, K)).fetchall()]
                times.append(time.perf_counter() - t)
                hits += len(set(got) & set(exact[cid]))
            recall = hits / (K * len(vectors))
            print(f"{ef:>9} | {recall:>9.3f} | {1000 * sum(times) / len(times):>8.1f}")
        conn.execute("RESET hnsw.ef_search")


if __name__ == "__main__":
    main()
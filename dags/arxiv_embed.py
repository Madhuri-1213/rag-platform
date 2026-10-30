"""Embedding DAG: gold chunks -> vectors in Postgres (pgvector).

Flow:  list_gold_files -> embed_file (one task per gold file, one at a time) -> summarize

For every chunk the DAG builds the text to embed, computes its cache key, and asks the
database which chunks already hold a vector for that exact key. Only the others are
embedded, so re-running costs almost nothing. At the end, chunks of older paper versions
are soft-deleted.
"""
import io
import time
from datetime import datetime, timedelta

from airflow.decorators import dag, task

from src.common.config import load_settings
from src.common.s3 import BUCKET, get_s3_client
from src.embedding.embedder import embed_passages
from src.embedding.store import connect, existing_embed_keys, retire_old_versions, upsert_chunks
from src.embedding.text import make_embed_key, make_embed_text

GROUP = 128  # chunks embedded and saved per step

default_args = {"retries": 2, "retry_delay": timedelta(minutes=1)}


@dag(
    dag_id="arxiv_embed",
    start_date=datetime(2026, 10, 15),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["embedding", "vectors"],
)
def arxiv_embed():

    @task
    def list_gold_files() -> list[str]:
        s3 = get_s3_client()
        keys: list[str] = []
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix="gold/chunks/"):
            keys += [o["Key"] for o in page.get("Contents", []) if o["Key"].endswith(".parquet")]
        print(f"{len(keys)} gold files")
        return sorted(keys)

    # pool "embedding" has 1 slot: one embedding job at a time keeps memory and CPU in check
    @task(pool="embedding")
    def embed_file(gold_key: str) -> dict:
        import polars as pl

        settings = load_settings()
        body = get_s3_client().get_object(Bucket=BUCKET, Key=gold_key)["Body"].read()
        rows = pl.read_parquet(io.BytesIO(body)).to_dicts()

        for r in rows:
            r["embed_text"] = (
                make_embed_text(r["title"], r["section"], r["text"]) if settings.embed_context else r["text"]
            )
            r["embed_key"] = make_embed_key(settings.embedding_model, r["embed_text"])

        started = time.perf_counter()
        with connect() as conn:
            known = existing_embed_keys(conn, [r["chunk_id"] for r in rows])
            todo = [r for r in rows if known.get(r["chunk_id"]) != r["embed_key"]]
            for i in range(0, len(todo), GROUP):
                group = todo[i : i + GROUP]
                vectors = embed_passages([r["embed_text"] for r in group], settings.embedding_model)
                for r, v in zip(group, vectors):
                    r["embedding"] = v
                upsert_chunks(conn, group, settings.embedding_model)
                conn.commit()  # progress is saved after every group
        seconds = time.perf_counter() - started

        print(f"{gold_key}: {len(rows)} chunks, {len(rows) - len(todo)} cached, {len(todo)} embedded in {seconds:.0f}s")
        return {"total": len(rows), "cached": len(rows) - len(todo), "embedded": len(todo), "seconds": round(seconds, 1)}

    @task(trigger_rule="none_failed")
    def summarize(results) -> None:
        results = list(results or [])
        total = sum(r["total"] for r in results)
        cached = sum(r["cached"] for r in results)
        embedded = sum(r["embedded"] for r in results)
        seconds = sum(r["seconds"] for r in results)
        with connect() as conn:
            retired = retire_old_versions(conn)
        rate = cached / total if total else 0.0
        speed = embedded / seconds if seconds else 0.0
        print(
            f"EMBED SUMMARY: {total} chunks, {cached} reused from the cache ({rate:.1%}), "
            f"{embedded} newly embedded ({speed:.1f} chunks/s); "
            f"{retired} chunks of older paper versions retired"
        )

    files = list_gold_files()
    results = embed_file.expand(gold_key=files)
    summarize(results)


arxiv_embed()
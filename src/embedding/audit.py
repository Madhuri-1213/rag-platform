"""Reconcile the vector table with the gold layer (are they the same set of chunks?).

Run inside the Airflow container:
    docker compose exec airflow-scheduler python -m src.embedding.audit
    docker compose exec airflow-scheduler python -m src.embedding.audit --delete-orphans

  in gold AND in the table  -> good
  in gold, not in the table -> not embedded yet (run arxiv_embed)
  in the table, not in gold -> ORPHANS: stale rows from an older pipeline version; they
                               would show up in search results. --delete-orphans removes them.
"""
import io
import sys
from collections import Counter

import polars as pl

from src.common.s3 import BUCKET, get_s3_client
from src.embedding.store import connect


def gold_chunk_ids() -> set[str]:
    s3 = get_s3_client()
    ids: set[str] = set()
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix="gold/chunks/"):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".parquet"):
                body = s3.get_object(Bucket=BUCKET, Key=obj["Key"])["Body"].read()
                ids.update(pl.read_parquet(io.BytesIO(body), columns=["chunk_id"])["chunk_id"].to_list())
    return ids


def main(delete_orphans: bool) -> None:
    gold = gold_chunk_ids()
    with connect() as conn:
        rows = conn.execute("SELECT chunk_id, is_deleted, pipeline_version, embedding_model FROM chunks").fetchall()
        table = {r[0] for r in rows}
        orphans = table - gold
        missing = gold - table

        print(f"chunks in gold:            {len(gold)}")
        print(f"rows in the vector table:  {len(rows)}  (soft-deleted: {sum(1 for r in rows if r[1])})")
        print(f"present in both:           {len(gold & table)}")
        print(f"missing from the table:    {len(missing)}")
        print(f"orphans (table, not gold): {len(orphans)}")
        print("pipeline versions in the table:", dict(Counter(r[2] for r in rows)))
        print("embedding models in the table: ", dict(Counter(r[3] for r in rows)))

        if orphans and delete_orphans:
            ids = sorted(orphans)
            for i in range(0, len(ids), 1000):
                conn.execute("DELETE FROM chunks WHERE chunk_id = ANY(%s)", (ids[i : i + 1000],))
            print(f"\ndeleted {len(ids)} orphan rows.")
        elif orphans:
            print("\nOrphans found. Run again with --delete-orphans to remove them.")
        elif not missing:
            print("\nThe vector table and gold match exactly.")


if __name__ == "__main__":
    main("--delete-orphans" in sys.argv)
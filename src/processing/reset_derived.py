"""Delete everything DERIVED from the raw PDFs so it can be rebuilt with new code.

Deletes: silver/, gold/ and dead_letter/ in MinIO, the quality_runs rows, the vectors in the
chunks table, and sets papers back to status 'ingested'. The raw PDFs in bronze/ are NOT touched.

Run inside the Airflow container. Without --yes it only shows what it would delete:
    docker compose exec airflow-scheduler python -m src.processing.reset_derived
    docker compose exec airflow-scheduler python -m src.processing.reset_derived --yes
"""
import sys

from src.common.db import get_conn
from src.common.s3 import BUCKET, get_s3_client

PREFIXES = ["silver/", "gold/", "dead_letter/stage=quality/", "dead_letter/stage=process/"]


def keys_under(s3, prefix: str) -> list[str]:
    keys: list[str] = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=prefix):
        keys += [o["Key"] for o in page.get("Contents", [])]
    return keys


def main(confirmed: bool) -> None:
    s3 = get_s3_client()
    plan = {prefix: keys_under(s3, prefix) for prefix in PREFIXES}
    for prefix, keys in plan.items():
        print(f"{prefix:<32} {len(keys)} objects")
    with get_conn() as conn:
        counts = conn.execute("SELECT status, count(*) FROM papers GROUP BY status ORDER BY status").fetchall()
        has_chunks = conn.execute("SELECT to_regclass('public.chunks')").fetchone()[0] is not None
        n_vectors = conn.execute("SELECT count(*) FROM chunks").fetchone()[0] if has_chunks else 0
    print("papers by status:", dict(counts))
    print(f"{'rows in the chunks (vector) table':<32} {n_vectors}")

    if not confirmed:
        print("\nNothing deleted. Run again with --yes to delete the objects above and reset statuses.")
        return

    for keys in plan.values():
        for key in keys:
            s3.delete_object(Bucket=BUCKET, Key=key)
    with get_conn() as conn:
        conn.execute("TRUNCATE quality_runs")
        if has_chunks:
            conn.execute("TRUNCATE chunks")
        conn.execute("UPDATE papers SET status = 'ingested' WHERE status IN ('parsed', 'failed')")
    print("\nDone: derived layers deleted, quality_runs and chunks cleared, papers set to 'ingested'.")


if __name__ == "__main__":
    main("--yes" in sys.argv)
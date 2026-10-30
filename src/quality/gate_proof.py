"""Prove that the quality gate really blocks bad data, end to end.

Every command runs INSIDE the Airflow container (your laptop's venv does not have polars,
psycopg or boto3). Run them in this order:

  1. docker compose exec airflow-scheduler python -m src.quality.gate_proof --create
       Copies one real silver file, damages 20% of its chunks, and stores it as an extra
       silver file. This is far above the 5% limit.
  2. In Airflow, trigger the arxiv_quality DAG. The validate_file task for the test file
     must FAIL (the other files are already passed and are skipped).
  3. docker compose exec airflow-scheduler python -m src.quality.gate_proof --check
       Shows the 'blocked' row in quality_runs and confirms NOTHING reached gold.
  4. docker compose exec airflow-scheduler python -m src.quality.gate_proof --cleanup
       Removes the test file, its dead-letter file and its quality_runs rows.
"""
import io
import sys

import polars as pl

from src.common.db import get_conn
from src.common.s3 import BUCKET, get_s3_client, object_exists
from src.processing.pipeline import records_to_parquet_bytes

PROOF_KEY = "silver/chunks/strategy=section/year=2099/month=01/day=01/batch_gate_proof.parquet"
GOLD_KEY = PROOF_KEY.replace("silver/", "gold/", 1)
DEAD_KEY = "dead_letter/stage=quality/" + PROOF_KEY[len("silver/"):]
SOUP = "x1=0.5; y2=0.7; z3=0.9; (1) [2] +-*/ 0.11 " * 10


def create() -> None:
    s3 = get_s3_client()
    keys = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix="silver/chunks/"):
        keys += [o["Key"] for o in page.get("Contents", []) if o["Key"].endswith(".parquet") and o["Key"] != PROOF_KEY]
    source = sorted(keys)[0]
    rows = pl.read_parquet(io.BytesIO(s3.get_object(Bucket=BUCKET, Key=source)["Body"].read())).to_dicts()
    damaged = 0
    for i, row in enumerate(rows):
        if i % 5 == 0:  # every 5th chunk = 20%
            row["text"] = SOUP
            damaged += 1
    s3.put_object(Bucket=BUCKET, Key=PROOF_KEY, Body=records_to_parquet_bytes(rows))
    print(f"copied {len(rows)} chunks from {source}")
    print(f"damaged {damaged} of them ({damaged / len(rows):.0%}) and stored the test file at:\n  {PROOF_KEY}")
    print("\nNext: trigger the arxiv_quality DAG in Airflow. The validate_file task for this file must FAIL.")


def check() -> None:
    s3 = get_s3_client()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT status, total, valid, invalid, failure_rate, reasons FROM quality_runs WHERE silver_key = %s",
            (PROOF_KEY,),
        ).fetchall()
    print("quality_runs rows for the test file:")
    for r in rows:
        print(f"  status={r[0]} total={r[1]} valid={r[2]} invalid={r[3]} failure_rate={r[4]} reasons={r[5]}")
    if not rows:
        print("  none yet: has the arxiv_quality DAG run since --create?")
    print(f"gold file exists (must be False): {object_exists(GOLD_KEY, client=s3)}")
    print(f"dead-letter file exists (should be True): {object_exists(DEAD_KEY, client=s3)}")


def cleanup() -> None:
    s3 = get_s3_client()
    for key in (PROOF_KEY, GOLD_KEY, DEAD_KEY):
        s3.delete_object(Bucket=BUCKET, Key=key)
    with get_conn() as conn:
        conn.execute("DELETE FROM quality_runs WHERE silver_key = %s", (PROOF_KEY,))
    print("test file, its dead-letter file and its quality_runs rows removed.")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    {"--create": create, "--check": check, "--cleanup": cleanup}.get(
        action, lambda: print(__doc__)
    )()
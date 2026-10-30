"""Quality gate: silver Parquet -> validated gold Parquet (+ dead-letter for bad chunks).

Flow:  list_new_files -> validate_file (one task per silver file) -> summarize

For each silver file:
  1. every chunk is checked (schema, content rules, duplicates)
  2. bad chunks are written to dead_letter/stage=quality/ with their reasons
  3. if more than the allowed share of chunks is bad, the task FAILS and nothing
     reaches gold; otherwise the good chunks are written to gold/
Downstream steps (embedding) read only gold/, so bad data cannot reach the index.
"""
import io
from collections import Counter
from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.exceptions import AirflowFailException

from src.common.config import load_settings
from src.common.s3 import BUCKET, get_s3_client
from src.processing.pipeline import records_to_parquet_bytes
from src.quality.gate import (
    QualityGateError,
    check_gate,
    failure_rate,
    get_threshold,
    reason_counts,
    validate_records,
)
from src.quality.store import get_passed_keys, record_run

default_args = {"retries": 1, "retry_delay": timedelta(minutes=1)}


def gold_key_for(silver_key: str) -> str:
    return silver_key.replace("silver/", "gold/", 1)


def dead_letter_key_for(silver_key: str) -> str:
    return "dead_letter/stage=quality/" + silver_key[len("silver/"):]


@dag(
    dag_id="arxiv_quality",
    start_date=datetime(2026, 10, 15),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["quality", "gold"],
)
def arxiv_quality():

    @task
    def list_new_files() -> list[str]:
        s3 = get_s3_client()
        keys: list[str] = []
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix="silver/chunks/"):
            keys += [o["Key"] for o in page.get("Contents", []) if o["Key"].endswith(".parquet")]
        todo = sorted(set(keys) - get_passed_keys())
        print(f"{len(keys)} silver files, {len(todo)} still to validate")
        return todo

    @task
    def validate_file(silver_key: str) -> dict:
        import polars as pl

        settings = load_settings()
        threshold = get_threshold()
        s3 = get_s3_client()

        body = s3.get_object(Bucket=BUCKET, Key=silver_key)["Body"].read()
        rows = pl.read_parquet(io.BytesIO(body)).to_dicts()

        max_words = settings.chunk_size + settings.min_chunk_words  # a merged tail can overflow
        valid, invalid = validate_records(rows, settings.min_chunk_words, max_words)
        rate = failure_rate(len(rows), len(invalid))
        reasons = reason_counts(invalid)

        gold_key = gold_key_for(silver_key)
        dl_key = dead_letter_key_for(silver_key)
        if invalid:
            s3.put_object(Bucket=BUCKET, Key=dl_key, Body=records_to_parquet_bytes(invalid))

        try:
            check_gate(len(rows), len(invalid), threshold)
        except QualityGateError as exc:
            record_run(silver_key, None, dl_key if invalid else None,
                       len(rows), len(valid), len(invalid), rate, reasons, "blocked")
            raise AirflowFailException(f"{silver_key}: {exc}. Reasons: {reasons}")

        if valid:
            s3.put_object(Bucket=BUCKET, Key=gold_key, Body=records_to_parquet_bytes(valid))
        record_run(silver_key, gold_key if valid else None, dl_key if invalid else None,
                   len(rows), len(valid), len(invalid), rate, reasons, "passed")
        print(f"{silver_key}: {len(valid)} valid, {len(invalid)} invalid ({rate:.2%}) {reasons}")
        return {"total": len(rows), "valid": len(valid), "invalid": len(invalid), "reasons": reasons}

    @task(trigger_rule="none_failed")
    def summarize(results) -> None:
        results = list(results or [])
        total = sum(r["total"] for r in results)
        invalid = sum(r["invalid"] for r in results)
        reasons: Counter = Counter()
        for r in results:
            reasons.update(r["reasons"])
        rate = invalid / total if total else 0.0
        print(f"QUALITY SUMMARY: {total} chunks checked, {total - invalid} valid, "
              f"{invalid} rejected ({rate:.2%}); reasons: {dict(reasons)}")

    files = list_new_files()
    results = validate_file.expand(silver_key=files)
    summarize(results)


arxiv_quality()
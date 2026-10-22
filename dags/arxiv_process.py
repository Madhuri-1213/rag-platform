"""Processing DAG: bronze PDFs -> clean chunks -> silver Parquet.

Flow:  select_batches -> process_batch (one task per batch) -> summarize

Picks up every paper with status 'ingested', so it needs no date logic and is
safe to re-run: processed papers move to 'parsed' and are never picked up again.
"""
import hashlib
import json
from datetime import datetime, timedelta

from airflow.decorators import dag, task

from src.common.config import load_settings
from src.common.s3 import BUCKET, get_s3_client, put_object_if_absent
from src.processing.pipeline import process_paper, records_to_parquet_bytes, silver_key
from src.processing.status import get_papers_to_process, set_status

PAPERS_PER_RUN = 1000  # upper limit of papers handled by one DAG run
BATCH_SIZE = 25        # papers per task and per Parquet file

default_args = {
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
    "retry_exponential_backoff": True,
}


@dag(
    dag_id="arxiv_process",
    start_date=datetime(2026, 10, 15),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["processing", "silver"],
)
def arxiv_process():

    @task
    def select_batches() -> list[list[dict]]:
        papers = get_papers_to_process(PAPERS_PER_RUN)
        batches = [papers[i : i + BATCH_SIZE] for i in range(0, len(papers), BATCH_SIZE)]
        print(f"{len(papers)} papers to process in {len(batches)} batches")
        return batches

    @task
    def process_batch(batch: list[dict], data_interval_end=None) -> dict:
        settings = load_settings()
        run_date = data_interval_end.isoformat()
        s3 = get_s3_client()

        records: list[dict] = []
        ok_keys: list[str] = []
        failed_keys: list[str] = []

        for paper in batch:
            try:
                pdf_bytes = s3.get_object(Bucket=BUCKET, Key=paper["bronze_pdf_path"])["Body"].read()
                records.extend(process_paper(paper, pdf_bytes, settings, run_date))
                ok_keys.append(paper["paper_key"])
            except Exception as exc:  # one bad PDF must not stop the batch
                failed_keys.append(paper["paper_key"])
                put_object_if_absent(
                    f"dead_letter/stage=process/{paper['paper_key']}.json",
                    json.dumps(
                        {
                            "paper_key": paper["paper_key"],
                            "arxiv_id": paper["arxiv_id"],
                            "version": paper["version"],
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    ).encode("utf-8"),
                    content_type="application/json",
                )
                print(f"FAILED {paper['arxiv_id']}v{paper['version']}: {type(exc).__name__}: {exc}")

        key = None
        if records:
            # Same papers -> same file name, so a retry never writes a second copy.
            batch_id = hashlib.sha256("".join(sorted(ok_keys)).encode()).hexdigest()[:16]
            key = silver_key(settings.chunk_strategy, run_date, batch_id)
            put_object_if_absent(key, records_to_parquet_bytes(records))
            set_status(ok_keys, "parsed")  # only after the file is safely stored
        set_status(failed_keys, "failed")

        print(f"batch done: {len(ok_keys)} ok, {len(failed_keys)} failed, {len(records)} chunks -> {key}")
        return {"ok": len(ok_keys), "failed": len(failed_keys), "chunks": len(records), "file": key}

    # none_failed: also run when there was nothing to process (mapped task skipped)
    @task(trigger_rule="none_failed")
    def summarize(results) -> None:
        results = list(results or [])
        ok = sum(r["ok"] for r in results)
        failed = sum(r["failed"] for r in results)
        chunks = sum(r["chunks"] for r in results)
        files = [r["file"] for r in results if r["file"]]
        print(f"SUMMARY: {ok} papers processed, {failed} failed, {chunks} chunks, {len(files)} Parquet files")

    batches = select_batches()
    results = process_batch.expand(batch=batches)
    summarize(results)


arxiv_process()
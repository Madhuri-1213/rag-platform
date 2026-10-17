"""Incremental arXiv ingestion DAG (bronze layer).

Flow:  fetch_metadata -> download_and_store (one task per paper)
       -> register -> advance_watermark
"""
import json
from datetime import datetime, timedelta

from airflow.decorators import dag, task

from src.common.s3 import object_exists, put_object_if_absent
from src.ingestion.arxiv_client import fetch_papers
from src.ingestion.download import PermanentDownloadError, download_pdf
from src.ingestion.keys import bronze_key, make_paper_key
from src.ingestion.registry import existing_paper_keys, register_papers
from src.ingestion.watermark import get_watermark, set_watermark

SOURCE = "arxiv_cs_cl"
CATEGORY = "cs.CL"
# Testing only: caps papers per run so a test finishes in reasonable time.
# Papers beyond the cap are skipped, so raise or remove this for real runs.
MAX_PER_RUN = 200
LOOKBACK = timedelta(days=2)  # re-scan before the watermark for late-appearing papers

default_args = {
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
}


@dag(
    dag_id="arxiv_ingest",
    start_date=datetime(2026, 10, 15),  # recent on purpose: few catch-up runs while testing
    schedule="@daily",
    catchup=True,
    max_active_runs=1,  # runs go one at a time, so the watermark stays consistent
    default_args=default_args,
    tags=["ingestion", "bronze"],
)
def arxiv_ingest():

    @task(pool="arxiv_api")
    def fetch_metadata(data_interval_start=None, data_interval_end=None) -> list[dict]:
        # Window starts a little before the saved watermark (lookback), or at the
        # start of this run's interval when there is no watermark yet.
        watermark = get_watermark(SOURCE)
        start = watermark - LOOKBACK if watermark else data_interval_start
        papers = fetch_papers(
            CATEGORY, start, data_interval_end, max_results=MAX_PER_RUN
        )

        # Give every paper its idempotency key (arXiv id + version).
        for p in papers:
            p["paper_key"] = make_paper_key(p["arxiv_id"], p["version"])

        # Drop papers we already registered, so re-runs do no extra downloads.
        known = existing_paper_keys([p["paper_key"] for p in papers])
        fresh = [p for p in papers if p["paper_key"] not in known]
        print(f"window {start} -> {data_interval_end}: "
              f"{len(papers)} fetched, {len(fresh)} new")
        return fresh

    @task(pool="arxiv_api")  # the pool has 1 slot: one download at a time
    def download_and_store(paper: dict, data_interval_start=None) -> dict | None:
        json_key = bronze_key(SOURCE, data_interval_start, paper["paper_key"], "json")
        pdf_key = bronze_key(SOURCE, data_interval_start, paper["paper_key"], "pdf")

        # Skip the slow download if the PDF is already in MinIO.
        if not object_exists(pdf_key):
            try:
                pdf_bytes = download_pdf(paper["pdf_url"])
            except PermanentDownloadError as exc:
                # Not available (e.g. 404). Set the paper aside instead of failing
                # the whole run. It is not registered, so a later run inside the
                # lookback window will try it again automatically.
                record = {
                    "paper_key": paper["paper_key"],
                    "arxiv_id": paper["arxiv_id"],
                    "version": paper["version"],
                    "pdf_url": paper["pdf_url"],
                    "error": str(exc),
                }
                put_object_if_absent(
                    f"dead_letter/stage=download/{paper['paper_key']}.json",
                    json.dumps(record).encode("utf-8"),
                    content_type="application/json",
                )
                print(f"Skipping {paper['arxiv_id']}v{paper['version']}: {exc}")
                return None
            put_object_if_absent(pdf_key, pdf_bytes, content_type="application/pdf")

        # Metadata JSON: written only if absent, so re-runs never overwrite it.
        put_object_if_absent(
            json_key,
            json.dumps(paper).encode("utf-8"),
            content_type="application/json",
        )

        # register_papers needs the two storage paths.
        return {**paper, "bronze_pdf_path": pdf_key, "bronze_json_path": json_key}

    # none_failed: still run when there were zero papers and the mapped task was
    # skipped. Without it, an empty day would never advance the watermark.
    @task(trigger_rule="none_failed")
    def register(results) -> int:
        # results is None when no papers were fetched (the mapped task was skipped)
        results = list(results or [])
        papers = [r for r in results if r]
        new_rows = register_papers(papers)
        print(f"{len(papers)} papers seen, {new_rows} new, "
              f"{len(results) - len(papers)} set aside (see dead_letter/)")
        return new_rows

    @task(trigger_rule="none_failed")
    def advance_watermark(_registered: int, data_interval_end=None) -> None:
        # Last task: only reached if everything before it succeeded.
        set_watermark(SOURCE, data_interval_end)

    # Wiring: this line order is the execution order.
    papers = fetch_metadata()
    results = download_and_store.expand(paper=papers)  # one task per paper
    registered = register(results)
    advance_watermark(registered)


arxiv_ingest()
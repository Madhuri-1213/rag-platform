"""Run the Great Expectations suite on ALL gold files and build the HTML report (Data Docs).

Run inside the Airflow container:
    docker compose exec airflow-scheduler python -m src.quality.gx_report

Step 1 validates every gold chunk (this part uses the same calls that already worked in
try_gx.py). Step 2 stores the suite in a file-based project and builds Data Docs. If step 2
fails because of an API detail, step 1's result is still printed; send me the error.

The report is written to ./logs/gx/uncommitted/data_docs/local_site/index.html on your
machine (the logs folder is shared with the container). Open it in a browser.
"""
import os

os.environ.setdefault("GX_ANALYTICS_ENABLED", "False")  # no usage reporting

import great_expectations as gx  # noqa: E402

from src.quality.try_gx import build_suite, load_gold  # noqa: E402

GX_ROOT = "/opt/airflow/logs"  # becomes ./logs on your machine


def print_results(results) -> None:
    for r in results:
        cfg = r.expectation_config
        name = getattr(cfg, "type", type(cfg).__name__)
        column = (getattr(cfg, "kwargs", {}) or {}).get("column", "-")
        bad = (r.result or {}).get("unexpected_count", "-")
        print(f"  {'PASS' if r.success else 'FAIL'}  {name:<45} column={column:<16} unexpected={bad}")


def validate_all(pdf) -> bool:
    context = gx.get_context(mode="ephemeral")
    source = context.data_sources.add_pandas("gold_source")
    asset = source.add_dataframe_asset("gold_chunks")
    batch_definition = asset.add_batch_definition_whole_dataframe("whole_table")
    batch = batch_definition.get_batch(batch_parameters={"dataframe": pdf})
    result = batch.validate(build_suite())
    print(f"\nSTEP 1 OVERALL: {'PASS' if result.success else 'FAIL'}")
    print_results(result.results)
    return result.success


def build_data_docs(pdf) -> None:
    from great_expectations.checkpoint import UpdateDataDocsAction

    context = gx.get_context(mode="file", project_root_dir=GX_ROOT)
    source = context.data_sources.add_or_update_pandas("gold_source")
    try:
        asset = source.get_asset("gold_chunks")
    except Exception:
        asset = source.add_dataframe_asset("gold_chunks")
    try:
        batch_definition = asset.get_batch_definition("whole_table")
    except Exception:
        batch_definition = asset.add_batch_definition_whole_dataframe("whole_table")

    suite = context.suites.add_or_update(build_suite())
    validation = context.validation_definitions.add_or_update(
        gx.ValidationDefinition(name="gold_chunks_validation", data=batch_definition, suite=suite)
    )
    checkpoint = context.checkpoints.add_or_update(
        gx.Checkpoint(
            name="gold_chunks_checkpoint",
            validation_definitions=[validation],
            actions=[UpdateDataDocsAction(name="update_data_docs")],
        )
    )
    result = checkpoint.run(batch_parameters={"dataframe": pdf})
    print(f"\nSTEP 2 CHECKPOINT: {'PASS' if result.success else 'FAIL'}")
    print("Data Docs: open logs\\gx\\uncommitted\\data_docs\\local_site\\index.html in a browser")
    try:
        print("Sites:", context.get_docs_sites_urls())
    except Exception:
        pass


def main() -> None:
    print("great_expectations version:", getattr(gx, "__version__", "unknown"))
    df, n_files = load_gold(10**6)  # all files
    print(f"loaded {df.height} gold chunks from {n_files} files")
    pdf = df.drop("authors").to_pandas()

    validate_all(pdf)
    try:
        build_data_docs(pdf)
    except Exception as exc:  # keep step 1's result even if the report step needs adjusting
        print(f"\nSTEP 2 FAILED: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
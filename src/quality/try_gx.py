"""Try a Great Expectations suite on the gold chunks (dataset-level checks).

Run inside the Airflow container:
    docker compose exec airflow-scheduler python -m src.quality.try_gx

Written for Great Expectations 1.x. If it fails with an AttributeError or ImportError,
the library version in your image has a different API: copy the error and the printed
version, and the suite below can be adjusted.
"""
import io
import os

os.environ.setdefault("GX_ANALYTICS_ENABLED", "False")  # no usage reporting

import great_expectations as gx  # noqa: E402
import great_expectations.expectations as gxe  # noqa: E402
import polars as pl  # noqa: E402

from src.common.s3 import BUCKET, get_s3_client  # noqa: E402

MAX_FILES = 5  # enough for a first check; raise it later


def load_gold(max_files: int):
    s3 = get_s3_client()
    keys = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix="gold/chunks/"):
        keys += [o["Key"] for o in page.get("Contents", []) if o["Key"].endswith(".parquet")]
    keys = sorted(keys)[:max_files]
    frames = [pl.read_parquet(io.BytesIO(s3.get_object(Bucket=BUCKET, Key=k)["Body"].read())) for k in keys]
    return pl.concat(frames), len(keys)


def build_suite() -> "gx.ExpectationSuite":
    suite = gx.ExpectationSuite(name="gold_chunks_suite")
    expectations = [
        # no missing values in the columns everything depends on
        *[gxe.ExpectColumnValuesToNotBeNull(column=c) for c in ("chunk_id", "paper_key", "arxiv_id", "title", "text")],
        # identity
        gxe.ExpectColumnValuesToBeUnique(column="chunk_id"),
        gxe.ExpectColumnValuesToMatchRegex(column="chunk_id", regex=r"^[0-9a-f]{64}$"),
        gxe.ExpectColumnValuesToMatchRegex(column="text_hash", regex=r"^[0-9a-f]{64}$"),
        gxe.ExpectColumnValuesToMatchRegex(column="arxiv_id", regex=r"^(\d{4}\.\d{4,5}|[a-z\-]+/\d{7})$"),
        # sizes
        gxe.ExpectColumnValuesToBeBetween(column="n_words", min_value=40, max_value=340),
        gxe.ExpectColumnValuesToBeBetween(column="version", min_value=1, max_value=50),
        gxe.ExpectColumnValuesToBeBetween(column="chunk_index", min_value=0, max_value=5000),
        # dates look like ISO timestamps
        gxe.ExpectColumnValuesToMatchRegex(column="published_at", regex=r"^\d{4}-\d{2}-\d{2}T"),
        # known values
        gxe.ExpectColumnValuesToBeInSet(column="chunk_strategy", value_set=["section", "fixed"]),
        # the table is not empty or absurdly large
        gxe.ExpectTableRowCountToBeBetween(min_value=1, max_value=1_000_000),
    ]
    for e in expectations:
        suite.add_expectation(e)
    return suite


def main() -> None:
    print("great_expectations version:", getattr(gx, "__version__", "unknown"))
    df, n_files = load_gold(MAX_FILES)
    print(f"loaded {df.height} gold chunks from {n_files} files")

    pdf = df.drop("authors").to_pandas()  # list columns are awkward in pandas-based validation

    context = gx.get_context(mode="ephemeral")
    source = context.data_sources.add_pandas("gold_source")
    asset = source.add_dataframe_asset("gold_chunks")
    batch_definition = asset.add_batch_definition_whole_dataframe("whole_table")
    batch = batch_definition.get_batch(batch_parameters={"dataframe": pdf})

    result = batch.validate(build_suite())

    print(f"\nOVERALL: {'PASS' if result.success else 'FAIL'}")
    for r in result.results:
        cfg = r.expectation_config
        name = getattr(cfg, "type", type(cfg).__name__)
        column = (getattr(cfg, "kwargs", {}) or {}).get("column", "-")
        bad = (r.result or {}).get("unexpected_count", "-")
        print(f"  {'PASS' if r.success else 'FAIL'}  {name:<45} column={column:<16} unexpected={bad}")


if __name__ == "__main__":
    main()
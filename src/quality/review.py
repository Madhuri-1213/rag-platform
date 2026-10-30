"""Print random rejected and accepted chunks so you can judge the quality gate by eye.

Run inside the Airflow container:
    docker compose exec airflow-scheduler python -m src.quality.review
    docker compose exec airflow-scheduler python -m src.quality.review 20     # 20 of each
"""
import io
import sys

import polars as pl

from src.common.s3 import BUCKET, get_s3_client
from src.processing.clean import noise_stats
from src.quality.rules import MIN_ALPHA_RATIO, MIN_STOPWORD_RATIO, alpha_ratio


def load(prefix: str):
    s3 = get_s3_client()
    keys = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=prefix):
        keys += [o["Key"] for o in page.get("Contents", []) if o["Key"].endswith(".parquet")]
    if not keys:
        return None, 0
    frames = [pl.read_parquet(io.BytesIO(s3.get_object(Bucket=BUCKET, Key=k)["Body"].read())) for k in keys]
    return pl.concat(frames, how="diagonal"), len(keys)


def show(df: pl.DataFrame, n: int, with_reasons: bool) -> None:
    for row in df.sample(min(n, df.height), seed=7).to_dicts():
        extra = ""
        if with_reasons:
            a = alpha_ratio(row["text"])
            stop = noise_stats(row["text"])[3]
            extra = (
                f" | {row['error_reasons']} | letters={a:.0%} (needs {MIN_ALPHA_RATIO:.0%}+)"
                f" function-words={stop:.0%} (needs {MIN_STOPWORD_RATIO:.0%}+)"
            )
        print(f"- {row['arxiv_id']} | section={row['section'] or '-'} | {row['n_words']} words{extra}")
        print("    " + row["text"][:300].replace("\n", " "))


def main(n: int = 12) -> None:
    rejected, n_files = load("dead_letter/stage=quality/")
    if rejected is None:
        print("No rejected chunks found.")
    else:
        print(f"=== REJECTED: {rejected.height} chunks in {n_files} files. Showing {min(n, rejected.height)} ===")
        show(rejected, n, with_reasons=True)

    accepted, n_files = load("gold/chunks/")
    if accepted is None:
        print("No gold files found.")
        return
    print(f"\n=== ACCEPTED (gold): {accepted.height} chunks in {n_files} files. Showing {n} random ones ===")
    show(accepted, n, with_reasons=False)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 12)
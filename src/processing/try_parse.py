"""Manual check: parse and clean one stored PDF and show the result.

Run inside the Airflow container:
    docker compose exec airflow-scheduler python -m src.processing.try_parse
    docker compose exec airflow-scheduler python -m src.processing.try_parse 5   # 6th PDF
"""
import json
import sys

from src.common.s3 import BUCKET, get_s3_client
from src.processing.clean import clean_document
from src.processing.parse import extract_blocks


def main(index: int = 0) -> None:
    s3 = get_s3_client()
    keys = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix="bronze/"):
        keys += [o["Key"] for o in page.get("Contents", []) if o["Key"].endswith(".pdf")]
    print(f"{len(keys)} PDFs in bronze. Using #{index}: {keys[index]}")

    try:
        meta = json.loads(
            s3.get_object(Bucket=BUCKET, Key=keys[index].replace(".pdf", ".json"))["Body"].read()
        )
        print(f"paper: {meta['title']}")
        print(f"check it at: https://arxiv.org/abs/{meta['arxiv_id']}v{meta['version']}")
    except Exception:
        print("(no metadata JSON found next to this PDF)")

    pdf_bytes = s3.get_object(Bucket=BUCKET, Key=keys[index])["Body"].read()
    pages = extract_blocks(pdf_bytes)
    raw_chars = sum(len(b) for p in pages for b in p)
    text = clean_document(pages)
    text_before_cut = clean_document(pages, cut_refs=False)

    print(f"pages: {len(pages)}   blocks: {sum(len(p) for p in pages)}")
    print(f"characters raw: {raw_chars}   clean: {len(text)}")
    print(f"removed by the references cut: {len(text_before_cut) - len(text)} characters "
          f"({len(text) / max(len(text_before_cut), 1):.0%} of the text kept)")
    print("\n===== START OF CLEAN TEXT =====")
    print(text[:1500])
    print("\n===== END OF CLEAN TEXT =====")
    print(text[-600:])


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
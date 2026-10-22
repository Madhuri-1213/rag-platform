"""Manual check: chunk one stored PDF with both strategies and compare.

Run inside the Airflow container:
    docker compose exec airflow-scheduler python -m src.processing.try_chunk
    docker compose exec airflow-scheduler python -m src.processing.try_chunk 5
    docker compose exec airflow-scheduler python -m src.processing.try_chunk 5 --blocks
"""
import sys
from dataclasses import replace

from src.common.config import load_settings
from src.common.s3 import BUCKET, get_s3_client
from src.processing.chunkers import get_chunker
from src.processing.clean import clean_document, noise_stats
from src.processing.parse import extract_blocks
from src.processing.sections import split_sections


def main(index: int = 0, show_blocks: bool = False) -> None:
    s3 = get_s3_client()
    keys = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix="bronze/"):
        keys += [o["Key"] for o in page.get("Contents", []) if o["Key"].endswith(".pdf")]
    print(f"Using PDF #{index} of {len(keys)}: {keys[index]}")

    pdf_bytes = s3.get_object(Bucket=BUCKET, Key=keys[index])["Body"].read()
    dropped: list[str] = []
    text = clean_document(extract_blocks(pdf_bytes), dropped=dropped)
    print(f"clean text: {len(text.split())} words")
    print(f"\nDropped as chart/table noise: {len(dropped)} blocks. First few:")
    for block in dropped[:6]:
        print(f"  x {block[:110]!r}")

    print("\nSections detected:")
    for title, body in split_sections(text):
        print(f"  - {title:<28} {len(body.split()):>6} words")

    if show_blocks:
        first_title, first_body = split_sections(text)[0]
        print(f"\nParagraphs of the first section ({first_title}):")
        for i, para in enumerate(first_body.split("\n\n")):
            n, w, num, stop = noise_stats(para)
            print(f"  [{i}] tokens={n} words={w:.0%} numbers={num:.0%} stopwords={stop:.0%} | {para[:90]!r}")

    base = load_settings()
    for strategy in ("fixed", "section"):
        chunks = get_chunker(replace(base, chunk_strategy=strategy)).chunk_document(text)
        sizes = [c.n_words for c in chunks]
        print(f"\n=== strategy: {strategy} ===")
        print(f"chunks: {len(chunks)}   words per chunk: "
              f"min {min(sizes)}  avg {sum(sizes) / len(sizes):.0f}  max {max(sizes)}")
        for c in chunks[:3]:
            print(f"[{c.index}] section={c.section or '-'} ({c.n_words} words): {c.text[:160]}...")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(int(args[0]) if args else 0, show_blocks="--blocks" in sys.argv)
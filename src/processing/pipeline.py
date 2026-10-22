"""Pure processing logic: PDF bytes -> chunk records -> Parquet bytes.

No database or MinIO calls here, so everything is easy to test.
"""
import hashlib
import io

from src.common.config import Settings
from src.processing.chunkers import get_chunker
from src.processing.clean import clean_document

MIN_DOC_WORDS = 200  # fewer words than this usually means a scanned or broken PDF


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_chunk_id(paper_key: str, chunk_index: int, text_hash: str) -> str:
    """Stable id: same paper, position and text always give the same id."""
    return sha256_hex(f"{paper_key}:{chunk_index}:{text_hash}")


def build_chunk_records(paper: dict, text: str, settings: Settings, run_date: str) -> list[dict]:
    """Chunk the cleaned text of one paper and attach metadata to every chunk."""
    if len(text.split()) < MIN_DOC_WORDS:
        raise ValueError(f"too little text after cleaning ({len(text.split())} words)")

    chunks = get_chunker(settings).chunk_document(text)
    records = []
    for chunk in chunks:
        text_hash = sha256_hex(chunk.text)
        records.append(
            {
                "chunk_id": make_chunk_id(paper["paper_key"], chunk.index, text_hash),
                "paper_key": paper["paper_key"],
                "arxiv_id": paper["arxiv_id"],
                "version": paper["version"],
                "title": paper["title"],
                "authors": list(paper["authors"] or []),
                "section": chunk.section,
                "published_at": paper["published_at"],
                "chunk_index": chunk.index,
                "text": chunk.text,
                "text_hash": text_hash,
                "n_words": chunk.n_words,
                "chunk_strategy": settings.chunk_strategy,
                "pipeline_version": settings.pipeline_version,
                "run_date": run_date,
            }
        )
    return records


def process_paper(paper: dict, pdf_bytes: bytes, settings: Settings, run_date: str) -> list[dict]:
    """Parse, clean and chunk one PDF. Raises an exception if it cannot be processed."""
    from src.processing.parse import extract_blocks  # imported here: needs PyMuPDF

    text = clean_document(extract_blocks(pdf_bytes))
    return build_chunk_records(paper, text, settings, run_date)


def silver_key(strategy: str, run_date: str, batch_id: str) -> str:
    """Partitioned path, e.g. silver/chunks/strategy=section/year=2026/month=10/day=17/batch_ab12.parquet"""
    year, month, day = run_date[:10].split("-")
    return (
        f"silver/chunks/strategy={strategy}/year={year}/month={month}/day={day}/"
        f"batch_{batch_id}.parquet"
    )


def records_to_parquet_bytes(records: list[dict]) -> bytes:
    import polars as pl  # imported here so tests of the other functions need no polars

    buf = io.BytesIO()
    pl.DataFrame(records).write_parquet(buf)
    return buf.getvalue()
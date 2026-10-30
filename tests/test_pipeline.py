import pytest

from src.common.config import Settings
from src.processing.pipeline import (
    MIN_DOC_WORDS,
    build_chunk_records,
    make_chunk_id,
    records_to_parquet_bytes,
    silver_key,
)

PAPER = {
    "paper_key": "pk123",
    "arxiv_id": "2610.00001",
    "version": 1,
    "title": "A Test Paper",
    "authors": ["A. Author", "B. Author"],
    "published_at": "2026-10-15T10:00:00+00:00",
}


def make_text(n_sentences=60):
    body = " ".join(
        f"Sentence number {i} talks about retrieval quality in detail today." for i in range(n_sentences)
    )
    return "Abstract We study retrieval.\n\n1 Introduction\n\n" + body


def test_chunk_id_is_stable_and_sensitive():
    a = make_chunk_id("pk", 0, "hash")
    assert a == make_chunk_id("pk", 0, "hash")
    assert a != make_chunk_id("pk", 1, "hash")
    assert a != make_chunk_id("pk", 0, "other")
    assert len(a) == 64


def test_records_carry_metadata_and_sequential_index():
    recs = build_chunk_records(PAPER, make_text(), Settings(), "2026-10-17T00:00:00+00:00")
    assert len(recs) >= 2
    assert [r["chunk_index"] for r in recs] == list(range(len(recs)))
    first = recs[0]
    for field in ("chunk_id", "paper_key", "arxiv_id", "version", "title", "authors", "section",
                  "published_at", "text", "text_hash", "n_words", "chunk_strategy",
                  "pipeline_version", "run_date"):
        assert field in first
    assert first["paper_key"] == "pk123" and first["title"] == "A Test Paper"
    assert first["chunk_strategy"] == "section" and first["pipeline_version"] == Settings().pipeline_version
    assert "bronze_pdf_path" in first


def test_chunk_ids_are_unique_within_a_paper():
    recs = build_chunk_records(PAPER, make_text(), Settings(), "2026-10-17T00:00:00+00:00")
    assert len({r["chunk_id"] for r in recs}) == len(recs)


def test_same_input_gives_same_records():
    a = build_chunk_records(PAPER, make_text(), Settings(), "2026-10-17T00:00:00+00:00")
    b = build_chunk_records(PAPER, make_text(), Settings(), "2026-10-17T00:00:00+00:00")
    assert a == b


def test_strategy_setting_changes_output():
    fixed = build_chunk_records(PAPER, make_text(), Settings(chunk_strategy="fixed"), "2026-10-17")
    assert all(r["section"] == "" and r["chunk_strategy"] == "fixed" for r in fixed)


def test_too_little_text_is_rejected():
    with pytest.raises(ValueError):
        build_chunk_records(PAPER, "Just a few words.", Settings(), "2026-10-17")
    assert MIN_DOC_WORDS >= 100


def test_silver_key_is_partitioned():
    key = silver_key("section", "2026-10-17T00:00:00+00:00", "abc123")
    assert key == "silver/chunks/strategy=section/year=2026/month=10/day=17/batch_abc123.parquet"


def test_parquet_roundtrip():
    pl = pytest.importorskip("polars")
    import io

    recs = build_chunk_records(PAPER, make_text(), Settings(), "2026-10-17T00:00:00+00:00")
    df = pl.read_parquet(io.BytesIO(records_to_parquet_bytes(recs)))
    assert df.height == len(recs)
    assert set(df.columns) >= {"chunk_id", "text", "section", "authors"}
    assert df["chunk_id"].n_unique() == df.height
import pytest

from src.common.config import Settings
from src.processing.chunkers import (
    FixedChunker,
    SectionChunker,
    get_chunker,
    n_words,
    split_sentences,
)


def make_text(n_sentences: int, tag: str) -> str:
    """Sentences of 8 words each, e.g. 'Sentence ALPHA number 3 talks about retrieval quality.'"""
    return " ".join(
        f"Sentence {tag} number {i} talks about retrieval quality." for i in range(n_sentences)
    )


def test_sentence_split_keeps_abbreviations():
    sents = split_sentences("Smith et al. showed this works. We agree, e.g. on cost. Done.")
    assert sents == ["Smith et al. showed this works.", "We agree, e.g. on cost.", "Done."]


def test_fixed_chunks_respect_size_and_cover_everything():
    text = make_text(60, "ALPHA")  # 480 words
    chunks = FixedChunker(chunk_size=100, overlap=16, min_words=20).chunk_document(text)
    assert len(chunks) > 3
    assert all(c.n_words <= 100 + 20 for c in chunks)  # a merged tail can add < min_words
    joined = " ".join(c.text for c in chunks)
    for i in range(60):
        assert f"ALPHA number {i} " in joined  # no sentence was lost


def test_fixed_chunks_overlap():
    text = make_text(60, "ALPHA")
    chunks = FixedChunker(chunk_size=100, overlap=16, min_words=20).chunk_document(text)
    last_sentence = split_sentences(chunks[0].text)[-1]
    assert last_sentence in chunks[1].text  # end of chunk 0 repeats at start of chunk 1


def test_chunking_is_deterministic():
    text = make_text(40, "ALPHA")
    a = FixedChunker(100, 16, 20).chunk_document(text)
    b = FixedChunker(100, 16, 20).chunk_document(text)
    assert [c.text for c in a] == [c.text for c in b]


def test_very_long_sentence_is_split():
    long_sentence = "Word " * 250 + "end."
    chunks = FixedChunker(chunk_size=100, overlap=10, min_words=10).chunk_document(long_sentence)
    assert all(c.n_words <= 110 for c in chunks)
    assert len(chunks) >= 3


def test_section_chunks_never_cross_sections():
    text = "\n\n".join(
        [
            "1 Introduction",
            make_text(30, "ALPHA"),
            "2 Method",
            make_text(30, "BETA"),
        ]
    )
    chunks = SectionChunker(chunk_size=100, overlap=16, min_words=20).chunk_document(text)
    assert {c.section for c in chunks} == {"Introduction", "Method"}
    for c in chunks:
        assert not ("ALPHA" in c.text and "BETA" in c.text)
        if c.section == "Introduction":
            assert "BETA" not in c.text
        else:
            assert "ALPHA" not in c.text


def test_short_section_stays_one_chunk():
    text = "Abstract " + make_text(10, "ALPHA")  # 80 words, fits in 100
    chunks = SectionChunker(chunk_size=100, overlap=16, min_words=20).chunk_document(text)
    assert len(chunks) == 1 and chunks[0].section == "Abstract"


def test_tiny_section_merges_into_next():
    text = "\n\n".join(
        [
            "1 Introduction",
            make_text(10, "ALPHA"),
            "2 Tiny",
            "Just a few words here.",
            "3 Method",
            make_text(10, "BETA"),
        ]
    )
    chunks = SectionChunker(chunk_size=200, overlap=16, min_words=20).chunk_document(text)
    assert "Tiny" not in {c.section for c in chunks}
    method = [c for c in chunks if c.section == "Method"][0]
    assert "Just a few words" in method.text


def test_chunk_indexes_are_sequential():
    text = "1 Introduction\n\n" + make_text(40, "ALPHA")
    chunks = SectionChunker(100, 16, 20).chunk_document(text)
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_get_chunker_follows_settings():
    assert isinstance(get_chunker(Settings(chunk_strategy="fixed")), FixedChunker)
    assert isinstance(get_chunker(Settings(chunk_strategy="section")), SectionChunker)


def test_invalid_settings_rejected():
    with pytest.raises(ValueError):
        Settings(chunk_strategy="magic")
    with pytest.raises(ValueError):
        Settings(chunk_size=100, chunk_overlap=100)
import hashlib
from datetime import datetime, timezone

from src.quality.rules import (
    BAD_CHARS, BAD_CHUNK_ID, BAD_DATE, BAD_INDEX, BAD_VERSION, EMPTY_TEXT, EMPTY_TITLE, HASH_MISMATCH,
    LOW_ALPHA, LOW_PROSE, TOO_LONG, TOO_SHORT, alpha_ratio, semantic_problems,
)

NOW = datetime(2026, 10, 22, tzinfo=timezone.utc)
SENT = "The model is trained with a reward that depends on the quality of the answer in the context. "


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def good_row(text=None):
    text = text or SENT * 6  # about 100 words of normal prose
    return {
        "chunk_id": sha("id" + text), "paper_key": "pk", "arxiv_id": "2610.00001", "version": 1,
        "title": "A Paper", "authors": ["A"], "section": "Introduction",
        "published_at": "2026-10-15T10:00:00+00:00", "chunk_index": 0, "text": text,
        "text_hash": sha(text), "n_words": len(text.split()), "chunk_strategy": "section",
        "pipeline_version": "0.1.0", "run_date": "2026-10-17",
    }


def problems(row, **kw):
    return semantic_problems(row, min_words=40, max_words=340, now=NOW, **kw)


def test_good_row_has_no_problems():
    assert problems(good_row()) == []


def test_empty_and_length_limits():
    assert EMPTY_TEXT in problems({**good_row(), "text": "   "})
    assert TOO_SHORT in problems(good_row("Too short to be a useful chunk."))
    assert TOO_LONG in problems(good_row(SENT * 40))


def test_ids_hash_and_integrity():
    assert BAD_CHUNK_ID in problems({**good_row(), "chunk_id": "not-a-hash"})
    row = good_row()
    row["text"] = row["text"] + " tampered"
    assert HASH_MISMATCH in problems(row)


def test_dates():
    assert BAD_DATE in problems({**good_row(), "published_at": "2099-01-01T00:00:00+00:00"})
    assert BAD_DATE in problems({**good_row(), "published_at": "1980-01-01T00:00:00+00:00"})
    assert BAD_DATE in problems({**good_row(), "published_at": "not a date"})
    assert BAD_DATE in problems({**good_row(), "published_at": None})
    assert BAD_DATE not in problems({**good_row(), "published_at": "2026-10-15T10:00:00"})  # naive = UTC


def test_title_version_index():
    assert EMPTY_TITLE in problems({**good_row(), "title": "  "})
    assert BAD_VERSION in problems({**good_row(), "version": 0})
    assert BAD_INDEX in problems({**good_row(), "chunk_index": -1})


def test_symbol_soup_is_low_alpha():
    soup = " ".join(["x1=0.5;", "y2=0.7;", "z3=0.9;", "(1)", "[2]", "+-*/", "0.11"] * 12)
    assert alpha_ratio(soup) < 0.5
    assert LOW_ALPHA in problems(good_row(soup))


def test_label_soup_is_low_prose():
    soup = " ".join(["Single Obj.", "Two Obj.", "Counting Colors", "Position Attribute"] * 14)
    assert LOW_PROSE in problems(good_row(soup))
    assert LOW_PROSE not in problems(good_row())


def test_control_characters_are_rejected():
    assert BAD_CHARS in problems(good_row(SENT * 6 + "bad\x00char"))
    assert BAD_CHARS in problems({**good_row(), "title": "Title with \x00 NUL"})
    assert BAD_CHARS in problems({**good_row(), "section": "Method\x07"})
    assert BAD_CHARS not in problems(good_row("Caf\u00e9 and na\u00efve text. " * 20))
from datetime import datetime

from src.ingestion.keys import bronze_key, bronze_prefix, make_paper_key


def test_key_is_deterministic():
    assert make_paper_key("2610.20582", 1) == make_paper_key("2610.20582", 1)


def test_new_version_gets_new_key():
    assert make_paper_key("2610.20582", 1) != make_paper_key("2610.20582", 2)


def test_key_is_64_hex_chars():
    key = make_paper_key("2610.20582", 1)
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)


def test_old_style_id_with_slash_is_safe():
    assert len(make_paper_key("cs/0501001", 2)) == 64


def test_bronze_partition_path():
    d = datetime(2026, 10, 5)
    assert bronze_prefix("arxiv", d) == "bronze/source=arxiv/year=2026/month=10/day=05"
    assert bronze_key("arxiv", d, "abc", "pdf") == (
        "bronze/source=arxiv/year=2026/month=10/day=05/abc.pdf"
    )
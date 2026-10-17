from src.ingestion.arxiv_client import parse_id

def test_parse_new_style_id():
    assert parse_id("http://arxiv.org/abs/2610.20582v1") == ("2610.20582", 1)

def test_parse_multi_digit_version():
    assert parse_id("http://arxiv.org/abs/2610.20582v12") == ("2610.20582", 12)

def test_parse_old_style_id():
    assert parse_id("http://arxiv.org/abs/cs/0501001v2") == ("cs/0501001", 2)
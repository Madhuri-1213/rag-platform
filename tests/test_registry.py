import pytest

from src.common.db import get_conn
from src.ingestion.registry import existing_paper_keys, register_papers

KEY = "pytest_paper_key_0001"


def make_paper():
    return {
        "paper_key": KEY,
        "arxiv_id": "0000.00000",
        "version": 1,
        "title": "Test paper",
        "authors": ["A. Author", "B. Author"],
        "abstract": "An abstract.",
        "published": "2026-10-14T17:57:01+00:00",
        "updated": "2026-10-14T17:57:01+00:00",
        "bronze_pdf_path": "bronze/test.pdf",
        "bronze_json_path": "bronze/test.json",
    }


@pytest.fixture(autouse=True)
def clean_row():
    try:
        conn = get_conn()
    except Exception:
        pytest.skip("Postgres not reachable (is docker compose up? is POSTGRES_PASSWORD set?)")
    with conn:
        conn.execute("DELETE FROM papers WHERE paper_key = %s", (KEY,))
    yield
    with get_conn() as conn:
        conn.execute("DELETE FROM papers WHERE paper_key = %s", (KEY,))


def test_register_is_idempotent():
    assert register_papers([make_paper()]) == 1  # new row
    assert register_papers([make_paper()]) == 0  # same key: nothing inserted
    with get_conn() as conn:
        n = conn.execute(
            "SELECT count(*) FROM papers WHERE paper_key = %s", (KEY,)
        ).fetchone()[0]
    assert n == 1


def test_existing_paper_keys():
    assert existing_paper_keys([KEY]) == set()
    register_papers([make_paper()])
    assert existing_paper_keys([KEY, "other"]) == {KEY}
    assert existing_paper_keys([]) == set()
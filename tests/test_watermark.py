from datetime import datetime, timezone

import pytest

from src.common.db import get_conn
from src.ingestion.watermark import get_watermark, set_watermark

SRC = "pytest_source"


@pytest.fixture(autouse=True)
def clean_row():
    try:
        conn = get_conn()
    except Exception:
        pytest.skip("Postgres not reachable (is docker compose up? is POSTGRES_PASSWORD set?)")
    with conn:
        conn.execute("DELETE FROM ingestion_watermark WHERE source = %s", (SRC,))
    yield
    with get_conn() as conn:
        conn.execute("DELETE FROM ingestion_watermark WHERE source = %s", (SRC,))


def test_missing_returns_default():
    assert get_watermark(SRC) is None
    fallback = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert get_watermark(SRC, default=fallback) == fallback


def test_set_then_get():
    ts = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
    set_watermark(SRC, ts)
    assert get_watermark(SRC) == ts


def test_second_set_overwrites():
    set_watermark(SRC, datetime(2026, 10, 14, tzinfo=timezone.utc))
    later = datetime(2026, 10, 15, tzinfo=timezone.utc)
    set_watermark(SRC, later)
    assert get_watermark(SRC) == later
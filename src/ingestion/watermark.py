from datetime import datetime

from src.common.db import get_conn


def get_watermark(source: str, default: datetime | None = None) -> datetime | None:
    """Return the last successfully fetched timestamp for a source.

    Returns `default` if this source has never been fetched (first run).
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_fetched_at FROM ingestion_watermark WHERE source = %s",
            (source,),
        ).fetchone()
    return row[0] if row else default


def set_watermark(source: str, ts: datetime) -> None:
    """Insert or update the watermark. Call this only after a run fully succeeds."""
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO ingestion_watermark (source, last_fetched_at)
            VALUES (%s, %s)
            ON CONFLICT (source) DO UPDATE
              SET last_fetched_at = EXCLUDED.last_fetched_at
            """,
            (source, ts),
        )
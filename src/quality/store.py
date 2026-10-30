from psycopg.types.json import Jsonb

from src.common.db import get_conn


def get_passed_keys() -> set[str]:
    """Silver files that already passed the gate (so they are not validated again)."""
    with get_conn() as conn:
        rows = conn.execute("SELECT silver_key FROM quality_runs WHERE status = 'passed'").fetchall()
    return {r[0] for r in rows}


def record_run(
    silver_key: str,
    gold_key: str | None,
    dead_letter_key: str | None,
    total: int,
    valid: int,
    invalid: int,
    rate: float,
    reasons: dict,
    status: str,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO quality_runs
              (silver_key, gold_key, dead_letter_key, total, valid, invalid, failure_rate, reasons, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (silver_key, gold_key, dead_letter_key, total, valid, invalid, round(rate, 4), Jsonb(reasons), status),
        )
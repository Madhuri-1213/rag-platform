import os
from collections import Counter
from datetime import datetime, timezone

from src.quality.models import schema_problems
from src.quality.rules import DUPLICATE_ID, DUPLICATE_TEXT, semantic_problems

DEFAULT_THRESHOLD = 0.05  # block a file when more than 5% of its chunks are bad


class QualityGateError(Exception):
    """Too many bad records: downstream steps must not run on this data."""


def get_threshold() -> float:
    return float(os.getenv("QUALITY_FAILURE_THRESHOLD", DEFAULT_THRESHOLD))


def validate_records(
    rows: list[dict], min_words: int, max_words: int, now: datetime | None = None
) -> tuple[list[dict], list[dict]]:
    """Split rows into (valid, invalid). Invalid rows get `error_reasons` and `failed_at`.

    Order of checks: schema (fields and types), then content rules, then duplicates
    (the first good copy of a chunk_id or text is kept, later copies are rejected).
    """
    now = now or datetime.now(timezone.utc)
    valid: list[dict] = []
    invalid: list[dict] = []
    seen_ids: set = set()
    seen_text: dict = {}

    for row in rows:
        reasons = schema_problems(row)
        if not reasons:
            reasons = semantic_problems(row, min_words, max_words, now)
            if row["chunk_id"] in seen_ids:
                reasons.append(DUPLICATE_ID)
            elif row["text_hash"] in seen_text and seen_text[row["text_hash"]] != row["chunk_id"]:
                reasons.append(DUPLICATE_TEXT)
        if reasons:
            invalid.append({**row, "error_reasons": reasons, "failed_at": now.isoformat()})
        else:
            valid.append(row)
            seen_ids.add(row["chunk_id"])
            seen_text.setdefault(row["text_hash"], row["chunk_id"])
    return valid, invalid


def failure_rate(total: int, n_invalid: int) -> float:
    return n_invalid / total if total else 0.0


def reason_counts(invalid: list[dict]) -> dict[str, int]:
    """How many rows failed for each reason (a row can have several)."""
    counts = Counter(r for row in invalid for r in row["error_reasons"])
    return dict(counts.most_common())


def check_gate(total: int, n_invalid: int, threshold: float) -> None:
    """Raise QualityGateError if the failure rate is above the threshold."""
    rate = failure_rate(total, n_invalid)
    if rate > threshold:
        raise QualityGateError(
            f"failure rate {rate:.1%} is above the {threshold:.1%} threshold "
            f"({n_invalid} of {total} chunks)"
        )
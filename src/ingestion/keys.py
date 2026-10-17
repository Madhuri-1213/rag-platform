import hashlib
from datetime import datetime


def make_paper_key(arxiv_id: str, version: int) -> str:
    """Stable idempotency key: same paper + same version -> same key, always.

    A new version (v2) gets a different key, so updates are detected.
    """
    return hashlib.sha256(f"{arxiv_id}:{version}".encode("utf-8")).hexdigest()


def bronze_prefix(source: str, logical_date: datetime) -> str:
    """Partition folder for a run, based on the run's logical date (not 'now')."""
    return (
        f"bronze/source={source}"
        f"/year={logical_date:%Y}/month={logical_date:%m}/day={logical_date:%d}"
    )


def bronze_key(source: str, logical_date: datetime, paper_key: str, ext: str) -> str:
    """Full object key, e.g. bronze/source=arxiv/year=2026/month=10/day=15/<key>.pdf"""
    return f"{bronze_prefix(source, logical_date)}/{paper_key}.{ext}"
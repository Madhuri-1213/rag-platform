"""Row-level data quality rules. Pure Python: no database, no Pydantic, easy to test.

Each problem is a short reason code, so failures can be counted and compared.
"""
import hashlib
import re
from datetime import datetime, timedelta, timezone

from src.processing.clean import CONTROL_CHARS, noise_stats

HEX64 = re.compile(r"^[0-9a-f]{64}$")
ARXIV_START = datetime(1991, 8, 1, tzinfo=timezone.utc)  # arXiv's first month

EMPTY_TEXT = "EMPTY_TEXT"
TOO_SHORT = "TOO_SHORT"
TOO_LONG = "TOO_LONG"
BAD_CHUNK_ID = "BAD_CHUNK_ID"
BAD_TEXT_HASH = "BAD_TEXT_HASH"
HASH_MISMATCH = "HASH_MISMATCH"
BAD_DATE = "BAD_DATE"
EMPTY_TITLE = "EMPTY_TITLE"
BAD_VERSION = "BAD_VERSION"
BAD_INDEX = "BAD_INDEX"
LOW_ALPHA = "LOW_ALPHA"
LOW_PROSE = "LOW_PROSE"
DUPLICATE_ID = "DUPLICATE_ID"
DUPLICATE_TEXT = "DUPLICATE_TEXT"
BAD_CHARS = "BAD_CHARS"

MIN_ALPHA_RATIO = 0.5   # letters / non-space characters; normal prose is about 0.8
MIN_STOPWORD_RATIO = 0.06  # 'the', 'of', 'and'... ; normal prose is 0.25 or more


def alpha_ratio(text: str) -> float:
    chars = [c for c in text if not c.isspace()]
    return sum(c.isalpha() for c in chars) / len(chars) if chars else 0.0


def has_bad_chars(value: str) -> bool:
    """True if the string has control characters (NUL...) or lone surrogates: the database
    would reject it."""
    if CONTROL_CHARS.search(value):
        return True
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return True
    return False


def _parse_date(value) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def semantic_problems(row: dict, min_words: int, max_words: int, now: datetime | None = None) -> list[str]:
    """Content checks for one chunk record. Returns reason codes (empty list = good)."""
    now = now or datetime.now(timezone.utc)
    problems: list[str] = []

    text = row.get("text") or ""
    if not text.strip():
        problems.append(EMPTY_TEXT)
    else:
        n_words = len(text.split())
        if n_words < min_words:
            problems.append(TOO_SHORT)
        if n_words > max_words:
            problems.append(TOO_LONG)
        if alpha_ratio(text) < MIN_ALPHA_RATIO:
            problems.append(LOW_ALPHA)
        n, _, _, stop_ratio = noise_stats(text)
        if n >= 20 and stop_ratio < MIN_STOPWORD_RATIO:
            problems.append(LOW_PROSE)

    if any(has_bad_chars(str(row.get(f) or "")) for f in ("text", "title", "section")):
        problems.append(BAD_CHARS)

    if not HEX64.match(str(row.get("chunk_id", ""))):
        problems.append(BAD_CHUNK_ID)
    text_hash = str(row.get("text_hash", ""))
    if not HEX64.match(text_hash):
        problems.append(BAD_TEXT_HASH)
    elif text.strip() and hashlib.sha256(text.encode("utf-8")).hexdigest() != text_hash:
        problems.append(HASH_MISMATCH)

    published = _parse_date(row.get("published_at"))
    if published is None or published < ARXIV_START or published > now + timedelta(days=1):
        problems.append(BAD_DATE)

    if not str(row.get("title") or "").strip():
        problems.append(EMPTY_TITLE)
    if not isinstance(row.get("version"), int) or row["version"] < 1:
        problems.append(BAD_VERSION)
    if not isinstance(row.get("chunk_index"), int) or row["chunk_index"] < 0:
        problems.append(BAD_INDEX)

    return problems
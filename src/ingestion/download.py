import time

import requests

HEADERS = {"User-Agent": "arxiv-rag-platform/0.1 (learning project)"}

# These statuses will not fix themselves by retrying.
PERMANENT_STATUSES = (403, 404, 410)


class PermanentDownloadError(Exception):
    """The PDF is not available and retrying will not help (e.g. 404)."""


def download_pdf(
    url: str,
    timeout: int = 60,
    retries: int = 3,
    backoff: float = 5.0,
    pause: float = 3.0,
) -> bytes:
    """Download a PDF politely and safely.

    - timeout: never hang forever
    - transient problems (timeouts, 5xx, rate limits): retry with exponential
      backoff (5 s, 10 s, 20 s ...)
    - permanent problems (404, 403, 410): raise PermanentDownloadError at once,
      so the caller can set the paper aside instead of blocking the whole run
    - checks the bytes really are a PDF (arXiv sometimes returns an HTML page)
    - pause: waits after each success to respect arXiv's rate limit
    """
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=timeout, headers=HEADERS)
            if resp.status_code in PERMANENT_STATUSES:
                raise PermanentDownloadError(f"HTTP {resp.status_code} for {url}")
            resp.raise_for_status()
            if not resp.content.startswith(b"%PDF"):
                raise ValueError(f"Response from {url} is not a PDF")
            time.sleep(pause)
            return resp.content
        except (requests.RequestException, ValueError):
            if attempt == retries:
                raise
            time.sleep(backoff * 2 ** (attempt - 1))
    raise RuntimeError("unreachable")
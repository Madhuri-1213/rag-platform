import re
from datetime import datetime, timedelta, timezone

import arxiv


def parse_id(entry_id: str) -> tuple[str, int]:
    """'http://arxiv.org/abs/2610.20582v1' -> ('2610.20582', 1)"""
    short = entry_id.rsplit("/abs/", 1)[-1]
    m = re.match(r"^(.+)v(\d+)$", short)
    if not m:
        raise ValueError(f"Unexpected arXiv id: {entry_id}")
    return m.group(1), int(m.group(2))


def _to_utc(dt: datetime) -> datetime:
    """Treat naive datetimes as UTC; convert aware ones to UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def fetch_papers(
    category: str,
    start: datetime,
    end: datetime,
    max_results: int | None = None,
) -> list[dict]:
    """Return one dict per paper whose last update is in [start, end).

    Instead of asking arXiv to filter by date (the manual only documents a date
    filter for submittedDate), we ask for the category sorted by last update,
    newest first, and do the date filtering ourselves. We stop as soon as we
    reach papers older than `start`, so we never read more than needed.
    This also catches new versions (v2, v3...) of older papers.
    """
    start = _to_utc(start)
    end = _to_utc(end)

    client = arxiv.Client(page_size=100, delay_seconds=3, num_retries=3)
    search = arxiv.Search(
        query=f"cat:{category}",
        max_results=None,  # we stop ourselves with `break`
        sort_by=arxiv.SortCriterion.LastUpdatedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    papers = []
    for r in client.results(search):
        updated = _to_utc(r.updated)
        if updated >= end:
            continue  # newer than this window: keep scanning down
        if updated < start:
            break  # results are sorted, so everything after is older: stop
        arxiv_id, version = parse_id(r.entry_id)
        papers.append(
            {
                "arxiv_id": arxiv_id,
                "version": version,
                "title": " ".join(r.title.split()),
                "authors": [a.name for a in r.authors],
                "abstract": " ".join(r.summary.split()),
                "categories": list(r.categories),
                "primary_category": r.primary_category,
                "published": r.published.isoformat(),
                "updated": r.updated.isoformat(),
                "pdf_url": r.pdf_url,
            }
        )
        if max_results is not None and len(papers) >= max_results:
            break
    return papers


if __name__ == "__main__":
    # Quick manual test: papers updated in the last 24 hours.
    now = datetime.now(timezone.utc)
    results = fetch_papers("cs.CL", now - timedelta(days=1), now, max_results=5)
    print(f"Fetched {len(results)} papers")
    for p in results:
        print(p["arxiv_id"], f"v{p['version']}", p["updated"], p["title"])
        print("  authors:", ", ".join(p["authors"][:3]))
        print("  pdf:", p["pdf_url"])
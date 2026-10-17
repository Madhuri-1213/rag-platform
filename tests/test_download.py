import pytest
import requests

from src.ingestion import download


class FakeResponse:
    def __init__(self, content=b"%PDF-1.7 fake", status=200):
        self.content = content
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(download.time, "sleep", lambda s: None)


def test_success(monkeypatch):
    monkeypatch.setattr(download.requests, "get", lambda *a, **k: FakeResponse())
    assert download.download_pdf("http://x/y.pdf").startswith(b"%PDF")


def test_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        return FakeResponse(status=503) if calls["n"] == 1 else FakeResponse()

    monkeypatch.setattr(download.requests, "get", flaky)
    assert download.download_pdf("http://x/y.pdf").startswith(b"%PDF")
    assert calls["n"] == 2


def test_non_pdf_raises_after_retries(monkeypatch):
    monkeypatch.setattr(
        download.requests, "get", lambda *a, **k: FakeResponse(content=b"<html>")
    )
    with pytest.raises(ValueError):
        download.download_pdf("http://x/y.pdf", retries=2)


def test_404_is_permanent_and_not_retried(monkeypatch):
    calls = {"n": 0}

    def not_found(*a, **k):
        calls["n"] += 1
        return FakeResponse(status=404)

    monkeypatch.setattr(download.requests, "get", not_found)
    with pytest.raises(download.PermanentDownloadError):
        download.download_pdf("http://x/y.pdf")
    assert calls["n"] == 1  # no retries for a permanent error
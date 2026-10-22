import pytest

pymupdf = pytest.importorskip("pymupdf")  # skipped if PyMuPDF is not installed on this machine

from src.processing.parse import extract_blocks  # noqa: E402


def make_pdf(pages_text):
    doc = pymupdf.open()
    for text in pages_text:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def test_extract_blocks_returns_text_per_page():
    pdf = make_pdf(["Hello first page", "Second page text"])
    pages = extract_blocks(pdf)
    assert len(pages) == 2
    assert "Hello first page" in " ".join(pages[0])
    assert "Second page text" in " ".join(pages[1])
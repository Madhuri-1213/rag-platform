import pymupdf  # PyMuPDF


def extract_blocks(pdf_bytes: bytes) -> list[list[str]]:
    """Read a PDF and return its text as pages of text blocks.

    Result: one list per page, each holding the page's text blocks in the
    order the PDF stores them (for most arXiv papers that is reading order,
    including two-column layouts). Images are ignored.
    """
    pages: list[list[str]] = []
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            # each block: (x0, y0, x1, y1, text, block_no, block_type)
            # block_type 0 = text, 1 = image
            blocks = page.get_text("blocks")
            pages.append([b[4] for b in blocks if b[6] == 0 and b[4].strip()])
    return pages
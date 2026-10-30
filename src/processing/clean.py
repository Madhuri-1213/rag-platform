import re
import unicodedata

from src.processing.sections import _heading_of

# Vertical arXiv stamp, e.g. "arXiv:2610.20582v1 [cs.CL] 14 Oct 2026"
ARXIV_STAMP = re.compile(r"^arXiv:\S+\s+\[[\w.\-]+\]\s+\d{1,2}\s+\w{3}\s+\d{4}$")
PAGE_NUMBER = re.compile(r"^\d{1,4}$")
ABSTRACT_START = re.compile(r"^\s*abstract\b", re.IGNORECASE)
REFERENCES_HEADING = re.compile(
    r"^\s*(?:\d+\.?\s*)?(references|bibliography)\s*$", re.IGNORECASE | re.MULTILINE
)


def _norm_key(block: str) -> str:
    """Make 'Page 3 of 12' and 'Page 4 of 12' look the same, for repeat detection."""
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", block.strip().lower()))


def drop_repeated_blocks(pages: list[list[str]]) -> list[list[str]]:
    """Remove running headers/footers, page numbers and the arXiv stamp.

    A short block that shows up (ignoring digits) on at least half of the pages
    is treated as a header or footer. Skipped for very short documents.
    """
    n_pages = len(pages)
    counts: dict[str, int] = {}
    if n_pages >= 4:
        for page in pages:
            for key in {_norm_key(b) for b in page if len(b) < 150}:
                counts[key] = counts.get(key, 0) + 1
    threshold = max(3, n_pages / 2)

    cleaned = []
    for page in pages:
        kept = []
        for block in page:
            text = block.strip()
            if PAGE_NUMBER.match(text) or ARXIV_STAMP.match(text):
                continue
            if len(block) < 150 and counts.get(_norm_key(block), 0) >= threshold:
                continue
            kept.append(block)
        cleaned.append(kept)
    return cleaned


def trim_front_matter(pages: list[list[str]]) -> list[list[str]]:
    """Drop the title, authors and affiliations that come before the abstract.

    Title and authors are already stored as metadata, and they would only add
    noise to the first chunk. Looks for a block starting with 'Abstract' in the
    first two pages; if there is none, the pages are returned unchanged.
    """
    for p_idx, page in enumerate(pages[:2]):
        for b_idx, block in enumerate(page):
            if ABSTRACT_START.match(block):
                return [page[b_idx:]] + pages[p_idx + 1 :]
    return pages


# C0 control characters except tab, newline and carriage return (those become spaces later)
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def strip_control_chars(text: str) -> str:
    """Remove NUL and other control characters, and lone surrogates.

    PostgreSQL refuses NUL bytes in text, and lone surrogates cannot be stored as UTF-8.
    PDF parsers occasionally emit both for odd glyphs.
    """
    return CONTROL_CHARS.sub("", text).encode("utf-8", "ignore").decode("utf-8")


def clean_block(block: str) -> str:
    """Fix one block: strip bad characters, rejoin hyphenated words, flatten lines,
    normalise unicode."""
    block = strip_control_chars(block)
    block = re.sub(r"(\w)-\n(\w)", r"\1\2", block)  # "informa-\ntion" -> "information"
    block = block.replace("\n", " ")
    block = unicodedata.normalize("NFKC", block)  # ligatures like "ﬁ" -> "fi"
    return re.sub(r"\s+", " ", block).strip()


STOPWORDS = frozenset(
    "the of and in to a an is are was were be been that this these those with for on by as at "
    "from we our it its which can not or than have has also such their they more both each using "
    "show shows shown into over between when where while however thus therefore".split()
)
_NUMBERED_HEADING = re.compile(r"^[1-9]\d?(?:\.\d{1,2})*\.?\s+[A-Z]")


# Dot leaders of a table of contents or list of figures: ". . . . ." or "....."
DOT_LEADERS = re.compile(r"(?:\.\s){4,}|\.{5,}")


def is_toc_block(block: str) -> bool:
    """True for table-of-contents style blocks (rows of dot leaders and page numbers)."""
    return bool(DOT_LEADERS.search(block))


def _is_word(token: str) -> bool:
    core = token.strip("().,;:!?\"'[]").replace("-", "")
    return len(core) >= 3 and core.isalpha()


def _is_numeric(token: str) -> bool:
    return any(c.isdigit() for c in token) and not any(c.isalpha() for c in token)


def noise_stats(block: str) -> tuple[int, float, float, float]:
    """(tokens, word_ratio, numeric_ratio, stopword_ratio) for a block."""
    tokens = block.split()
    n = len(tokens)
    if n == 0:
        return 0, 1.0, 0.0, 1.0
    words = sum(_is_word(t) for t in tokens) / n
    numeric = sum(_is_numeric(t) for t in tokens) / n
    stops = sum(
        "(" not in t and ")" not in t and t.strip(".,;:!?\"'[]").lower() in STOPWORDS
        for t in tokens
    ) / n
    return n, words, numeric, stops


def _looks_like_heading(block: str) -> bool:
    return _heading_of(block) is not None or bool(_NUMBERED_HEADING.match(block))


def is_noise_block(block: str) -> bool:
    """True for blocks that look like chart axes, legends or numeric tables, not prose.

    For blocks of 6+ tokens, noise if any of these holds:
      - fewer than half the tokens are real words (3+ letters)
      - 40% or more of the tokens are numbers
      - (8+ tokens) under 10% function words like 'the', 'of', 'and' AND the block
        does not end like a sentence. Prose is full of function words; label soup
        such as 'Single Obj. Two Obj. (a) FLUX: In-Domain' has none.
    Headings are never noise. Trade-off: numeric tables are dropped too, which is
    fine for question answering over prose.
    """
    n, word_ratio, numeric_ratio, stop_ratio = noise_stats(block)
    if n < 6 or _looks_like_heading(block):
        return False
    if word_ratio < 0.5 or numeric_ratio >= 0.4:
        return True
    if n >= 8 and stop_ratio < 0.10 and not block.rstrip().endswith((".", "!", "?")):
        return True
    return False


def _is_fragment(block: str) -> bool:
    """A short block (6 tokens or fewer) with no function words that is not a heading.

    '0 100 200 Training Step' and 'Single Obj. Two Obj.' are fragments; short real
    sentences such as 'We thank Alice.' are not, because they contain function words.
    """
    if len(block.split()) > 6 or _looks_like_heading(block):
        return False
    return noise_stats(block)[3] == 0


def drop_fragment_runs(blocks: list[str], min_run: int = 4, dropped: list | None = None) -> list[str]:
    """Drop runs of 4+ consecutive tiny fragments (axis labels, legend entries)."""
    out: list[str] = []
    run: list[str] = []
    for block in blocks + [None]:
        if block is not None and _is_fragment(block):
            run.append(block)
            continue
        if len(run) >= min_run:
            if dropped is not None:
                dropped.extend(run)
        else:
            out.extend(run)
        run = []
        if block is not None:
            out.append(block)
    return out


def cut_references(text: str) -> str:
    """Drop everything from the last 'References' heading onward.

    Only counts a heading in the second part of the document, so a mention
    of 'References' near the start does not cut the paper short.
    Limitation: appendices placed after the references are removed too.
    """
    matches = [m for m in REFERENCES_HEADING.finditer(text) if m.start() > 0.3 * len(text)]
    if not matches:
        return text
    return text[: matches[-1].start()].rstrip()


def clean_document(
    pages: list[list[str]], cut_refs: bool = True, dropped: list | None = None
) -> str:
    """Pages of raw blocks -> one clean text; paragraphs separated by blank lines.

    If a list is passed as `dropped`, blocks removed as chart/table noise are
    appended to it (useful for checking the filter by eye).
    """
    pages = trim_front_matter(drop_repeated_blocks(pages))
    blocks = [b for b in (clean_block(b) for page in pages for b in page) if b]
    kept = []
    for block in blocks:
        if is_toc_block(block) or is_noise_block(block):
            if dropped is not None:
                dropped.append(block)
        else:
            kept.append(block)
    kept = drop_fragment_runs(kept, dropped=dropped)
    text = "\n\n".join(kept)
    return cut_references(text) if cut_refs else text
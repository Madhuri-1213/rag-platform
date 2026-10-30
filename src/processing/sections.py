import re

KNOWN_NAMES = [
    "abstract", "introduction", "related work", "related works", "background",
    "preliminaries", "method", "methods", "methodology", "approach", "model",
    "experiments", "experimental setup", "experimental results", "results",
    "analysis", "discussion", "conclusion", "conclusions", "limitations",
    "ethics statement", "ethical considerations", "acknowledgments", "acknowledgements",
    "appendix",
]
_KNOWN = "|".join(re.escape(n) for n in sorted(KNOWN_NAMES, key=len, reverse=True))

# A short paragraph that is only a known section name: "Introduction", "6 Conclusion"
STANDALONE_KNOWN = re.compile(
    rf"^(?:[1-9]\d?(?:\.\d{{1,2}})*\.?\s+)?(?:{_KNOWN})\s*:?$", re.IGNORECASE
)
# A short numbered title: "3.2 Decoupled RL Training"
STANDALONE_NUMBERED = re.compile(r"^[1-9]\d?(?:\.\d{1,2})*\.?\s+[A-Z][^.!?]{1,70}$")
# Heading and text glued in one block: "Abstract We study ..."
MERGED_ABSTRACT = re.compile(r"^abstract\s*[:.\-\u2014]?\s+(?=\S)", re.IGNORECASE)
# Numbered known name glued to text: "6 Conclusion This work introduces ..."
MERGED_NUMBERED_KNOWN = re.compile(
    rf"^([1-9]\d?(?:\.\d{{1,2}})*\.?\s+(?:{_KNOWN}))\s+(?=(?-i:[A-Z]))", re.IGNORECASE
)


# One spelling per known section name: 'related work', 'RELATED WORK' -> 'Related Work'
CANONICAL = {name: name.title() for name in KNOWN_NAMES}
CANONICAL.update(
    {
        "acknowledgements": "Acknowledgments",
        "related works": "Related Work",
        "conclusions": "Conclusion",
    }
)

# Closing sections are short. Text that runs on long after such a heading is almost always
# the appendix, which would otherwise inherit the wrong label. Limits are in words.
TAIL_LIMITS = [
    ("conclusion", 600),
    ("limitation", 350),
    ("ethic", 350),
    ("acknowledge", 350),
    ("broader impact", 350),
]


def _tail_limit(title: str):
    t = title.lower()
    for prefix, limit in TAIL_LIMITS:
        if t.startswith(prefix):
            return limit
    return None


def canonical_title(title: str) -> str:
    key = title.strip().lower()
    if key in CANONICAL:
        return CANONICAL[key]
    if title.isupper() and len(title) > 3:  # "EVALUATION SETTING" -> "Evaluation Setting"
        return title.title()
    return title


def _clean_title(raw: str) -> str:
    stripped = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", raw.strip()).strip(" :")
    return canonical_title(stripped)


def _cap_tail(title: str, body: str) -> list[tuple[str, str]]:
    """Split a too-long closing section: the first paragraphs up to the limit keep the label,
    the rest becomes 'Appendix'."""
    limit = _tail_limit(title)
    if limit is None:
        return [(title, body)]
    paragraphs = body.split("\n\n")
    kept: list[str] = []
    words = 0
    for par in paragraphs:
        w = len(par.split())
        if kept and words + w > limit:
            rest = paragraphs[len(kept):]
            return [(title, "\n\n".join(kept)), ("Appendix", "\n\n".join(rest))]
        kept.append(par)
        words += w
    return [(title, body)]


MATH_CHARS = set("=<>\u2265\u2264\u2248\u2260\u2208\u2211\u220f\u222b\u00b1\u00d7\u00f7\u2202\u2207")


def _is_list_item(p: str) -> bool:
    """A numbered list item or a line of maths ('1. Y=GEMM(X, W) ...,' or '5 Hence D >= h2')
    is not a heading."""
    return p.endswith((",", ";")) or any(c in MATH_CHARS for c in p)


def _heading_of(paragraph: str):
    """Return (title, remaining_text) if the paragraph starts a section, else None."""
    p = paragraph.strip()
    if len(p) <= 80 and STANDALONE_KNOWN.match(p):
        return _clean_title(p), ""
    if len(p) <= 80 and STANDALONE_NUMBERED.match(p) and not _is_list_item(p):
        return _clean_title(p), ""
    m = MERGED_ABSTRACT.match(p)
    if m:
        return "Abstract", p[m.end():]
    m = MERGED_NUMBERED_KNOWN.match(p)
    if m:
        return _clean_title(m.group(1)), p[m.end():]
    return None


def split_sections(text: str) -> list[tuple[str, str]]:
    """Split cleaned paper text into (section_title, section_text) pairs.

    Heading detection is heuristic: it will miss some headings and occasionally
    invent one. Text before the first heading is called 'Preamble'; a document
    with no detected headings becomes a single 'Body' section.
    """
    sections: list[tuple[str, str]] = []
    title, buf = "Preamble", []
    for paragraph in text.split("\n\n"):
        found = _heading_of(paragraph)
        if found:
            if buf:
                sections.extend(_cap_tail(title, "\n\n".join(buf)))
            title, rest = found
            buf = [rest] if rest else []
        elif paragraph.strip():
            buf.append(paragraph)
    if buf:
        sections.extend(_cap_tail(title, "\n\n".join(buf)))
    if len(sections) == 1 and sections[0][0] == "Preamble":
        sections = [("Body", sections[0][1])]
    return sections
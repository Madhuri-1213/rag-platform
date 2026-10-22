import re

KNOWN_NAMES = [
    "abstract", "introduction", "related work", "related works", "background",
    "preliminaries", "method", "methods", "methodology", "approach", "model",
    "experiments", "experimental setup", "experimental results", "results",
    "analysis", "discussion", "conclusion", "conclusions", "limitations",
    "ethics statement", "acknowledgments", "acknowledgements", "appendix",
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


def _clean_title(raw: str) -> str:
    return re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", raw.strip()).strip(" :")


def _heading_of(paragraph: str):
    """Return (title, remaining_text) if the paragraph starts a section, else None."""
    p = paragraph.strip()
    if len(p) <= 80 and (STANDALONE_KNOWN.match(p) or STANDALONE_NUMBERED.match(p)):
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
                sections.append((title, "\n\n".join(buf)))
            title, rest = found
            buf = [rest] if rest else []
        elif paragraph.strip():
            buf.append(paragraph)
    if buf:
        sections.append((title, "\n\n".join(buf)))
    if len(sections) == 1 and sections[0][0] == "Preamble":
        sections = [("Body", sections[0][1])]
    return sections
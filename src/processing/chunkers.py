import re
from dataclasses import dataclass

from src.common.config import Settings, load_settings
from src.processing.sections import split_sections

# Abbreviations whose full stop must not end a sentence.
ABBREVIATIONS = ["et al.", "e.g.", "i.e.", "Fig.", "Figs.", "Eq.", "Sec.", "vs.", "No."]
_SENTENCE_END = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9(\["\u201c])')
_DOT = "<DOT>"


@dataclass
class Chunk:
    text: str
    section: str
    index: int = 0

    @property
    def n_words(self) -> int:
        return len(self.text.split())


def n_words(text: str) -> int:
    return len(text.split())


def split_sentences(text: str) -> list[str]:
    """Split text into sentences with a simple rule (no extra downloads needed)."""
    out: list[str] = []
    for paragraph in text.split("\n\n"):
        protected = paragraph
        for abbr in ABBREVIATIONS:
            protected = protected.replace(abbr, abbr.replace(".", _DOT))
        for sentence in _SENTENCE_END.split(protected):
            sentence = sentence.replace(_DOT, ".").strip()
            if sentence:
                out.append(sentence)
    return out


def _split_long(sentence: str, max_words: int) -> list[str]:
    words = sentence.split()
    return [" ".join(words[i : i + max_words]) for i in range(0, len(words), max_words)]


def pack_sentences(text: str, chunk_size: int, overlap: int, min_words: int) -> list[str]:
    """Greedily pack sentences into chunks of at most `chunk_size` words.

    - Never cuts a sentence in half (unless one sentence alone is too long).
    - Each new chunk starts with the last sentences of the previous one, up to
      `overlap` words, so an idea at a boundary appears in both chunks.
    - A tiny final piece (under `min_words`) is merged into the previous chunk.
    """
    sentences: list[str] = []
    for s in split_sentences(text):
        sentences.extend(_split_long(s, chunk_size) if n_words(s) > chunk_size else [s])

    chunks: list[str] = []
    current: list[str] = []
    carry_len = 0  # how many sentences at the start of `current` are repeated overlap
    cur_words = 0
    for sent in sentences:
        w = n_words(sent)
        if current and cur_words + w > chunk_size:
            chunks.append(" ".join(current))
            carry: list[str] = []
            carried = 0
            for prev in reversed(current):
                pw = n_words(prev)
                if carried + pw > overlap:
                    break
                carry.insert(0, prev)
                carried += pw
            if carried + w > chunk_size:  # no room for the overlap: start clean
                carry, carried = [], 0
            current, carry_len, cur_words = carry, len(carry), carried
        current.append(sent)
        cur_words += w

    if current:
        if chunks and cur_words < min_words:
            new_part = current[carry_len:]
            chunks[-1] = chunks[-1] + " " + " ".join(new_part)
        else:
            chunks.append(" ".join(current))
    return chunks


class FixedChunker:
    """Fixed-size chunks with overlap, ignoring the paper's structure."""

    def __init__(self, chunk_size: int, overlap: int, min_words: int):
        self.chunk_size, self.overlap, self.min_words = chunk_size, overlap, min_words

    def chunk_document(self, text: str) -> list[Chunk]:
        pieces = pack_sentences(text, self.chunk_size, self.overlap, self.min_words)
        return [Chunk(text=t, section="", index=i) for i, t in enumerate(pieces)]


class SectionChunker:
    """Chunks that never cross a section boundary.

    A section that fits in one chunk stays whole; a longer one is split with the
    same sentence packing; a tiny section is merged into the next one.
    """

    def __init__(self, chunk_size: int, overlap: int, min_words: int):
        self.chunk_size, self.overlap, self.min_words = chunk_size, overlap, min_words

    def chunk_document(self, text: str) -> list[Chunk]:
        chunks: list[Chunk] = []
        pending = ""  # text of tiny sections waiting to join the next section
        for title, body in split_sections(text):
            body = (pending + "\n\n" + body).strip() if pending else body
            pending = ""
            if n_words(body) < self.min_words:
                pending = body
                continue
            for piece in pack_sentences(body, self.chunk_size, self.overlap, self.min_words):
                chunks.append(Chunk(text=piece, section=title))
        if pending:
            if chunks:
                chunks[-1].text += " " + " ".join(pending.split())
            else:
                chunks.append(Chunk(text=" ".join(pending.split()), section="Body"))
        for i, c in enumerate(chunks):
            c.index = i
        return chunks


def get_chunker(settings: Settings | None = None):
    """Pick the chunking strategy from the settings (CHUNK_STRATEGY env var)."""
    s = settings or load_settings()
    cls = FixedChunker if s.chunk_strategy == "fixed" else SectionChunker
    return cls(s.chunk_size, s.chunk_overlap, s.min_chunk_words)
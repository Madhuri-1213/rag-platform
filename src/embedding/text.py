"""What exactly gets embedded, and the cache key for it. Pure functions, easy to test."""
import hashlib

# Labels that say nothing about the content are left out of the embedded text.
UNINFORMATIVE_SECTIONS = {"", "Body", "Preamble"}


def make_embed_text(title: str, section: str | None, text: str) -> str:
    """Put the paper title (and section) in front of the chunk, so a chunk that says
    'the model' still carries which paper and part it belongs to."""
    head = (title or "").strip()
    if section and section not in UNINFORMATIVE_SECTIONS:
        head = f"{head} | {section}"
    return f"{head}\n{text}" if head else text


def make_embed_key(model_name: str, embed_text: str) -> str:
    """Cache key: same model and same embedded text -> same key -> no need to embed again."""
    return hashlib.sha256(f"{model_name}\x1f{embed_text}".encode("utf-8")).hexdigest()
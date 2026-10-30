import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Pipeline settings. Sizes are counted in WORDS (a simple stand-in for tokens).

    As a rule of thumb 1 word is about 1.3 tokens, so 300 words is roughly 400 tokens.
    """

    chunk_strategy: str = "section"   # "fixed" or "section"
    chunk_size: int = 300             # maximum words per chunk
    chunk_overlap: int = 50           # words shared between neighbouring chunks (fixed strategy)
    min_chunk_words: int = 40         # smaller pieces are merged into a neighbour
    pipeline_version: str = "0.5.0"   # stored on every chunk so you can tell which code made it
    embedding_model: str = "BAAI/bge-small-en-v1.5"  # 384-dimensional, runs on a CPU
    embedding_dim: int = 384
    embed_context: bool = True        # put the title and section in front of the text before embedding

    def __post_init__(self):
        if self.chunk_strategy not in ("fixed", "section"):
            raise ValueError(f"CHUNK_STRATEGY must be 'fixed' or 'section', got {self.chunk_strategy!r}")
        if self.chunk_size <= 0:
            raise ValueError("CHUNK_SIZE must be positive")
        if not 0 <= self.chunk_overlap < self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be >= 0 and smaller than CHUNK_SIZE")


def load_settings() -> Settings:
    """Read settings from environment variables, falling back to the defaults."""
    defaults = Settings()
    return Settings(
        chunk_strategy=os.getenv("CHUNK_STRATEGY", defaults.chunk_strategy),
        chunk_size=int(os.getenv("CHUNK_SIZE", defaults.chunk_size)),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", defaults.chunk_overlap)),
        min_chunk_words=int(os.getenv("MIN_CHUNK_WORDS", defaults.min_chunk_words)),
        pipeline_version=os.getenv("PIPELINE_VERSION", defaults.pipeline_version),
        embedding_model=os.getenv("EMBEDDING_MODEL", defaults.embedding_model),
        embedding_dim=int(os.getenv("EMBEDDING_DIM", defaults.embedding_dim)),
        embed_context=os.getenv("EMBED_CONTEXT", "1").lower() not in ("0", "false", "no"),
    )
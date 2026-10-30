"""Turns text into vectors with a sentence-transformers model (runs on the CPU)."""
import numpy as np

# bge models are trained so that QUESTIONS carry this prefix and passages do not
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_model = None
_model_name = None


def get_model(model_name: str):
    """Load the model once per process (the first call downloads it into HF_HOME)."""
    global _model, _model_name
    if _model is None or _model_name != model_name:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(model_name)
        _model_name = model_name
    return _model


def embed_passages(texts: list[str], model_name: str, batch_size: int = 32) -> np.ndarray:
    """Vectors for chunks. Normalised to length 1, so cosine similarity = dot product."""
    model = get_model(model_name)
    return model.encode(texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False)


def embed_query(question: str, model_name: str) -> np.ndarray:
    model = get_model(model_name)
    return model.encode([QUERY_PREFIX + question], normalize_embeddings=True, show_progress_bar=False)[0]
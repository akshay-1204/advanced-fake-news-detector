"""Multilingual embedding generation service for Satyavani AI.

Uses sentence-transformers (default: BAAI/bge-m3, 1024 dimensions)
to embed claims and articles across English, Hindi, and Telugu.
Includes fallback support for fast unit testing and offline execution.
"""
import logging
import math
from typing import List, Optional

from backend.config import settings

logger = logging.getLogger(__name__)

_MODEL_INSTANCE = None


def _get_model():
    """Lazy-load the multilingual SentenceTransformer model."""
    global _MODEL_INSTANCE
    if _MODEL_INSTANCE is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model '%s'...", settings.EMBEDDING_MODEL)
            _MODEL_INSTANCE = SentenceTransformer(settings.EMBEDDING_MODEL)
        except Exception as exc:
            logger.warning("Could not load sentence_transformers (%s). Using fallback embedding generator.", exc)
            _MODEL_INSTANCE = "fallback"
    return _MODEL_INSTANCE


def _generate_fallback_vector(text: str, dim: int) -> List[float]:
    """Generate a deterministic normalized pseudo-embedding for testing and offline development."""
    vec = [0.0] * dim
    clean = text.lower().strip()
    if not clean:
        return vec

    # Hash character trigrams into dimensions
    for i in range(len(clean) - 2):
        trigram = clean[i:i + 3]
        idx = hash(trigram) % dim
        vec[idx] += 1.0

    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a batch of text strings into normalized vectors of length EMBEDDING_DIM."""
    if not texts:
        return []

    model = _get_model()
    if model != "fallback":
        try:
            embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return [emb.tolist() if hasattr(emb, "tolist") else list(emb) for emb in embeddings]
        except Exception as exc:
            logger.error("Error during batch embedding: %s", exc)

    # Fallback deterministic vector generator
    return [_generate_fallback_vector(t, settings.EMBEDDING_DIM) for t in texts]


def embed_query(query: str) -> List[float]:
    """Embed a single query string into a normalized vector of length EMBEDDING_DIM."""
    res = embed_texts([query])
    return res[0] if res else [0.0] * settings.EMBEDDING_DIM

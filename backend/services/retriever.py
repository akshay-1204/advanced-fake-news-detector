"""Retriever service for semantic search over pgvector chunks and recent news articles.

Features:
- Time-window filtering (EVIDENCE_WINDOW_DAYS for claims, 24 hours for today's news)
- Cosine similarity thresholding (SIMILARITY_THRESHOLD)
- Hybrid fallback to in-memory cosine computation for offline SQLite testing
"""
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.config import settings
from backend.db.models import Chunk, Article
from backend.services.embeddings import embed_query

logger = logging.getLogger(__name__)


def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine similarity between two lists of floats."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def retrieve_evidence_for_claim(
    claim_text: str,
    db: Session,
    top_k: Optional[int] = None,
    threshold: Optional[float] = None,
    window_days: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Retrieve supporting or contradicting chunks for a claim.

    Filters by published date within the last `window_days` (default EVIDENCE_WINDOW_DAYS)
    and cosine similarity above `threshold` (default SIMILARITY_THRESHOLD).
    """
    if not claim_text or not claim_text.strip():
        return []

    k = top_k or settings.RETRIEVAL_TOP_K
    sim_threshold = threshold if threshold is not None else settings.SIMILARITY_THRESHOLD
    days = window_days or settings.EVIDENCE_WINDOW_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    query_embedding = embed_query(claim_text)

    # Check if we are running on PostgreSQL with pgvector
    dialect_name = db.bind.dialect.name if db.bind else ""
    if dialect_name == "postgresql":
        try:
            # Native pgvector cosine distance: distance = 1 - similarity
            max_distance = 1.0 - sim_threshold
            results = (
                db.query(
                    Chunk,
                    (1 - Chunk.embedding.cosine_distance(query_embedding)).label("similarity")
                )
                .filter(Chunk.published_at >= cutoff)
                .filter(Chunk.embedding.cosine_distance(query_embedding) <= max_distance)
                .order_by(Chunk.embedding.cosine_distance(query_embedding).asc())
                .limit(k)
                .all()
            )

            evidence = []
            for chunk, sim in results:
                evidence.append({
                    "id": chunk.id,
                    "text": chunk.text,
                    "source": chunk.source,
                    "url": chunk.url,
                    "published_at": chunk.published_at,
                    "doc_type": chunk.doc_type,
                    "similarity": float(sim),
                })
            return evidence
        except Exception as exc:
            logger.warning("Postgres pgvector query failed (%s). Falling back to in-memory ranking.", exc)

    # In-memory fallback (used in unit tests / SQLite)
    candidate_chunks = db.query(Chunk).filter(Chunk.published_at >= cutoff).all()
    scored = []
    for chunk in candidate_chunks:
        chunk_emb = chunk.embedding
        if chunk_emb is not None:
            # Handle both list and pgvector Vector object
            emb_list = list(chunk_emb) if not isinstance(chunk_emb, list) else chunk_emb
            sim = _cosine_similarity(query_embedding, emb_list)
            if sim >= sim_threshold:
                scored.append((chunk, sim))

    scored.sort(key=lambda x: x[1], reverse=True)
    top_scored = scored[:k]

    return [
        {
            "id": c.id,
            "text": c.text,
            "source": c.source,
            "url": c.url,
            "published_at": c.published_at,
            "doc_type": c.doc_type,
            "similarity": float(sim),
        }
        for c, sim in top_scored
    ]


def retrieve_today_news(
    db: Session,
    topic: str = "general",
    max_items: int = 30
) -> List[Dict[str, Any]]:
    """Retrieve news articles from the last 24 hours counted from current moment.

    Filters by topic (if not 'general' or 'all') and orders by newest first.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    query = db.query(Article).filter(Article.published_at >= cutoff)

    if topic and topic.lower() not in ["general", "all", ""]:
        query = query.filter(Article.topic == topic.lower())

    articles = query.order_by(desc(Article.published_at)).limit(max_items).all()

    return [
        {
            "id": art.id,
            "source": art.source,
            "title": art.title,
            "url": art.url,
            "published_at": art.published_at,
            "topic": art.topic,
            "content": art.content,
        }
        for art in articles
    ]

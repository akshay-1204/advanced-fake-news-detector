"""Text chunking, embedding generation, and database storage for news articles."""
import hashlib
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from backend.db.models import Article, Chunk
from backend.services.embeddings import embed_texts

logger = logging.getLogger(__name__)


def compute_content_hash(text: str) -> str:
    """Generate SHA-256 hash of cleaned text for fast deduplication."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def chunk_text(text: str, chunk_size: int = 200, overlap: int = 30) -> List[str]:
    """Split text into chunks of approximately `chunk_size` words with `overlap` words."""
    words = text.split()
    if not words:
        return []

    if len(words) <= chunk_size:
        return [" ".join(words)]

    chunks = []
    step = max(1, chunk_size - overlap)
    for i in range(0, len(words), step):
        chunk_words = words[i:i + chunk_size]
        chunks.append(" ".join(chunk_words))
        if i + chunk_size >= len(words):
            break

    return chunks


def process_and_store_article(
    db: Session,
    source: str,
    title: str,
    url: str,
    published_at: datetime,
    content: str,
    language: str = "en",
    topic: str = "general",
    doc_type: str = "news"
) -> Optional[Article]:
    """Validate, deduplicate, chunk, embed, and persist an article into the database."""
    if not content or not content.strip():
        return None

    cleaned_content = content.strip()
    content_hash = compute_content_hash(cleaned_content)

    # Skip duplicates by hash or unique URL
    existing = db.query(Article).filter(
        (Article.content_hash == content_hash) | (Article.url == url)
    ).first()
    if existing:
        logger.debug("Article already exists (hash=%s, url=%s). Skipping.", content_hash[:8], url)
        return existing

    # 1. Create Article record
    article = Article(
        source=source,
        title=title,
        url=url,
        published_at=published_at,
        topic=topic,
        language=language,
        content=cleaned_content,
        content_hash=content_hash,
    )
    db.add(article)
    db.flush()  # Populates article.id

    # 2. Chunk text
    text_chunks = chunk_text(cleaned_content, chunk_size=200, overlap=30)
    if not text_chunks:
        db.commit()
        return article

    # 3. Generate embeddings in batch
    embeddings = embed_texts(text_chunks)

    # 4. Create Chunk records
    for idx, (chunk_str, emb) in enumerate(zip(text_chunks, embeddings)):
        chunk_record = Chunk(
            article_id=article.id,
            chunk_index=idx,
            text=chunk_str,
            embedding=emb,
            source=source,
            url=url,
            published_at=published_at,
            doc_type=doc_type,
        )
        db.add(chunk_record)

    db.commit()
    db.refresh(article)
    logger.info("Saved article '%s' with %d chunks.", title[:40], len(text_chunks))
    return article

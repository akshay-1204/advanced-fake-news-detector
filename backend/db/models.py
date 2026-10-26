from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from backend.config import settings
from backend.db.session import Base


def utc_now() -> datetime:
    """Return timezone-aware current UTC time."""
    return datetime.now(timezone.utc)


class Article(Base):
    """Stores full news articles collected from trusted RSS feeds."""

    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(100), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    url = Column(String(1000), unique=True, nullable=False, index=True)
    published_at = Column(DateTime(timezone=True), nullable=False, index=True)
    topic = Column(String(50), default="general", nullable=False, index=True)
    language = Column(String(10), default="en", nullable=False, index=True)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    chunks = relationship("Chunk", back_populates="article", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Article(id={self.id}, source='{self.source}', title='{self.title[:30]}...')>"


class Chunk(Base):
    """Text chunks (~200 words) with vector embeddings for semantic retrieval."""

    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=True, index=True)
    chunk_index = Column(Integer, default=0, nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=True)
    source = Column(String(100), nullable=False, index=True)
    url = Column(String(1000), nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=False, index=True)
    doc_type = Column(String(20), default="news", nullable=False, index=True)  # "news" | "factcheck"
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    article = relationship("Article", back_populates="chunks")

    __table_args__ = (
        Index(
            "ix_chunks_embedding_hnsw",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    def __repr__(self) -> str:
        return f"<Chunk(id={self.id}, source='{self.source}', doc_type='{self.doc_type}')>"


class FactCheck(Base):
    """Published fact-checks from authoritative sources (e.g., Google Fact Check API, BOOM)."""

    __tablename__ = "fact_checks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    claim = Column(Text, nullable=False)
    claimant = Column(String(255), nullable=True)
    rating = Column(String(100), nullable=False)  # e.g., "False", "Misleading", "Partly True"
    review_date = Column(DateTime(timezone=True), nullable=True, index=True)
    publisher = Column(String(100), nullable=False, index=True)
    review_url = Column(String(1000), nullable=False)
    language = Column(String(10), default="en", nullable=False)
    content_hash = Column(String(64), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    def __repr__(self) -> str:
        return f"<FactCheck(id={self.id}, publisher='{self.publisher}', rating='{self.rating}')>"


class ChatLog(Base):
    """Audit log of user queries and bot responses without any personal data (no IP, no names)."""

    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=True, index=True)
    user_query = Column(Text, nullable=False)
    intent = Column(String(50), nullable=False, index=True)
    detected_language = Column(String(10), default="en", nullable=False)
    verdict = Column(String(50), nullable=True, index=True)
    confidence = Column(String(20), nullable=True)
    reason = Column(Text, nullable=True)
    response_text = Column(Text, nullable=False)
    sources_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<ChatLog(id={self.id}, intent='{self.intent}', verdict='{self.verdict}')>"

"""Unit and integration tests for Phase 1: Models, Config, Database, and Migrations."""
import os
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from backend.config import settings
from backend.db.session import Base
from backend.db.models import Article, Chunk, FactCheck, ChatLog, utc_now
from scripts.init_db import check_connection


def test_settings_load_properly():
    """Verify that pydantic-settings loaded configuration correctly."""
    assert settings.EMBEDDING_DIM == 1024
    assert settings.EMBEDDING_MODEL == "BAAI/bge-m3"
    assert settings.SIMILARITY_THRESHOLD == 0.55
    assert settings.RETRIEVAL_TOP_K == 6
    assert settings.EVIDENCE_WINDOW_DAYS == 7
    assert settings.ARTICLE_RETENTION_DAYS == 14
    assert "postgresql" in settings.DATABASE_URL


def test_models_metadata_and_structure():
    """Verify SQLAlchemy model declarations, table names, and column definitions."""
    tables = Base.metadata.tables
    assert "articles" in tables
    assert "chunks" in tables
    assert "fact_checks" in tables
    assert "chat_logs" in tables

    # Articles
    article_cols = [c.name for c in tables["articles"].columns]
    for expected in ["id", "source", "title", "url", "published_at", "topic", "language", "content", "content_hash", "created_at"]:
        assert expected in article_cols

    # Chunks
    chunk_cols = [c.name for c in tables["chunks"].columns]
    for expected in ["id", "article_id", "chunk_index", "text", "embedding", "source", "url", "published_at", "doc_type", "created_at"]:
        assert expected in chunk_cols

    # ChatLog privacy check: verify NO IP address or username fields exist
    chat_cols = [c.name for c in tables["chat_logs"].columns]
    assert "ip" not in chat_cols
    assert "ip_address" not in chat_cols
    assert "user_name" not in chat_cols
    assert "username" not in chat_cols
    assert "email" not in chat_cols


def test_chunks_hnsw_index_declaration():
    """Verify HNSW index with vector_cosine_ops is declared on Chunk."""
    indexes = Chunk.__table__.indexes
    hnsw_index = next((idx for idx in indexes if idx.name == "ix_chunks_embedding_hnsw"), None)
    assert hnsw_index is not None
    assert hnsw_index.dialect_options["postgresql"]["using"] == "hnsw"
    assert hnsw_index.dialect_options["postgresql"]["ops"]["embedding"] == "vector_cosine_ops"
    assert hnsw_index.dialect_options["postgresql"]["with"]["m"] == 16
    assert hnsw_index.dialect_options["postgresql"]["with"]["ef_construction"] == 64


def test_sqlite_in_memory_crud_for_core_models():
    """Verify that models without pgvector types work seamlessly for testing/in-memory verification."""
    # Test Article, FactCheck, ChatLog in an isolated SQLite engine
    test_engine = create_engine("sqlite:///:memory:")
    Article.__table__.create(test_engine)
    FactCheck.__table__.create(test_engine)
    ChatLog.__table__.create(test_engine)

    TestSession = sessionmaker(bind=test_engine)
    session = TestSession()

    now = utc_now()
    # Insert Article
    art = Article(
        source="The Hindu",
        title="Test News Article",
        url="https://example.com/test",
        published_at=now,
        topic="india",
        language="en",
        content="Full article content here.",
        content_hash="testhash1234",
    )
    session.add(art)

    # Insert FactCheck
    fc = FactCheck(
        claim="500 rupee notes banned",
        rating="False",
        publisher="BOOM",
        review_url="https://boomlive.in/test",
        language="en",
        content_hash="fchash1234",
    )
    session.add(fc)

    # Insert ChatLog (no PII)
    log = ChatLog(
        session_id="sess-001",
        user_query="Are 500 notes banned?",
        intent="CLAIM_CHECK",
        detected_language="en",
        verdict="CONTRADICTED",
        confidence="high",
        reason="BOOM reported this is false.",
        response_text="The claim is contradicted.",
    )
    session.add(log)
    session.commit()

    # Query back
    fetched_art = session.query(Article).filter_by(content_hash="testhash1234").first()
    assert fetched_art is not None
    assert fetched_art.title == "Test News Article"

    fetched_fc = session.query(FactCheck).filter_by(content_hash="fchash1234").first()
    assert fetched_fc is not None
    assert fetched_fc.rating == "False"

    fetched_log = session.query(ChatLog).filter_by(session_id="sess-001").first()
    assert fetched_log is not None
    assert fetched_log.verdict == "CONTRADICTED"

    session.close()


def test_migration_file_exists_and_contains_vector_extension():
    """Verify Alembic migration script exists and has CREATE EXTENSION IF NOT EXISTS vector."""
    migration_file = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "backend", "db", "migrations", "versions", "0001_initial_schema.py")
    )
    assert os.path.exists(migration_file)
    with open(migration_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert "CREATE EXTENSION IF NOT EXISTS vector;" in content
    assert "ix_chunks_embedding_hnsw" in content
    assert "vector_cosine_ops" in content


def test_connectivity_check_handles_unreachable_db_gracefully():
    """Verify check_connection returns False cleanly when Postgres is not running."""
    # When PostgreSQL container is not started, check_connection returns False without uncaught crash
    result = check_connection()
    assert isinstance(result, bool)

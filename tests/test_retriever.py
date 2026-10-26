"""Unit tests for retriever: time-window filtering, thresholding, and cosine similarity."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Article, Chunk
from backend.services.retriever import retrieve_today_news, retrieve_evidence_for_claim, _cosine_similarity
from backend.services.embeddings import embed_query


def test_cosine_similarity_math():
    """Verify vector cosine similarity calculation."""
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]
    assert abs(_cosine_similarity(v1, v2) - 1.0) < 1e-6
    assert abs(_cosine_similarity(v1, v3) - 0.0) < 1e-6


def test_today_news_24h_window():
    """Verify articles older than 24 hours from current moment are excluded."""
    test_engine = create_engine("sqlite:///:memory:")
    Article.__table__.create(test_engine)

    TestSession = sessionmaker(bind=test_engine)
    session = TestSession()

    now = datetime.now(timezone.utc)
    recent_time = now - timedelta(hours=3)
    old_time = now - timedelta(hours=26)

    # 1 recent article
    session.add(Article(
        source="The Hindu",
        title="Recent Article",
        url="https://example.com/recent",
        published_at=recent_time,
        topic="general",
        language="en",
        content="Recent content",
        content_hash="h1"
    ))

    # 1 old article (>24h)
    session.add(Article(
        source="The Hindu",
        title="Old Article",
        url="https://example.com/old",
        published_at=old_time,
        topic="general",
        language="en",
        content="Old content",
        content_hash="h2"
    ))
    session.commit()

    results = retrieve_today_news(db=session, topic="general")
    assert len(results) == 1
    assert results[0]["title"] == "Recent Article"
    session.close()


def test_evidence_retrieval_threshold_and_window():
    """Verify claim evidence retrieval respects similarity threshold and window days."""
    test_engine = create_engine("sqlite:///:memory:")
    Article.__table__.create(test_engine)
    Chunk.__table__.create(test_engine)

    TestSession = sessionmaker(bind=test_engine)
    session = TestSession()

    now = datetime.now(timezone.utc)
    matching_text = "Reserve Bank of India monetary policy committee interest rate repo"
    unrelated_text = "Baking chocolate cake with vanilla frosting recipe"

    emb_match = embed_query(matching_text)
    emb_unrelated = embed_query(unrelated_text)

    # Fresh chunk matching query
    session.add(Chunk(
        text=matching_text,
        embedding=emb_match,
        source="NDTV",
        url="https://example.com/c1",
        published_at=now - timedelta(days=2),
        doc_type="news"
    ))

    # Fresh chunk unrelated
    session.add(Chunk(
        text=unrelated_text,
        embedding=emb_unrelated,
        source="Food Blog",
        url="https://example.com/c2",
        published_at=now - timedelta(days=1),
        doc_type="news"
    ))

    # Matching chunk but older than 7 days
    session.add(Chunk(
        text=matching_text,
        embedding=emb_match,
        source="Old News",
        url="https://example.com/c3",
        published_at=now - timedelta(days=10),
        doc_type="news"
    ))
    session.commit()

    evidence = retrieve_evidence_for_claim(
        claim_text=matching_text,
        db=session,
        threshold=0.5,
        window_days=7
    )

    assert len(evidence) == 1
    assert evidence[0]["source"] == "NDTV"
    session.close()

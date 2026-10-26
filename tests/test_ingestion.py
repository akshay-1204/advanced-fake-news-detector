"""Unit tests for ingestion: RSS/Atom parsing, chunking, and deduplication."""
import os
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Article, Chunk
from ingestion.fetch_rss import parse_feed_xml, parse_date_to_utc
from ingestion.chunk_embed_store import chunk_text, compute_content_hash, process_and_store_article


def test_rss_2_0_parsing():
    """Verify parsing of standard RSS 2.0 feed items."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_rss.xml")
    with open(fixture_path, "r", encoding="utf-8") as f:
        xml_content = f.read()

    items = parse_feed_xml(xml_content, source_name="Sample RSS Outlet", default_language="en", default_topic="general")
    assert len(items) == 2
    first = items[0]
    assert first["source"] == "Sample RSS Outlet"
    assert first["title"] == "RBI keeps repo rate unchanged at 6.5 percent"
    assert "https://example.com/rbi-rate-unchanged" in first["url"]
    assert first["published_at"].tzinfo == timezone.utc


def test_atom_parsing():
    """Verify parsing of Atom feed items and ISO 8601 timestamps."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_atom.xml")
    with open(fixture_path, "r", encoding="utf-8") as f:
        xml_content = f.read()

    items = parse_feed_xml(xml_content, source_name="Sample Atom Outlet", default_language="en", default_topic="technology")
    assert len(items) == 1
    first = items[0]
    assert first["source"] == "Sample Atom Outlet"
    assert "ISRO" in first["title"]
    assert first["published_at"].tzinfo == timezone.utc


def test_date_utc_conversion():
    """Verify RFC 2822 and ISO dates are parsed strictly to timezone-aware UTC."""
    rfc_date = "Fri, 09 Oct 2026 05:30:00 +0530"
    dt = parse_date_to_utc(rfc_date)
    assert dt is not None
    assert dt.tzinfo == timezone.utc
    assert dt.hour == 0
    assert dt.minute == 0

    iso_date = "2026-10-09T05:30:00Z"
    dt2 = parse_date_to_utc(iso_date)
    assert dt2 is not None
    assert dt2.tzinfo == timezone.utc


def test_chunking_word_bounds_and_overlap():
    """Verify word chunking with target size and overlap."""
    words = [f"word{i}" for i in range(250)]
    text = " ".join(words)

    chunks = chunk_text(text, chunk_size=200, overlap=30)
    assert len(chunks) == 2
    # First chunk has 200 words
    assert len(chunks[0].split()) == 200
    # Overlap check: last 30 words of chunk 0 should equal first 30 words of chunk 1
    c0_words = chunks[0].split()
    c1_words = chunks[1].split()
    assert c0_words[-30:] == c1_words[:30]


def test_deduplication_by_content_hash():
    """Verify identical articles are skipped based on content hash."""
    test_engine = create_engine("sqlite:///:memory:")
    Article.__table__.create(test_engine)
    Chunk.__table__.create(test_engine)

    TestSession = sessionmaker(bind=test_engine)
    session = TestSession()

    now = datetime.now(timezone.utc)
    text = "Unique news content for testing deduplication."

    # First insert
    art1 = process_and_store_article(
        db=session,
        source="NDTV",
        title="Breaking News",
        url="https://example.com/unique-1",
        published_at=now,
        content=text
    )
    assert art1 is not None

    # Second insert with same content but different URL
    art2 = process_and_store_article(
        db=session,
        source="NDTV",
        title="Breaking News Duplicate",
        url="https://example.com/unique-2",
        published_at=now,
        content=text
    )
    # Returns existing article without creating duplicate
    assert art2.id == art1.id

    articles_count = session.query(Article).count()
    assert articles_count == 1
    session.close()

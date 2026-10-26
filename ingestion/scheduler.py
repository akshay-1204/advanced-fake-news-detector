"""APScheduler periodic news ingestion and retention purge job for Satyavani AI."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db.session import SessionLocal
from backend.db.models import Article, Chunk
from ingestion.sources import TRUSTED_SOURCES
from ingestion.fetch_rss import fetch_feed
from ingestion.extract_text import extract_full_text
from ingestion.chunk_embed_store import process_and_store_article

logger = logging.getLogger(__name__)


def purge_old_articles(db: Optional[Session] = None) -> int:
    """Delete articles and associated chunks older than ARTICLE_RETENTION_DAYS."""
    owns_session = False
    if db is None:
        db = SessionLocal()
        owns_session = True

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.ARTICLE_RETENTION_DAYS)
        logger.info("Purging articles older than %s (%d days retention)...", cutoff, settings.ARTICLE_RETENTION_DAYS)

        # Cascading delete removes chunks linked via foreign key
        deleted = db.query(Article).filter(Article.published_at < cutoff).delete(synchronize_session=False)
        db.commit()
        logger.info("Purged %d expired articles.", deleted)
        return deleted
    except Exception as exc:
        db.rollback()
        logger.error("Failed to purge old articles: %s", exc)
        return 0
    finally:
        if owns_session:
            db.close()


def run_ingestion_cycle(db: Optional[Session] = None) -> int:
    """Run one full ingestion pass across all trusted news outlets.

    A failure in any individual source or article is caught and logged,
    never stopping the overall process.
    """
    logger.info("Starting news ingestion cycle across %d sources...", len(TRUSTED_SOURCES))
    owns_session = False
    if db is None:
        db = SessionLocal()
        owns_session = True

    total_added = 0
    try:
        for src in TRUSTED_SOURCES:
            src_name = src.get("name", "Unknown")
            try:
                items = fetch_feed(src)
                logger.info("Fetched %d items from %s", len(items), src_name)

                for item in items:
                    try:
                        url = item["url"]
                        summary = item.get("summary", "")
                        content = extract_full_text(url, fallback_summary=summary)

                        if not content:
                            content = summary or item["title"]

                        saved = process_and_store_article(
                            db=db,
                            source=src_name,
                            title=item["title"],
                            url=url,
                            published_at=item["published_at"],
                            content=content,
                            language=item.get("language", "en"),
                            topic=item.get("topic", "general"),
                            doc_type="news",
                        )
                        if saved:
                            total_added += 1
                    except Exception as item_err:
                        logger.warning("Error processing item '%s' from %s: %s", item.get("title", "")[:30], src_name, item_err)
            except Exception as src_err:
                # Failing source is logged and skipped, NEVER fatal
                logger.error("Source '%s' failed during feed fetch: %s", src_name, src_err)

        # Purge expired articles after ingestion pass
        purge_old_articles(db)

    finally:
        if owns_session:
            db.close()

    logger.info("Ingestion cycle complete. Processed %d articles.", total_added)
    return total_added


def start_scheduler():
    """Start the APScheduler background daemon."""
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_ingestion_cycle,
        "interval",
        minutes=settings.INGEST_INTERVAL_MINUTES,
        id="news_ingest_job",
        replace_existing=True
    )
    scheduler.start()
    logger.info("APScheduler started: running news ingestion every %d minutes.", settings.INGEST_INTERVAL_MINUTES)
    return scheduler

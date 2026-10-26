import os
import sys

# Ensure UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.db.session import SessionLocal
from ingestion.sources import TRUSTED_SOURCES
from ingestion.fetch_rss import fetch_feed
from ingestion.chunk_embed_store import process_and_store_article

def main():
    print("=== Ingesting Top Live News from RSS Feeds ===")
    db = SessionLocal()
    total = 0
    try:
        # Ingest from trusted India news sources
        india_sources = [s for s in TRUSTED_SOURCES if s.get("topic") == "india"]
        for src in india_sources:
            src_name = src["name"]
            print(f"Fetching from {src_name} ({src['rss_url']})...")
            try:
                items = fetch_feed(src)
                print(f" -> Found {len(items)} items from {src_name}")
                # Save top 5 items per source
                for item in items[:5]:
                    saved = process_and_store_article(
                        db=db,
                        source=src_name,
                        title=item["title"],
                        url=item["url"],
                        published_at=item["published_at"],
                        content=item.get("summary") or item["title"],
                        language=item.get("language", "en"),
                        topic="india",
                        doc_type="news",
                    )
                    if saved:
                        total += 1
                        print(f"    [+] Saved: {item['title'][:50]}...")
            except Exception as e:
                print(f" -> Error fetching {src_name}: {e}")
        print(f"=== Successfully ingested {total} new articles! ===")
    finally:
        db.close()

if __name__ == "__main__":
    main()

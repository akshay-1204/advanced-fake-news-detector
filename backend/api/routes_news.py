"""FastAPI router for news retrieval and FAQ shortcuts."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.chat import FAQItem
from backend.services.retriever import retrieve_today_news

router = APIRouter(tags=["News & FAQ"])


@router.get("/news/today")
def get_today_news(
    topic: str = Query("general", description="Topic filter: general, india, sports, technology, business, world"),
    db: Session = Depends(get_db)
):
    """Retrieve articles published in the last 24 hours (counted from current time)."""
    articles = retrieve_today_news(db=db, topic=topic, max_items=25)
    return {
        "topic": topic,
        "count": len(articles),
        "articles": [
            {
                "id": a["id"],
                "source": a["source"],
                "title": a["title"],
                "url": a["url"],
                "published_at": str(a["published_at"]),
                "topic": a["topic"],
            }
            for a in articles
        ]
    }


@router.get("/faq", response_model=List[FAQItem])
def get_faq_shortcuts():
    """Return preset FAQ topics for UI buttons."""
    return [
        FAQItem(label="Top news in the last 24 hours", query="top news today", topic="general"),
        FAQItem(label="India", query="India news in the last 24 hours", topic="india"),
        FAQItem(label="Sports", query="sports news in the last 24 hours", topic="sports"),
        FAQItem(label="Technology", query="technology news today", topic="technology"),
        FAQItem(label="Business", query="business and finance news today", topic="business"),
        FAQItem(label="World", query="world news in the last 24 hours", topic="world"),
    ]

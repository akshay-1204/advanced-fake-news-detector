#!/usr/bin/env python3
"""Seed demo data (articles, chunks, and fact-checks) into Satyavani AI database.

Allows immediate local testing of fact-checking and news queries.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.db.session import SessionLocal
from backend.db.models import Article, Chunk, FactCheck
from backend.services.embeddings import embed_texts
from ingestion.chunk_embed_store import compute_content_hash, chunk_text


DEMO_ARTICLES = [
    {
        "source": "The Hindu",
        "title": "RBI monetary policy committee keeps repo rate unchanged at 6.5 percent",
        "url": "https://www.thehindu.com/business/rbi-repo-rate-decision-2026/article1.ece",
        "topic": "business",
        "language": "en",
        "content": "The Reserve Bank of India monetary policy committee decided unanimously to keep the policy repo rate unchanged at 6.5 percent. Governor announced that headline inflation is trending downward, but persistence in food prices necessitates monetary vigilance.",
        "hours_ago": 2,
    },
    {
        "source": "NDTV",
        "title": "RBI holds repo rate steady at 6.5 percent for another meeting",
        "url": "https://www.ndtv.com/business/rbi-holds-repo-rate-steady-2026",
        "topic": "business",
        "language": "en",
        "content": "In its monetary policy review, the RBI decided to maintain the benchmark repo rate at 6.5 percent. The decision aligns with market expectations as the central bank balances economic growth with inflation targets.",
        "hours_ago": 1,
    },
    {
        "source": "BBC News",
        "title": "India beat Australia by 4 wickets in Mumbai cricket test match",
        "url": "https://www.bbc.com/sport/cricket/india-win-mumbai-test-2026",
        "topic": "sports",
        "language": "en",
        "content": "India secured a thrilling victory over Australia by 4 wickets at the Wankhede Stadium in Mumbai. Resuming the final day requiring 80 runs, the middle order held their nerve to chase down the target.",
        "hours_ago": 4,
    },
    {
        "source": "PIB",
        "title": "ISRO successfully launches Earth Observation Satellite into orbit",
        "url": "https://pib.gov.in/PressReleasePage.aspx?PRID=987654",
        "topic": "technology",
        "language": "en",
        "content": "The Indian Space Research Organisation (ISRO) successfully accomplished the launch of the new Earth Observation Satellite aboard the PSLV mission from Sriharikota. The satellite will aid agricultural and disaster monitoring.",
        "hours_ago": 5,
    },
    {
        "source": "The Hindu",
        "title": "హైదరాబాద్‌లో భారీ వర్షాల కారణంగా పాఠశాలలకు సెలవు ప్రకటించిన జిల్లా కలెక్టర్",
        "url": "https://www.thehindu.com/news/cities/Hyderabad/hyderabad-school-holiday-rain-te/article2.ece",
        "topic": "general",
        "language": "te",
        "content": "హైదరాబాద్‌లో కురుస్తున్న భారీ వర్షాల దృష్ట్యా రేపు అన్ని పాఠశాలలకు సెలవు ప్రకటిస్తూ విద్యాశాఖ మరియు కలెక్టర్ ఉత్తర్వులు జారీ చేశారు.",
        "hours_ago": 3,
    },
    {
        "source": "NDTV",
        "title": "आरबीआई ने नीतिगत ब्याज दरों में कोई बदलाव नहीं किया, रेपो रेट 6.5% पर बरकरार",
        "url": "https://khabar.ndtv.com/news/business/rbi-monetary-policy-repo-rate-steady-hi",
        "topic": "business",
        "language": "hi",
        "content": "भारतीय रिजर्व बैंक की मौद्रिक नीति समिति ने रेपो रेट को 6.5 प्रतिशत पर यथावत रखने का फैसला किया है। गवर्नर ने कहा कि विकास को समर्थन देते हुए महंगाई को लक्ष्य के दायरे में रखना प्राथमिकता है।",
        "hours_ago": 2,
    }
]

DEMO_FACT_CHECKS = [
    {
        "claim": "Government will ban 500 rupee notes from tomorrow / 500 notes discontinued",
        "claimant": "Viral WhatsApp Forward",
        "rating": "False",
        "publisher": "BOOM",
        "review_url": "https://www.boomlive.in/fact-check/500-rupee-notes-ban-viral-message-false",
        "language": "en",
        "days_ago": 1,
    },
    {
        "claim": "UNESCO declared Indian National Anthem Jana Gana Mana as best anthem in the world",
        "claimant": "Social Media Rumour",
        "rating": "False",
        "publisher": "PIB Fact Check",
        "review_url": "https://factcheck.pib.gov.in/unesco-national-anthem-hoax",
        "language": "en",
        "days_ago": 2,
    },
    {
        "claim": "सरकार ने 500 रुपये के नोट बंद करने का आदेश दिया है",
        "claimant": "सोशल मीडिया वायरल मैसेज",
        "rating": "False",
        "publisher": "BOOM",
        "review_url": "https://hindi.boomlive.in/fact-check/500-note-bandi-fake-news",
        "language": "hi",
        "days_ago": 1,
    }
]


def seed():
    """Populate database with sample articles, embeddings, and fact checks."""
    print("=== Seeding Demo Data for Satyavani AI ===")
    db = SessionLocal()
    now = datetime.now(timezone.utc)

    try:
        # 1. Seed Articles and Chunks
        for art_data in DEMO_ARTICLES:
            content = art_data["content"]
            h = compute_content_hash(content)
            pub_date = now - timedelta(hours=art_data["hours_ago"])

            existing = db.query(Article).filter(Article.content_hash == h).first()
            if existing:
                print(f"[SKIP] Article already exists: {art_data['title'][:35]}...")
                continue

            art = Article(
                source=art_data["source"],
                title=art_data["title"],
                url=art_data["url"],
                published_at=pub_date,
                topic=art_data["topic"],
                language=art_data["language"],
                content=content,
                content_hash=h,
            )
            db.add(art)
            db.flush()

            # Chunks
            chunks = chunk_text(content, chunk_size=200, overlap=30)
            embeddings = embed_texts(chunks)
            for idx, (txt, emb) in enumerate(zip(chunks, embeddings)):
                c = Chunk(
                    article_id=art.id,
                    chunk_index=idx,
                    text=txt,
                    embedding=emb,
                    source=art.source,
                    url=art.url,
                    published_at=pub_date,
                    doc_type="news",
                )
                db.add(c)
            print(f"[ADDED] Article: {art.title[:45]} ({len(chunks)} chunks)")

        # 2. Seed Fact-Checks
        for fc_data in DEMO_FACT_CHECKS:
            claim_text = fc_data["claim"]
            fc_hash = compute_content_hash(claim_text)

            existing_fc = db.query(FactCheck).filter(FactCheck.content_hash == fc_hash).first()
            if existing_fc:
                continue

            fc = FactCheck(
                claim=claim_text,
                claimant=fc_data["claimant"],
                rating=fc_data["rating"],
                publisher=fc_data["publisher"],
                review_url=fc_data["review_url"],
                language=fc_data["language"],
                content_hash=fc_hash,
                review_date=now - timedelta(days=fc_data["days_ago"]),
            )
            db.add(fc)
            print(f"[ADDED] Fact-Check: {fc.claim[:40]}... [{fc.rating}]")

        db.commit()
        print("=== Seed Completed Successfully! ===")
    except Exception as exc:
        db.rollback()
        print(f"[ERROR] Seeding failed: {exc}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()

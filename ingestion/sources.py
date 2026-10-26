"""Trusted news outlets and their RSS feed URLs for Satyavani AI."""
from typing import List, Dict, Any

TRUSTED_SOURCES: List[Dict[str, Any]] = [
    {
        "name": "The Hindu",
        "rss_url": "https://www.thehindu.com/news/national/feeder/default.rss",
        "language": "en",
        "topic": "india"
    },
    {
        "name": "NDTV",
        "rss_url": "https://feeds.feedburner.com/ndtvnews-india-news",
        "language": "en",
        "topic": "india"
    },
    {
        "name": "Indian Express",
        "rss_url": "https://indianexpress.com/section/india/feed/",
        "language": "en",
        "topic": "india"
    },
    {
        "name": "Hindustan Times",
        "rss_url": "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml",
        "language": "en",
        "topic": "india"
    },
    {
        "name": "Times of India",
        "rss_url": "https://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms",
        "language": "en",
        "topic": "india"
    },
    {
        "name": "BBC News",
        "rss_url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "language": "en",
        "topic": "world"
    },
    {
        "name": "Al Jazeera",
        "rss_url": "https://www.aljazeera.com/xml/rss/all.xml",
        "language": "en",
        "topic": "world"
    },
    {
        "name": "PIB",
        "rss_url": "https://pib.gov.in/PressReleaseRSS.aspx",
        "language": "en",
        "topic": "india"
    },
]

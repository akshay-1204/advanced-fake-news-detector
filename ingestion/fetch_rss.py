"""RSS and Atom feed fetcher and XML parser for Satyavani AI.

CRITICAL IMPLEMENTATION RULES:
1. XML element comparison MUST use `elem is not None` (never truthiness `if elem:`
   because empty XML elements evaluate to False in Python).
2. All dates must be converted to timezone-aware UTC datetime. Items without
   a valid date are skipped.
3. Polite HTTP requests with custom User-Agent and timeouts.
"""
import email.utils
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SatyavaniAI/1.0 (News Fact-Checking Bot)"


def parse_date_to_utc(date_str: Optional[str]) -> Optional[datetime]:
    """Parse various date formats (RFC 822, RFC 2822, ISO 8601) to timezone-aware UTC datetime."""
    if not date_str or not date_str.strip():
        return None

    cleaned = date_str.strip()

    # Try RFC 2822 / RFC 822 format (standard RSS)
    try:
        dt = email.utils.parsedate_to_datetime(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    # Try ISO 8601 / Atom formats
    try:
        iso_clean = cleaned.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso_clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    return None


def parse_feed_xml(xml_content: str, source_name: str, default_language: str = "en", default_topic: str = "general") -> List[Dict[str, Any]]:
    """Parse RSS or Atom XML content into a structured list of article dictionaries."""
    items: List[Dict[str, Any]] = []
    if not xml_content or not xml_content.strip():
        return items

    try:
        root = ET.fromstring(xml_content)
    except Exception as exc:
        logger.warning("Failed to parse XML for %s: %s", source_name, exc)
        return items

    tag = root.tag.lower()

    # Atom Feed
    if "feed" in tag:
        # Strip namespace if present
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"

        entries = root.findall(f"{ns}entry")
        for entry in entries:
            title_elem = entry.find(f"{ns}title")
            title = title_elem.text.strip() if title_elem is not None and title_elem.text is not None else ""

            # Atom link can be <link href="..."/> or <link>...</link>
            link = ""
            link_elem = entry.find(f"{ns}link")
            if link_elem is not None:
                link = link_elem.get("href") or link_elem.text or ""
            link = link.strip()

            # Date: check published or updated
            pub_elem = entry.find(f"{ns}published")
            if pub_elem is None:
                pub_elem = entry.find(f"{ns}updated")
            pub_date_str = pub_elem.text if pub_elem is not None and pub_elem.text is not None else None
            pub_date = parse_date_to_utc(pub_date_str)

            if not pub_date or not title or not link:
                continue

            # Summary
            summary_elem = entry.find(f"{ns}summary")
            if summary_elem is None:
                summary_elem = entry.find(f"{ns}content")
            summary = summary_elem.text.strip() if summary_elem is not None and summary_elem.text is not None else ""

            items.append({
                "source": source_name,
                "title": title,
                "url": link,
                "published_at": pub_date,
                "summary": summary,
                "language": default_language,
                "topic": default_topic,
            })

    # RSS 2.0 Feed
    else:
        channel = root.find("channel")
        item_elements = channel.findall("item") if channel is not None else root.findall(".//item")

        for item in item_elements:
            title_elem = item.find("title")
            title = title_elem.text.strip() if title_elem is not None and title_elem.text is not None else ""

            link_elem = item.find("link")
            link = link_elem.text.strip() if link_elem is not None and link_elem.text is not None else ""

            # Sometimes link is inside guid if permalink
            if not link:
                guid_elem = item.find("guid")
                if guid_elem is not None and guid_elem.text is not None:
                    if guid_elem.text.startswith("http"):
                        link = guid_elem.text.strip()

            pub_elem = item.find("pubDate")
            if pub_elem is None:
                pub_elem = item.find("dc:date", {"dc": "http://purl.org/dc/elements/1.1/"})
            pub_date_str = pub_elem.text if pub_elem is not None and pub_elem.text is not None else None
            pub_date = parse_date_to_utc(pub_date_str)

            if not pub_date or not title or not link:
                continue

            desc_elem = item.find("description")
            summary = desc_elem.text.strip() if desc_elem is not None and desc_elem.text is not None else ""

            items.append({
                "source": source_name,
                "title": title,
                "url": link,
                "published_at": pub_date,
                "summary": summary,
                "language": default_language,
                "topic": default_topic,
            })

    return items


def fetch_feed(source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Politely fetch and parse an RSS/Atom feed from a source configuration."""
    name = source_config.get("name", "Unknown")
    url = source_config.get("rss_url", "")
    lang = source_config.get("language", "en")
    topic = source_config.get("topic", "general")

    if not url:
        return []

    try:
        headers = {"User-Agent": USER_AGENT}
        with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                logger.warning("Feed %s returned status %d", name, resp.status_code)
                return []
            return parse_feed_xml(resp.text, name, default_language=lang, default_topic=topic)
    except Exception as exc:
        logger.warning("Error fetching feed for %s from %s: %s", name, url, exc)
        return []

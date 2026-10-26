"""Full article text extraction using trafilatura with graceful fallback to RSS summary."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def extract_full_text(url: str, fallback_summary: str = "") -> str:
    """Fetch and extract cleaned main text from article URL.

    Falls back to `fallback_summary` if trafilatura extraction fails or returns empty.
    """
    if not url:
        return fallback_summary.strip()

    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if downloaded is not None:
            text = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
                no_fallback=False
            )
            if text and text.strip():
                return text.strip()
    except Exception as exc:
        logger.debug("Trafilatura failed for %s: %s", url, exc)

    return fallback_summary.strip()

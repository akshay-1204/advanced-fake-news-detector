"""Google Fact Check Tools API client.
Gracefully handles missing API keys and network errors.
"""
import logging
from typing import List, Dict, Any
import httpx

from backend.config import settings

logger = logging.getLogger(__name__)


def search_google_fact_check(query: str, language_code: str = "en") -> List[Dict[str, Any]]:
    """Query the Google Fact Check Tools API for verified claims.

    If GOOGLE_FACTCHECK_API_KEY is not configured or an error occurs,
    returns an empty list gracefully without throwing an exception.
    """
    api_key = settings.GOOGLE_FACTCHECK_API_KEY
    if not api_key or not api_key.strip():
        logger.debug("GOOGLE_FACTCHECK_API_KEY not configured. Skipping external Google Fact Check query.")
        return []

    if not query or not query.strip():
        return []

    url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
    params = {
        "query": query.strip(),
        "key": api_key.strip(),
    }
    if language_code in ["hi", "te"]:
        params["languageCode"] = language_code

    try:
        response = httpx.get(url, params=params, timeout=5.0)
        if response.status_code != 200:
            logger.warning("Google Fact Check API returned status %s: %s", response.status_code, response.text)
            return []

        data = response.json()
        claims = data.get("claims", [])
        results = []

        for c in claims:
            reviews = c.get("claimReview", [])
            for r in reviews:
                publisher_info = r.get("publisher", {})
                results.append({
                    "claim": c.get("text", ""),
                    "claimant": c.get("claimant", ""),
                    "rating": r.get("textualRating", "Unknown"),
                    "publisher": publisher_info.get("name", "Fact-Checker"),
                    "review_url": r.get("url", ""),
                    "review_date": r.get("reviewDate", ""),
                    "title": r.get("title", c.get("text", "")),
                })
        return results
    except Exception as exc:
        logger.warning("Error querying Google Fact Check API: %s", exc)
        return []

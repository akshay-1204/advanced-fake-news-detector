"""Streamlit component for rendering color-coded fact-check verdict cards.

Colors:
- VERIFIED: Green (#2e7d32)
- PARTIAL: Amber (#f57f17)
- CONTRADICTED: Red (#c62828)
- UNVERIFIED: Slate Grey (#616161)
All dynamic user/model strings are safely HTML escaped.
"""
import html
from typing import List, Dict, Any, Optional


CARD_STYLES = {
    "VERIFIED": {
        "border": "#2e7d32",
        "bg": "#f1f8e9",
        "badge_bg": "#2e7d32",
        "badge_text": "#ffffff",
        "icon": "VERIFIED"
    },
    "PARTIAL": {
        "border": "#f57f17",
        "bg": "#fffde7",
        "badge_bg": "#f57f17",
        "badge_text": "#ffffff",
        "icon": "PARTIAL"
    },
    "CONTRADICTED": {
        "border": "#c62828",
        "bg": "#ffebee",
        "badge_bg": "#c62828",
        "badge_text": "#ffffff",
        "icon": "CONTRADICTED"
    },
    "UNVERIFIED": {
        "border": "#757575",
        "bg": "#f5f5f5",
        "badge_bg": "#757575",
        "badge_text": "#ffffff",
        "icon": "UNVERIFIED"
    }
}


def render_verdict_card_html(
    verdict: Optional[str],
    confidence: Optional[str],
    reason: Optional[str],
    sources: List[Dict[str, Any]]
) -> str:
    """Generate safe, responsive HTML for a verdict card."""
    norm_verdict = (verdict or "UNVERIFIED").strip().upper()
    style = CARD_STYLES.get(norm_verdict, CARD_STYLES["UNVERIFIED"])

    conf_str = (confidence or "low").strip().capitalize()
    escaped_reason = html.escape(reason or "No explanation provided.")

    sources_html_list = []
    for s in sources:
        outlet = html.escape(str(s.get("outlet", "Source")))
        title = html.escape(str(s.get("title", "Read report")))
        link = html.escape(str(s.get("link", "#")))
        pub_time = html.escape(str(s.get("published_time", "")))

        item_html = (
            f"<li style='margin-bottom: 6px;'>"
            f"<strong>{outlet}</strong>: "
            f"<a href='{link}' target='_blank' rel='noopener noreferrer' style='color: #1565c0; text-decoration: underline;'>"
            f"{title}</a>"
            f"{f' <span style=\"color:#888; font-size:0.85em;\">({pub_time})</span>' if pub_time else ''}"
            f"</li>"
        )
        sources_html_list.append(item_html)

    sources_block = ""
    if sources_html_list:
        sources_block = f"""
        <div style="margin-top: 12px; border-top: 1px solid rgba(0,0,0,0.1); padding-top: 8px;">
            <div style="font-size: 0.85em; font-weight: bold; color: #555; text-transform: uppercase;">Verified Sources & Evidence:</div>
            <ul style="margin: 6px 0 0 16px; padding: 0; font-size: 0.9em; line-height: 1.4;">
                {''.join(sources_html_list)}
            </ul>
        </div>
        """

    card_html = f"""
    <div style="border-left: 6px solid {style['border']}; background-color: {style['bg']}; padding: 14px 18px; border-radius: 6px; margin: 10px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
            <span style="background-color: {style['badge_bg']}; color: {style['badge_text']}; padding: 4px 12px; border-radius: 14px; font-weight: bold; font-size: 0.85em; letter-spacing: 0.5px;">
                {style['icon']}
            </span>
            <span style="font-size: 0.85em; color: #555; font-weight: 500;">
                Confidence: <strong style="color: #222;">{conf_str}</strong>
            </span>
        </div>
        <div style="font-size: 0.98em; line-height: 1.5; color: #1e1e1e; margin-top: 6px;">
            {escaped_reason}
        </div>
        {sources_block}
    </div>
    """
    return card_html

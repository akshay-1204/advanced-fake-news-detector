"""Streamlit Chat UI for Satyavani AI.

Features:
- Multilingual font support (English, Hindi, Telugu)
- Color-coded verdict cards for claim verification
- FAQ quick-inquiry buttons
- Live backend and service health status
- Resilient error handling when services are down or degraded
"""
import os
import sys
import uuid

# Ensure project root is in sys.path so 'frontend' package is always resolvable
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import streamlit as st

from frontend.api_client import SatyavaniAPIClient
from frontend.components.verdict_card import render_verdict_card_html
from frontend.components.faq_buttons import render_faq_buttons

# Page Configuration
st.set_page_config(
    page_title="Satyavani AI | Voice of Truth",
    page_icon="🛡️",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Custom Typography & Styling for English, Hindi, and Telugu
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+Devanagari:wght@400;600;700&family=Noto+Sans+Telugu:wght@400;600;700&display=swap');

html, body, [class*="css"], .stMarkdown {
    font-family: 'Inter', 'Noto Sans Devanagari', 'Noto Sans Telugu', -apple-system, BlinkMacSystemFont, sans-serif;
}

.main-title {
    font-size: 2.1rem;
    font-weight: 700;
    color: #1a237e;
    margin-bottom: 2px;
}
.sub-title {
    font-size: 1.0rem;
    color: #555;
    margin-bottom: 20px;
}
.status-pill {
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.85em;
    font-weight: 600;
}
.status-online { background-color: #e8f5e9; color: #2e7d32; }
.status-offline { background-color: #ffebee; color: #c62828; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Session State Initialization
if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {
            "role": "assistant",
            "content": (
                "Namaste! I am **Satyavani AI** (Voice of Truth), an anti-misinformation news fact-checking assistant.\n\n"
                "• Paste any news claim, social media post, or WhatsApp rumour to verify it.\n"
                "• Ask about today's news headlines or click any topic button below.\n"
                "• I answer **only** from trusted news outlets and published fact-checks in English, Hindi, or Telugu."
            ),
            "verdict": None,
            "confidence": None,
            "sources": []
        }
    ]

if "queued_query" not in st.session_state:
    st.session_state["queued_query"] = None

client = SatyavaniAPIClient()

# Sidebar: System Health & Info
with st.sidebar:
    st.markdown("### 🛡️ Satyavani AI")
    st.markdown("*Anti-Hallucination News Verifier*")
    st.divider()

    # Health probe
    health_resp = client.get_health()
    if health_resp.get("connected"):
        data = health_resp.get("data", {})
        status_txt = data.get("status", "ok")
        st.markdown(f"**Backend Status**: <span class='status-pill status-online'>{status_txt.upper()}</span>", unsafe_allow_html=True)
        st.caption(f"DB: {data.get('database', 'unknown')} | LLM: {data.get('llm_config', {}).get('provider', 'ollama')}")
    else:
        st.markdown("**Backend Status**: <span class='status-pill status-offline'>OFFLINE</span>", unsafe_allow_html=True)
        st.caption(f"Error: {health_resp.get('error')}")

    st.divider()
    st.markdown("#### How Satyavani Works")
    st.markdown(
        "1. **Trusted Sources Only**: The Hindu, NDTV, Indian Express, BBC, etc.\n"
        "2. **Strict Verdict Rules**:\n"
        "   - 🟢 **VERIFIED**: Confirmed by 2+ independent outlets.\n"
        "   - 🟡 **PARTIAL**: 1 outlet supports or minor detail differs.\n"
        "   - 🔴 **CONTRADICTED**: Direct debunk from trusted source or fact-check.\n"
        "   - ⚪ **UNVERIFIED**: No evidence found (does not prove falsehood).\n"
        "3. **Zero Hallucination**: Does not fabricate facts beyond retrieved passages."
    )

    st.divider()
    if st.button("🗑️ Clear Conversation", use_container_width=True):
        st.session_state["messages"] = []
        st.session_state["queued_query"] = None
        st.rerun()

# Main Header
st.markdown("<div class='main-title'>🛡️ Satyavani AI</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Voice of Truth: Fact-checking news and social media claims against verified sources</div>", unsafe_allow_html=True)

# Callback for FAQ button clicks
def handle_faq_click(query_text: str):
    st.session_state["queued_query"] = query_text
    st.rerun()

render_faq_buttons(on_select_query=handle_faq_click)
st.divider()

# Display Chat History
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        if msg.get("verdict"):
            card_html = render_verdict_card_html(
                verdict=msg["verdict"],
                confidence=msg.get("confidence"),
                reason=msg.get("content"),
                sources=msg.get("sources", [])
            )
            st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.markdown(msg["content"])
            # Display any sources if available for non-verdict answers
            if msg.get("sources"):
                with st.expander("🔗 Sources Cited"):
                    for s in msg["sources"]:
                        outlet = s.get("outlet", "Source")
                        title = s.get("title", "Article")
                        link = s.get("link", "#")
                        st.markdown(f"- **{outlet}**: [{title}]({link})")

# Determine incoming query (either typed or FAQ button clicked)
incoming_query = None
if st.session_state["queued_query"]:
    incoming_query = st.session_state["queued_query"]
    st.session_state["queued_query"] = None
else:
    user_input = st.chat_input("Enter a news claim or question (English / हिंदी / తెలుగు)...")
    if user_input:
        incoming_query = user_input

# Handle New Message
if incoming_query:
    clean_query = incoming_query.strip()
    if len(clean_query) > 500:
        st.warning("⚠️ Your message exceeds 500 characters. Please provide a shorter claim or question.")
    else:
        # 1. Add user message
        st.session_state["messages"].append({
            "role": "user",
            "content": clean_query
        })
        with st.chat_message("user"):
            st.markdown(clean_query)

        # 2. Assistant response
        with st.chat_message("assistant"):
            with st.spinner("🔍 Checking trusted sources and published fact-checks..."):
                resp = client.send_chat(
                    query=clean_query,
                    session_id=st.session_state["session_id"]
                )

                if resp.get("success"):
                    data = resp.get("data", {})
                    reply_text = data.get("reply", "")
                    verdict = data.get("verdict")
                    confidence = data.get("confidence")
                    sources = data.get("sources", [])

                    if verdict:
                        card_html = render_verdict_card_html(
                            verdict=verdict,
                            confidence=confidence,
                            reason=reply_text,
                            sources=sources
                        )
                        st.markdown(card_html, unsafe_allow_html=True)
                    else:
                        st.markdown(reply_text)
                        if sources:
                            with st.expander("🔗 Sources Cited"):
                                for s in sources:
                                    outlet = s.get("outlet", "Source")
                                    title = s.get("title", "Article")
                                    link = s.get("link", "#")
                                    st.markdown(f"- **{outlet}**: [{title}]({link})")

                    st.session_state["messages"].append({
                        "role": "assistant",
                        "content": reply_text,
                        "verdict": verdict,
                        "confidence": confidence,
                        "sources": sources
                    })

                else:
                    err_msg = resp.get("error", "An unexpected error occurred.")
                    st.error(f"⚠️ {err_msg}")
                    st.session_state["messages"].append({
                        "role": "assistant",
                        "content": f"⚠️ {err_msg}",
                        "verdict": None,
                        "confidence": None,
                        "sources": []
                    })

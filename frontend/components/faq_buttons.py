"""Streamlit component for FAQ and quick topic inquiry buttons."""
from typing import List, Dict, Callable
import streamlit as st

DEFAULT_FAQ = [
    {"label": "Top news in the last 24 hours", "query": "Top news in the last 24 hours"},
    {"label": "India News", "query": "Top India news today"},
    {"label": "Sports", "query": "Sports news in the last 24 hours"},
    {"label": "Technology", "query": "Technology news today"},
    {"label": "Business", "query": "Business and economic news today"},
    {"label": "World", "query": "World news today"},
]


def render_faq_buttons(on_select_query: Callable[[str], None]):
    """Render horizontal FAQ shortcut buttons. Clicking sets the query and executes."""
    st.markdown("<p style='font-size:0.9em; font-weight:600; color:#555; margin-bottom:6px;'>Quick Topics & FAQ:</p>", unsafe_allow_html=True)

    cols = st.columns(len(DEFAULT_FAQ))
    for idx, item in enumerate(DEFAULT_FAQ):
        with cols[idx]:
            if st.button(item["label"], key=f"faq_btn_{idx}", use_container_width=True):
                on_select_query(item["query"])

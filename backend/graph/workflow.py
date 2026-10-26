"""LangGraph workflow definition for Satyavani AI routing and execution."""
import logging
from typing import Optional, Dict, Any
from langgraph.graph import StateGraph, END
from sqlalchemy.orm import Session

from backend.graph.state import SatyavaniState
from backend.graph.nodes import (
    classify_intent_node,
    today_news_node,
    weather_node,
    claim_check_node,
    small_talk_node,
)
from backend.schemas.chat import IntentType

logger = logging.getLogger(__name__)


def route_by_intent(state: SatyavaniState) -> str:
    """Conditional edge router based on classified intent."""
    intent = state.get("intent", IntentType.CLAIM_CHECK.value)
    if intent == IntentType.TODAY_NEWS.value:
        return "today_news"
    elif intent == IntentType.WEATHER.value:
        return "weather"
    elif intent == IntentType.SMALL_TALK.value:
        return "small_talk"
    else:
        return "claim_check"


def create_satyavani_workflow():
    """Build and compile the LangGraph StateGraph."""
    graph = StateGraph(SatyavaniState)

    # 1. Add nodes
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("today_news", today_news_node)
    graph.add_node("weather", weather_node)
    graph.add_node("claim_check", claim_check_node)
    graph.add_node("small_talk", small_talk_node)

    # 2. Add entry point
    graph.set_entry_point("classify_intent")

    # 3. Add conditional edges
    graph.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "today_news": "today_news",
            "weather": "weather",
            "claim_check": "claim_check",
            "small_talk": "small_talk",
        }
    )

    # 4. Each terminal node leads to END
    graph.add_edge("today_news", END)
    graph.add_edge("weather", END)
    graph.add_edge("claim_check", END)
    graph.add_edge("small_talk", END)

    return graph.compile()


# Precompiled app instance
workflow_app = create_satyavani_workflow()


def run_satyavani_workflow(
    user_message: str,
    session_id: Optional[str] = None,
    db: Optional[Session] = None
) -> SatyavaniState:
    """Execute the full Satyavani graph from an input message and database context."""
    initial_state: SatyavaniState = {
        "user_message": user_message,
        "session_id": session_id,
        "intent": IntentType.CLAIM_CHECK.value,
        "topic": "general",
        "city": None,
        "language": "en",
        "claim": None,
        "evidence": [],
        "fact_checks": [],
        "verdict": None,
        "confidence": None,
        "reason": None,
        "reply": "",
        "sources": [],
        "db": db,
    }

    final_state = workflow_app.invoke(initial_state)
    return final_state

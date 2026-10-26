"""State definition for Satyavani AI LangGraph workflow."""
from typing import TypedDict, Optional, List, Dict, Any


class SatyavaniState(TypedDict):
    # Inputs
    user_message: str
    session_id: Optional[str]

    # Classification fields
    intent: str
    topic: str
    city: Optional[str]
    language: str
    claim: Optional[str]

    # Retrieval and external facts
    evidence: List[Dict[str, Any]]
    fact_checks: List[Dict[str, Any]]

    # Judgement and outputs
    verdict: Optional[str]
    confidence: Optional[str]
    reason: Optional[str]
    reply: str
    sources: List[Dict[str, Any]]

    # Transient runtime context (optional DB session)
    db: Optional[Any]

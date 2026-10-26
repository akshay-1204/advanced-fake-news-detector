"""FastAPI router for user chat interactions and claim checking."""
import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db.models import ChatLog
from backend.schemas.chat import ChatRequest, ChatResponse, SourceItem
from backend.graph.workflow import run_satyavani_workflow

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Chat"])


@router.post("/chat", response_model=ChatResponse)
def handle_chat_message(
    payload: ChatRequest,
    db: Session = Depends(get_db)
):
    """Processes user queries/claims through the LangGraph fact-checking workflow.

    Enforces input length <= 500 chars and records chat interaction without personal data.
    """
    user_query = payload.query.strip()
    if not user_query:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query cannot be empty.")
    if len(user_query) > 500:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query exceeds maximum length of 500 characters.")

    try:
        result_state = run_satyavani_workflow(
            user_message=user_query,
            session_id=payload.session_id,
            db=db,
        )

        sources_models = [
            SourceItem(
                outlet=s.get("outlet", "Unknown"),
                title=s.get("title", ""),
                link=s.get("link", ""),
                published_time=str(s.get("published_time", ""))
            )
            for s in result_state.get("sources", [])
        ]

        # Audit log to ChatLog WITHOUT personal data (no IP, no names)
        try:
            log_record = ChatLog(
                session_id=payload.session_id,
                user_query=user_query,
                intent=result_state.get("intent", "CLAIM_CHECK"),
                detected_language=result_state.get("language", "en"),
                verdict=result_state.get("verdict"),
                confidence=result_state.get("confidence"),
                reason=result_state.get("reason"),
                response_text=result_state.get("reply", ""),
                sources_json=json.dumps([s.model_dump() for s in sources_models])
            )
            db.add(log_record)
            db.commit()
        except Exception as log_err:
            db.rollback()
            logger.warning("Could not persist ChatLog: %s", log_err)

        return ChatResponse(
            intent=result_state.get("intent", "CLAIM_CHECK"),
            verdict=result_state.get("verdict"),
            confidence=result_state.get("confidence"),
            reason=result_state.get("reason"),
            reply=result_state.get("reply", ""),
            sources=sources_models,
            language=result_state.get("language", "en")
        )

    except Exception as exc:
        logger.error("Unhandled error in /chat route: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while analyzing the claim. Please try again."
        )

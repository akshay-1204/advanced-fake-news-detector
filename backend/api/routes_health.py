"""Health check endpoint reporting status of Database, LLM, and Embeddings."""
import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db.session import get_db
from backend.services.embeddings import embed_query

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])


@router.get("/health")
def check_health(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Inspect and report operational health of database, embeddings, and LLM configuration."""
    health_status: Dict[str, Any] = {
        "status": "healthy",
        "database": "unknown",
        "embeddings": "unknown",
        "llm_config": {
            "provider": settings.LLM_PROVIDER,
            "model": settings.LLM_MODEL,
        }
    }

    # 1. Database check
    try:
        db.execute(text("SELECT 1;"))
        health_status["database"] = "connected"
    except Exception as exc:
        health_status["database"] = f"unreachable: {str(exc)}"
        health_status["status"] = "degraded"

    # 2. Embeddings check
    try:
        vec = embed_query("test probe")
        if len(vec) == settings.EMBEDDING_DIM:
            health_status["embeddings"] = f"ready (dim={len(vec)})"
        else:
            health_status["embeddings"] = f"unexpected dim {len(vec)}"
            health_status["status"] = "degraded"
    except Exception as exc:
        health_status["embeddings"] = f"error: {str(exc)}"
        health_status["status"] = "degraded"

    # 3. LLM Configuration check
    provider = settings.LLM_PROVIDER.lower()
    if provider == "gemini" and not settings.GEMINI_API_KEY:
        health_status["llm_config"]["warning"] = "GEMINI_API_KEY is not set."
    elif provider == "groq" and not settings.GROQ_API_KEY:
        health_status["llm_config"]["warning"] = "GROQ_API_KEY is not set."
    else:
        health_status["llm_config"]["status"] = "configured"

    return health_status

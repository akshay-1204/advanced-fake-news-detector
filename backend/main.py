"""FastAPI main application entrypoint for Satyavani AI."""
import time
import logging
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Dict, List

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.api import routes_chat, routes_news, routes_health
from ingestion.scheduler import start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("satyavani_api")

# In-memory sliding window rate limiter
_request_records: Dict[str, List[float]] = defaultdict(list)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup checks and background scheduler initialization."""
    logger.info("=== Starting Satyavani AI Backend ===")
    logger.info("LLM Provider: %s (Model: %s)", settings.LLM_PROVIDER, settings.LLM_MODEL)
    logger.info("Embedding Dim: %d (Model: %s)", settings.EMBEDDING_DIM, settings.EMBEDDING_MODEL)
    logger.info("Evidence Window: %d days | Similarity Threshold: %.2f", settings.EVIDENCE_WINDOW_DAYS, settings.SIMILARITY_THRESHOLD)

    # Start ingestion scheduler in background
    scheduler = None
    try:
        scheduler = start_scheduler()
    except Exception as exc:
        logger.warning("Could not start background APScheduler: %s", exc)

    yield

    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped.")


app = FastAPI(
    title="Satyavani AI Backend API",
    description="Anti-hallucination news fact-checking and inquiry engine.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate-limits calls to sensitive endpoints like /chat based on client IP."""
    if request.url.path == "/chat" and request.method == "POST":
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - 60.0

        # Purge records older than 1 minute
        history = [t for t in _request_records[client_ip] if t > window_start]
        if len(history) >= settings.RATE_LIMIT_PER_MINUTE:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": f"Rate limit exceeded ({settings.RATE_LIMIT_PER_MINUTE} requests/min). Please slow down."
                }
            )

        history.append(now)
        _request_records[client_ip] = history

    response: Response = await call_next(request)
    return response


# Include Routers
app.include_router(routes_chat.router)
app.include_router(routes_news.router)
app.include_router(routes_health.router)


@app.get("/")
def root():
    return {
        "service": "Satyavani AI",
        "tagline": "Voice of Truth - News Fact-Checking Chatbot",
        "docs": "/docs",
        "health": "/health"
    }

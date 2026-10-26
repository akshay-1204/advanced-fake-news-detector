"""API endpoint tests for FastAPI: /chat, /news/today, /faq, /health, input validation, and privacy."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.db.session import get_db, Base
from backend.db.models import Article, FactCheck, ChatLog, utc_now
from backend.services.llm import set_mock_llm_handler


from sqlalchemy.pool import StaticPool

# Setup isolated test SQLite database for API tests with StaticPool for thread sharing
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Article.__table__.create(test_engine)
FactCheck.__table__.create(test_engine)
ChatLog.__table__.create(test_engine)



def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_health_endpoint():
    """Verify GET /health returns operational diagnostics."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "embeddings" in data
    assert "llm_config" in data


def test_faq_endpoint():
    """Verify GET /faq returns topic list."""
    response = client.get("/faq")
    assert response.status_code == 200
    faqs = response.json()
    assert len(faqs) >= 6
    labels = [f["label"] for f in faqs]
    assert "India" in labels
    assert "Sports" in labels


def test_news_today_endpoint():
    """Verify GET /news/today endpoint."""
    response = client.get("/news/today?topic=general")
    assert response.status_code == 200
    data = response.json()
    assert "articles" in data
    assert data["topic"] == "general"


def test_chat_empty_input_validation():
    """Verify POST /chat rejects empty string."""
    response = client.post("/chat", json={"query": "   "})
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_chat_oversized_input_validation():
    """Verify POST /chat rejects queries longer than 500 characters."""
    oversized = "a" * 501
    response = client.post("/chat", json={"query": oversized})
    assert response.status_code in [400, 422]


def test_chat_smalltalk_workflow_and_privacy():
    """Verify smalltalk returns greeting and ChatLog records interaction without personal data."""
    # Mock LLM to return SMALL_TALK
    def mock_llm(prompt: str, json_mode: bool) -> str:
        return '{"intent":"SMALL_TALK","topic":"general","city":null,"language":"en","claim":null}'

    set_mock_llm_handler(mock_llm)
    try:
        response = client.post("/chat", json={"query": "Hello Satyavani!", "session_id": "test-session-123"})
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "SMALL_TALK"
        assert "Satyavani" in data["reply"]

        # Check privacy in database
        db = TestingSessionLocal()
        log = db.query(ChatLog).filter_by(session_id="test-session-123").first()
        assert log is not None
        assert log.intent == "SMALL_TALK"
        assert log.user_query == "Hello Satyavani!"

        # Ensure no IP address column exists in ChatLog table
        columns = [c.name for c in ChatLog.__table__.columns]
        assert "ip" not in columns
        assert "ip_address" not in columns
        assert "user_name" not in columns
        db.close()

    finally:
        set_mock_llm_handler(None)

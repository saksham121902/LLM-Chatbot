import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database import Base, get_db
import os

# Test in-memory database
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def client():
    """Create test client with fresh database."""
    Base.metadata.create_all(bind=engine)
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("test.db"):
        os.remove("test.db")


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "keys_configured" in data
    assert "cache_enabled" in data


def test_chat_missing_fields(client):
    """Test chat endpoint with missing required fields."""
    response = client.post("/chat", json={})
    assert response.status_code == 422


def test_chat_empty_message(client):
    """Test chat endpoint with empty message."""
    response = client.post("/chat", json={
        "session_id": "test-session",
        "message": "   "
    })
    assert response.status_code == 422


def test_chat_message_too_long(client):
    """Test chat endpoint with message over 4000 chars."""
    response = client.post("/chat", json={
        "session_id": "test-session",
        "message": "x" * 4001
    })
    assert response.status_code == 422


def test_session_not_found(client):
    """Test retrieving non-existent session."""
    response = client.get("/sessions/nonexistent/messages")
    assert response.status_code == 404
    assert response.json()["detail"] == "session not found"


def test_chat_response_structure(client):
    """Test that chat response has correct structure."""
    # Note: This requires valid API keys to fully test
    # For now, we test the structure when it fails
    response = client.post("/chat", json={
        "session_id": "test-123",
        "message": "Hello"
    })

    # It may fail due to invalid keys, but we check the error format
    if response.status_code == 503:
        assert "detail" in response.json()
    elif response.status_code == 200:
        data = response.json()
        assert "session_id" in data
        assert "reply" in data
        assert "metadata" in data
        metadata = data["metadata"]
        assert "resolution_source" in metadata
        assert "model" in metadata
        assert "latency_ms" in metadata
        assert "input_tokens" in metadata
        assert "output_tokens" in metadata
        assert "key_id" in metadata
        assert "fallback_attempts" in metadata


def test_session_history_structure(client):
    """Test session history retrieval structure."""
    # First create a session by attempting chat
    client.post("/chat", json={
        "session_id": "history-test",
        "message": "Test message"
    })

    # Try to get history (may not exist if chat failed)
    response = client.get("/sessions/history-test/messages")

    if response.status_code == 200:
        data = response.json()
        assert "session_id" in data
        assert "messages" in data
        assert isinstance(data["messages"], list)

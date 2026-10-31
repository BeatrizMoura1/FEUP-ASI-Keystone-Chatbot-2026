import httpx
import pytest
from fastapi.testclient import TestClient

from app import chat, llm
from app.config import settings
from app.llm import LLMError
from app.main import DATABASE_UNAVAILABLE_MESSAGE, UNEXPECTED_ERROR_MESSAGE, app
from app.routes import chat as chat_routes
from app.routes.chat import AI_FAILED_MESSAGE
from tests.conftest import login_as

UNREACHABLE_DATABASE_URL = "postgresql://localhost:1/unreachable?connect_timeout=2"


@pytest.fixture
def gemini_configured(monkeypatch) -> None:
    """Route questions through the real `generate` with a dummy Gemini key, no waits between retries.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Used to set the Gemini settings and restore `chat.generate`.
    """
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "gemini_model", "test-model")
    monkeypatch.setattr(settings, "llm_retry_wait_seconds", 0)
    monkeypatch.setattr(chat, "generate", llm.generate)


def test_llm_failure_shows_a_plain_message_without_internal_details(client, monkeypatch):
    def failing_generate(system_prompt: str, user_prompt: str) -> str:
        raise LLMError("Gemini returned HTTP 400: API key not valid (internal detail)")

    monkeypatch.setattr(chat, "generate", failing_generate)
    login_as(client, "employee", "employee123")

    response = client.post("/api/ask", json={"question": "Carry-over days?"})

    assert response.status_code == 502
    assert response.json() == {"error": AI_FAILED_MESSAGE}
    assert "internal detail" not in response.text


@pytest.mark.parametrize(
    "network_error",
    [httpx.ReadTimeout("read timed out"), httpx.ConnectError("connection refused")],
)
def test_gemini_timeout_or_connection_failure_becomes_ai_failed(client, monkeypatch, gemini_configured, network_error):
    def failing_post(*args, **kwargs):
        raise network_error

    monkeypatch.setattr(llm.httpx, "post", failing_post)
    login_as(client, "employee", "employee123")

    response = client.post("/api/ask", json={"question": "Carry-over days?"})

    assert response.status_code == 502
    assert response.json() == {"error": AI_FAILED_MESSAGE}
    assert client.get("/api/conversations").json() == []


def test_too_long_question_is_rejected(client):
    login_as(client, "employee", "employee123")

    response = client.post("/api/ask", json={"question": "x" * 2001})

    assert response.status_code == 422


def test_unreachable_database_gives_503_with_a_plain_message(client, monkeypatch):
    login_as(client, "employee", "employee123")
    monkeypatch.setattr(settings, "database_url", UNREACHABLE_DATABASE_URL)

    for response in (
        client.get("/api/conversations"),
        client.post("/api/login", json={"username": "employee", "password": "employee123"}),
    ):
        assert response.status_code == 503
        assert response.json() == {"detail": DATABASE_UNAVAILABLE_MESSAGE}


def test_unexpected_error_gives_500_with_a_plain_message(client, monkeypatch):
    def broken_list_conversations(user: dict) -> list[dict]:
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(chat_routes, "list_conversations", broken_list_conversations)
    login_as(client, "employee", "employee123")
    client_without_raising = TestClient(app, raise_server_exceptions=False, cookies=client.cookies)

    response = client_without_raising.get("/api/conversations")

    assert response.status_code == 500
    assert response.json() == {"detail": UNEXPECTED_ERROR_MESSAGE}
    assert "secret internal detail" not in response.text

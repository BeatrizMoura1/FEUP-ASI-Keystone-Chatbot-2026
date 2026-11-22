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
    monkeypatch.setattr(settings, "llm_transient_retry_wait_seconds", 0)
    monkeypatch.setattr(chat, "generate", llm.generate)


def gemini_replies(monkeypatch, responses: list[httpx.Response]) -> list[int]:
    """Make `httpx.post` return the given Gemini responses in order and count the calls.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Used to replace `httpx.post` inside `app.llm`.
    responses : list[httpx.Response]
        Responses to return, one per call; the last one repeats once the list runs out.

    Returns
    -------
    list[int]
        One entry is appended per call, so its length is the number of calls made.
    """
    calls: list[int] = []

    def fake_post(*args, **kwargs) -> httpx.Response:
        calls.append(1)
        return responses[min(len(calls), len(responses)) - 1]

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    return calls


GEMINI_OK_RESPONSE = httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "reply"}]}}]})


def test_llm_failure_shows_a_plain_message_without_internal_details(client, monkeypatch):
    """An LLM error shows the plain failure message, never the provider's details."""
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
    """A Gemini timeout or connection failure gives the plain failure message and saves nothing."""
    def failing_post(*args, **kwargs):
        raise network_error

    monkeypatch.setattr(llm.httpx, "post", failing_post)
    login_as(client, "employee", "employee123")

    response = client.post("/api/ask", json={"question": "Carry-over days?"})

    assert response.status_code == 502
    assert response.json() == {"error": AI_FAILED_MESSAGE}
    assert client.get("/api/conversations").json() == []


def test_brief_gemini_failure_is_retried_then_answers(monkeypatch, gemini_configured):
    """A Gemini 503 ("model overloaded") is retried, and the next successful reply is returned."""
    calls = gemini_replies(monkeypatch, [httpx.Response(503, text="overloaded"), GEMINI_OK_RESPONSE])

    assert llm.generate("system", "user") == "reply"
    assert len(calls) == 2


def test_dropped_connection_is_retried_then_answers(monkeypatch, gemini_configured):
    """A refused connection is retried, and the next successful reply is returned."""
    calls: list[int] = []

    def connection_fails_once(*args, **kwargs) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectError("connection refused")
        return GEMINI_OK_RESPONSE

    monkeypatch.setattr(llm.httpx, "post", connection_fails_once)

    assert llm.generate("system", "user") == "reply"
    assert len(calls) == 2


def test_persistent_gemini_failure_gives_ai_failed_after_retries(client, monkeypatch, gemini_configured):
    """When Gemini keeps answering 503, the user gets the plain failure message after every retry is used."""
    calls = gemini_replies(monkeypatch, [httpx.Response(503, text="overloaded")])
    login_as(client, "employee", "employee123")

    response = client.post("/api/ask", json={"question": "Carry-over days?"})

    assert response.status_code == 502
    assert response.json() == {"error": AI_FAILED_MESSAGE}
    assert len(calls) == settings.llm_transient_retries + 1


@pytest.mark.parametrize("status_code", [400, 403])
def test_request_errors_are_not_retried(monkeypatch, gemini_configured, status_code):
    """A bad request or a rejected key is not retried, so a real problem shows at once."""
    calls = gemini_replies(monkeypatch, [httpx.Response(status_code, text="bad request")])

    with pytest.raises(LLMError):
        llm.generate("system", "user")
    assert len(calls) == 1


def test_timeout_is_not_retried(monkeypatch, gemini_configured):
    """A Gemini timeout is not retried, so a stuck call does not keep the user waiting several times over."""
    calls: list[int] = []

    def timed_out_post(*args, **kwargs) -> httpx.Response:
        calls.append(1)
        raise httpx.ReadTimeout("read timed out")

    monkeypatch.setattr(llm.httpx, "post", timed_out_post)

    with pytest.raises(LLMError):
        llm.generate("system", "user")
    assert len(calls) == 1


def test_too_long_question_is_rejected(client):
    """A question over 2000 characters is rejected."""
    login_as(client, "employee", "employee123")

    response = client.post("/api/ask", json={"question": "x" * 2001})

    assert response.status_code == 422


def test_unreachable_database_gives_503_with_a_plain_message(client, monkeypatch):
    """When the database is unreachable, requests get 503 with a plain message, login included."""
    login_as(client, "employee", "employee123")
    monkeypatch.setattr(settings, "database_url", UNREACHABLE_DATABASE_URL)

    for response in (
        client.get("/api/conversations"),
        client.post("/api/login", json={"username": "employee", "password": "employee123"}),
    ):
        assert response.status_code == 503
        assert response.json() == {"detail": DATABASE_UNAVAILABLE_MESSAGE}


def test_unexpected_error_gives_500_with_a_plain_message(client, monkeypatch):
    """Any unhandled error gives 500 with a plain message, never the internal details."""
    def broken_list_conversations(user: dict) -> list[dict]:
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(chat_routes, "list_conversations", broken_list_conversations)
    login_as(client, "employee", "employee123")
    client_without_raising = TestClient(app, raise_server_exceptions=False, cookies=client.cookies)

    response = client_without_raising.get("/api/conversations")

    assert response.status_code == 500
    assert response.json() == {"detail": UNEXPECTED_ERROR_MESSAGE}
    assert "secret internal detail" not in response.text

from app import chat, llm
from app.chat import parse_llm_reply
from app.config import NO_ANSWER_TEXT
from app.documents import document_name_from_filename
from tests.conftest import login_as

ALLOWED_NAMES = {"Employee Handbook Leave and Hybrid Work"}


def test_parse_valid_json():
    raw_reply = '{"answer": "25 working days.", "sources": ["Employee Handbook Leave and Hybrid Work"]}'

    assert parse_llm_reply(raw_reply, ALLOWED_NAMES) == {
        "answer": "25 working days.", "sources": ["Employee Handbook Leave and Hybrid Work"]
    }


def test_parse_json_wrapped_in_markdown_fence():
    raw_reply = '```json\n{"answer": "Before 10:00.", "sources": ["Employee Handbook Leave and Hybrid Work"]}\n```'

    assert parse_llm_reply(raw_reply, ALLOWED_NAMES)["answer"] == "Before 10:00."


def test_parse_malformed_json_falls_back_to_raw_text():
    parsed_reply = parse_llm_reply("The answer is 25 days {broken", ALLOWED_NAMES)

    assert parsed_reply == {"answer": "The answer is 25 days {broken", "sources": []}


def test_parse_drops_sources_the_user_cannot_see():
    raw_reply = '{"answer": "x", "sources": ["Employee Handbook Leave and Hybrid Work", "03_Secret"]}'

    assert parse_llm_reply(raw_reply, ALLOWED_NAMES)["sources"] == ["Employee Handbook Leave and Hybrid Work"]


def test_parse_no_answer_clears_sources():
    raw_reply = '{"answer": "No answer found", "sources": ["Employee Handbook Leave and Hybrid Work"]}'

    assert parse_llm_reply(raw_reply, ALLOWED_NAMES) == {"answer": NO_ANSWER_TEXT, "sources": []}


def test_rate_limit_retries_then_returns_429(client, monkeypatch):
    call_counter = {"num_calls": 0}

    def always_rate_limited(system_prompt: str, user_prompt: str) -> str:
        call_counter["num_calls"] += 1
        raise llm.RateLimitError("429")

    monkeypatch.setattr(llm, "_call_gemini", always_rate_limited)
    monkeypatch.setattr(llm.settings, "llm_provider", "gemini")
    monkeypatch.setattr(llm.settings, "llm_retry_wait_seconds", 0)
    monkeypatch.setattr(chat, "generate", llm.generate)
    login_as(client, "employee", "employee123")

    response = client.post("/api/ask", json={"question": "anything"})

    assert response.status_code == 429
    assert "rate-limited" in response.json()["error"]
    assert call_counter["num_calls"] == llm.settings.llm_max_retries + 1


def test_document_name_from_filename():
    assert document_name_from_filename("Project_A_Design_Review_Minutes_2026-09-24.md") == (
        "Project A Design Review Minutes 2026-09-24"
    )

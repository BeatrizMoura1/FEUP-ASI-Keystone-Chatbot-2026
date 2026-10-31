import json

import pytest

from app import chat
from tests.conftest import login_as

SOURCE_NAME = "Employee Handbook Leave and Hybrid Work"


@pytest.fixture
def fake_llm(monkeypatch) -> list[str]:
    """Replace the LLM with a fake that numbers its answers and always cites the Employee Handbook.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Used to replace `chat.generate`.

    Returns
    -------
    list of str
        Every prompt the fake LLM received.
    """
    received_prompts = []

    def fake_generate(system_prompt: str, user_prompt: str) -> str:
        received_prompts.append(user_prompt)
        return json.dumps({"answer": f"Answer number {len(received_prompts)}", "sources": [SOURCE_NAME]})

    monkeypatch.setattr(chat, "generate", fake_generate)
    return received_prompts


def ask_and_rate(client, question: str, is_positive: bool) -> dict:
    """Ask a question as the logged-in user and rate its answer.

    Parameters
    ----------
    client : TestClient
        Logged-in client.
    question : str
        Question to ask.
    is_positive : bool
        True for thumbs up.

    Returns
    -------
    dict
        The /api/ask response.
    """
    answer = client.post("/api/ask", json={"question": question}).json()
    client.post("/api/ratings", json={"message_id": answer["message_id"], "is_positive": is_positive})
    return answer


def test_admin_sees_ratings_newest_first(client, fake_llm):
    login_as(client, "employee", "employee123")
    ask_and_rate(client, "Carry-over days?", True)
    login_as(client, "newhire", "newhire123")
    ask_and_rate(client, "Remote work abroad?", False)
    login_as(client, "admin", "admin123")

    ratings = client.get("/api/admin/ratings").json()

    rating_rows = [
        (rating["username"], rating["question"], rating["answer"], rating["is_positive"]) for rating in ratings
    ]
    assert rating_rows == [
        ("newhire", "Remote work abroad?", "Answer number 2", False),
        ("employee", "Carry-over days?", "Answer number 1", True),
    ]
    assert all(rating["created_at"] and rating["is_chat_deleted"] is False for rating in ratings)


def test_changed_rating_shows_its_latest_value_once(client, fake_llm):
    login_as(client, "employee", "employee123")
    answer = ask_and_rate(client, "Carry-over days?", True)
    client.post("/api/ratings", json={"message_id": answer["message_id"], "is_positive": False})
    login_as(client, "admin", "admin123")

    ratings = client.get("/api/admin/ratings").json()

    assert len(ratings) == 1
    assert ratings[0]["is_positive"] is False


def test_rating_stays_visible_after_its_chat_is_deleted(client, fake_llm):
    login_as(client, "employee", "employee123")
    answer = ask_and_rate(client, "Carry-over days?", False)
    client.delete(f"/api/conversations/{answer['conversation_id']}")
    login_as(client, "admin", "admin123")

    ratings = client.get("/api/admin/ratings").json()

    assert [(rating["question"], rating["is_chat_deleted"]) for rating in ratings] == [("Carry-over days?", True)]


def test_no_ratings_gives_an_empty_list(client):
    login_as(client, "admin", "admin123")

    assert client.get("/api/admin/ratings").json() == []


def test_employee_cannot_read_ratings(client, fake_llm):
    login_as(client, "employee", "employee123")
    ask_and_rate(client, "Carry-over days?", True)

    assert client.get("/api/admin/ratings").status_code == 403


def test_ratings_require_login(client):
    assert client.get("/api/admin/ratings").status_code == 401

from app import chat
from app.conversations import make_title
from app.db import get_connection
from app.llm import LLMError
from tests.conftest import CITED_DOCUMENT_NAME, login_as


def test_first_question_creates_a_titled_conversation(client, numbered_llm):
    login_as(client, "employee", "employee123")

    response = client.post("/api/ask", json={"question": "How many leave days do I get?"})

    assert response.status_code == 200
    assert response.json()["title"] == "How many leave days do I get?"
    conversation_list = client.get("/api/conversations").json()
    assert [conversation["id"] for conversation in conversation_list] == [response.json()["conversation_id"]]


def test_follow_up_question_is_added_to_the_same_conversation(client, numbered_llm):
    login_as(client, "employee", "employee123")
    conversation_id = client.post("/api/ask", json={"question": "First?"}).json()["conversation_id"]

    client.post("/api/ask", json={"question": "Second?", "conversation_id": conversation_id})

    conversation = client.get(f"/api/conversations/{conversation_id}").json()
    assert [(message["role"], message["content"]) for message in conversation["messages"]] == [
        ("user", "First?"), ("assistant", "Answer number 1"), ("user", "Second?"), ("assistant", "Answer number 2"),
    ]
    assert conversation["messages"][1]["sources"][0]["name"] == CITED_DOCUMENT_NAME
    assert len(client.get("/api/conversations").json()) == 1


def test_history_survives_logout_and_login(client, numbered_llm):
    login_as(client, "employee", "employee123")
    conversation_id = client.post("/api/ask", json={"question": "Remember me?"}).json()["conversation_id"]
    client.post("/api/logout")

    login_as(client, "employee", "employee123")

    assert client.get(f"/api/conversations/{conversation_id}").json()["messages"][0]["content"] == "Remember me?"


def test_users_cannot_see_or_change_each_others_conversations(client, numbered_llm):
    login_as(client, "admin", "admin123")
    admin_answer = client.post("/api/ask", json={"question": "Admin secret question"}).json()
    client.post("/api/logout")
    login_as(client, "employee", "employee123")

    assert client.get("/api/conversations").json() == []
    assert client.get(f"/api/conversations/{admin_answer['conversation_id']}").status_code == 404
    assert client.delete(f"/api/conversations/{admin_answer['conversation_id']}").status_code == 404
    rating_response = client.post("/api/ratings", json={"message_id": admin_answer["message_id"], "is_positive": True})
    assert rating_response.status_code == 404
    hijack_response = client.post(
        "/api/ask", json={"question": "Add to admin chat", "conversation_id": admin_answer["conversation_id"]}
    )
    assert hijack_response.status_code == 404
    assert len(numbered_llm) == 1


def test_delete_conversation_removes_its_messages(client, numbered_llm):
    login_as(client, "employee", "employee123")
    conversation_id = client.post("/api/ask", json={"question": "Delete me"}).json()["conversation_id"]

    assert client.delete(f"/api/conversations/{conversation_id}").status_code == 200

    assert client.get("/api/conversations").json() == []
    assert client.get(f"/api/conversations/{conversation_id}").status_code == 404
    with get_connection() as connection:
        assert connection.execute("SELECT count(*) FROM messages").fetchone()["count"] == 0


def test_rating_is_stored_and_shown_in_history(client, numbered_llm):
    login_as(client, "employee", "employee123")
    answer = client.post("/api/ask", json={"question": "Rate this"}).json()

    client.post("/api/ratings", json={"message_id": answer["message_id"], "is_positive": True})
    client.post("/api/ratings", json={"message_id": answer["message_id"], "is_positive": False})

    with get_connection() as connection:
        stored_ratings = connection.execute("SELECT question, answer, is_positive FROM ratings").fetchall()
    assert [tuple(rating.values()) for rating in stored_ratings] == [("Rate this", "Answer number 1", False)]
    conversation = client.get(f"/api/conversations/{answer['conversation_id']}").json()
    assert conversation["messages"][1]["rating"] is False


def test_failed_llm_call_saves_nothing(client, monkeypatch):
    def broken_generate(system_prompt: str, user_prompt: str) -> str:
        raise LLMError("service down")

    monkeypatch.setattr(chat, "generate", broken_generate)
    login_as(client, "employee", "employee123")

    assert client.post("/api/ask", json={"question": "Will fail"}).status_code == 502

    assert client.get("/api/conversations").json() == []


def test_make_title_shortens_long_questions():
    long_question = "What   is the\nprocedure " + "for checking calculations " * 5

    conversation_title = make_title(long_question)

    assert len(conversation_title) == 60
    assert conversation_title.startswith("What is the procedure for")
    assert conversation_title.endswith("…")

from tests.conftest import CITED_DOCUMENT_NAME, login_as


def test_admin_sees_unanswered_questions_newest_first(client, queued_llm):
    """The admin sees every user's "No answer found." questions, newest first; answered ones are not listed (S4)."""
    queued_llm.reply_with("No answer found.", [])
    queued_llm.reply_with("You can carry over 5 days.", [CITED_DOCUMENT_NAME])
    queued_llm.reply_with("No answer found.", [])
    login_as(client, "employee", "employee123")
    client.post("/api/ask", json={"question": "Is there a company car?"})
    client.post("/api/ask", json={"question": "Carry-over days?"})
    login_as(client, "newhire", "newhire123")
    client.post("/api/ask", json={"question": "What is the Linha Verde red alert?"})
    login_as(client, "admin", "admin123")

    unanswered_questions = client.get("/api/admin/unanswered").json()

    assert [(row["username"], row["question"]) for row in unanswered_questions] == [
        ("newhire", "What is the Linha Verde red alert?"),
        ("employee", "Is there a company car?"),
    ]
    assert all(row["created_at"] for row in unanswered_questions)


def test_uncited_reply_is_listed_as_unanswered(client, queued_llm):
    """A reply that cites no permitted document is saved as "No answer found." and so is listed."""
    queued_llm.reply_with("Invented answer.", [])
    login_as(client, "employee", "employee123")
    client.post("/api/ask", json={"question": "Is there a company car?"})
    login_as(client, "admin", "admin123")

    unanswered_questions = client.get("/api/admin/unanswered").json()

    assert [row["question"] for row in unanswered_questions] == ["Is there a company car?"]


def test_follow_up_lists_its_own_question(client, queued_llm):
    """In a chat with several questions, the listed question is the one right before the "No answer found."."""
    queued_llm.reply_with("You can carry over 5 days.", [CITED_DOCUMENT_NAME])
    queued_llm.reply_with("No answer found.", [])
    login_as(client, "employee", "employee123")
    first_answer = client.post("/api/ask", json={"question": "Carry-over days?"}).json()
    client.post(
        "/api/ask", json={"question": "And a company car?", "conversation_id": first_answer["conversation_id"]}
    )
    login_as(client, "admin", "admin123")

    unanswered_questions = client.get("/api/admin/unanswered").json()

    assert [row["question"] for row in unanswered_questions] == ["And a company car?"]


def test_deleted_chat_is_not_listed(client, queued_llm):
    """A question from a chat the user deleted is no longer listed."""
    queued_llm.reply_with("No answer found.", [])
    login_as(client, "employee", "employee123")
    answer = client.post("/api/ask", json={"question": "Is there a company car?"}).json()
    client.delete(f"/api/conversations/{answer['conversation_id']}")
    login_as(client, "admin", "admin123")

    assert client.get("/api/admin/unanswered").json() == []


def test_employee_cannot_read_unanswered_questions(client):
    """Employees get 403 on the unanswered questions list."""
    login_as(client, "employee", "employee123")

    assert client.get("/api/admin/unanswered").status_code == 403


def test_unanswered_questions_require_login(client):
    """The unanswered questions list needs a login."""
    assert client.get("/api/admin/unanswered").status_code == 401

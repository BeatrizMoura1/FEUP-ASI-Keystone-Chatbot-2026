import pytest

from app.config import NO_ANSWER_TEXT, settings
from app.conversations import HIDDEN_ANSWER_TEXT, is_answer_visible
from app.db import get_connection
from tests.conftest import FakeLLM, login_as

PROJECT_A_DOCUMENT_NAME = "Project A Linha Verde Metro Extension Execution Plan"
SECRET_ANSWER_TEXT = "The trigger level is 20 mm (PROJECT-A-ONLY-PHRASE)."


def get_employee_user_id() -> int:
    """Look up the demo employee's user id.

    Returns
    -------
    int
        The employee's id.
    """
    with get_connection() as connection:
        return connection.execute("SELECT id FROM users WHERE username = 'employee'").fetchone()["id"]


def set_employee_project_a_access(has_access: bool) -> None:
    """Grant or revoke the employee's access to Project A.

    Parameters
    ----------
    has_access : bool
        True to grant, False to revoke.
    """
    employee_user_id = get_employee_user_id()
    with get_connection() as connection:
        if has_access:
            connection.execute(
                "INSERT INTO user_projects (user_id, project_id) SELECT %s, id FROM projects WHERE code = 'A'",
                (employee_user_id,),
            )
        else:
            connection.execute(
                "DELETE FROM user_projects WHERE user_id = %s "
                "AND project_id = (SELECT id FROM projects WHERE code = 'A')",
                (employee_user_id,),
            )


def ask_project_a_question(client, queued_llm: FakeLLM) -> dict:
    """Log in as the employee and get a saved answer that cites a Project A document.

    Parameters
    ----------
    client : TestClient
        The test client.
    queued_llm : FakeLLM
        The fake LLM.

    Returns
    -------
    dict
        The /api/ask response body.
    """
    login_as(client, "employee", "employee123")
    queued_llm.reply_with(SECRET_ANSWER_TEXT, [PROJECT_A_DOCUMENT_NAME])
    return client.post("/api/ask", json={"question": "What is the red trigger level?"}).json()


def test_follow_up_question_gets_the_earlier_messages(client, queued_llm):
    login_as(client, "employee", "employee123")
    queued_llm.reply_with("You need a helmet and a gas detector.", ["Site Health and Safety Rules"])
    conversation_id = client.post("/api/ask", json={"question": "What PPE do I need in a tunnel?"}).json()[
        "conversation_id"
    ]

    client.post("/api/ask", json={"question": "Who provides it?", "conversation_id": conversation_id})

    assert "CONVERSATION SO FAR" not in queued_llm.received_prompts[0]
    follow_up_prompt = queued_llm.received_prompts[1]
    assert "User: What PPE do I need in a tunnel?" in follow_up_prompt
    assert "Assistant: You need a helmet and a gas detector." in follow_up_prompt
    assert follow_up_prompt.endswith("QUESTION: Who provides it?")


def test_history_is_limited_to_the_configured_number_of_messages(client, queued_llm, monkeypatch):
    monkeypatch.setattr(settings, "chat_history_messages", 2)
    for answer_number in (1, 2, 3):
        queued_llm.reply_with(f"Cited answer {answer_number}", ["Site Health and Safety Rules"])
    login_as(client, "employee", "employee123")
    conversation_id = client.post("/api/ask", json={"question": "Question one"}).json()["conversation_id"]
    for question in ["Question two", "Question three"]:
        client.post("/api/ask", json={"question": question, "conversation_id": conversation_id})

    last_prompt = queued_llm.received_prompts[-1]

    assert "Question one" not in last_prompt
    assert "User: Question two" in last_prompt
    assert "Assistant: Cited answer 2" in last_prompt


def test_history_can_be_switched_off(client, queued_llm, monkeypatch):
    monkeypatch.setattr(settings, "chat_history_messages", 0)
    login_as(client, "employee", "employee123")
    conversation_id = client.post("/api/ask", json={"question": "First"}).json()["conversation_id"]

    client.post("/api/ask", json={"question": "Second", "conversation_id": conversation_id})

    assert "CONVERSATION SO FAR" not in queued_llm.received_prompts[1]


def test_answer_is_hidden_after_access_is_revoked_and_shown_again_when_restored(client, queued_llm):
    answer = ask_project_a_question(client, queued_llm)

    set_employee_project_a_access(False)
    conversation_response = client.get(f"/api/conversations/{answer['conversation_id']}")

    assert "PROJECT-A-ONLY-PHRASE" not in conversation_response.text
    assert PROJECT_A_DOCUMENT_NAME not in conversation_response.text
    hidden_message = conversation_response.json()["messages"][1]
    assert hidden_message["is_hidden"] is True
    assert hidden_message["content"] == HIDDEN_ANSWER_TEXT
    assert hidden_message["sources"] == []

    set_employee_project_a_access(True)
    restored_message = client.get(f"/api/conversations/{answer['conversation_id']}").json()["messages"][1]
    assert restored_message["content"] == SECRET_ANSWER_TEXT


def test_hidden_answer_is_not_sent_to_the_model_in_a_follow_up(client, queued_llm):
    answer = ask_project_a_question(client, queued_llm)
    set_employee_project_a_access(False)

    client.post("/api/ask", json={"question": "And the amber level?", "conversation_id": answer["conversation_id"]})

    follow_up_prompt = queued_llm.received_prompts[-1]
    assert "PROJECT-A-ONLY-PHRASE" not in follow_up_prompt
    assert HIDDEN_ANSWER_TEXT not in follow_up_prompt
    assert "User: What is the red trigger level?" in follow_up_prompt


def test_answer_is_hidden_after_its_source_document_is_deleted(client, queued_llm):
    answer = ask_project_a_question(client, queued_llm)
    with get_connection() as connection:
        connection.execute("UPDATE documents SET deleted_at = now() WHERE name = %s", (PROJECT_A_DOCUMENT_NAME,))

    hidden_message = client.get(f"/api/conversations/{answer['conversation_id']}").json()["messages"][1]

    assert hidden_message["is_hidden"] is True


def test_uncited_reply_is_saved_as_no_answer_and_never_shown(client, queued_llm):
    login_as(client, "employee", "employee123")
    queued_llm.queued_replies.append("Raw text that is not JSON and cites nothing (PROJECT-A-ONLY-PHRASE)")
    queued_llm.reply_with("Valid JSON that cites nothing (PROJECT-A-ONLY-PHRASE)", [])
    first_answer = client.post("/api/ask", json={"question": "Uncited"}).json()
    second_answer = client.post(
        "/api/ask", json={"question": "Uncited again", "conversation_id": first_answer["conversation_id"]}
    ).json()

    set_employee_project_a_access(False)
    conversation_response = client.get(f"/api/conversations/{first_answer['conversation_id']}")

    assert first_answer["answer"] == second_answer["answer"] == NO_ANSWER_TEXT
    assert "PROJECT-A-ONLY-PHRASE" not in conversation_response.text
    assert [message["content"] for message in conversation_response.json()["messages"][1::2]] == [NO_ANSWER_TEXT] * 2


@pytest.mark.parametrize(
    ("answer", "cited_document_ids", "context_document_ids", "allowed_document_ids", "expected_visible"),
    [
        ("Cited answer", [1], [1, 2, 3], {1}, True),
        ("Cited answer", [1, 2], [1, 2], {1}, False),
        (NO_ANSWER_TEXT, [], [1, 2], set(), True),
        ("Uncited answer", [], [1, 2], {1, 2, 3}, True),
        ("Uncited answer", [], [1, 2], {1}, False),
    ],
)
def test_is_answer_visible(answer, cited_document_ids, context_document_ids, allowed_document_ids, expected_visible):
    assert is_answer_visible(answer, cited_document_ids, context_document_ids, allowed_document_ids) is expected_visible

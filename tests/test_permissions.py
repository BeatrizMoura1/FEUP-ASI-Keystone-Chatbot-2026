import json

import pytest

from app import chat
from app.db import get_connection
from tests.conftest import login_as

BETA_QUESTION = "What is our walk-away price for the offshore wind substation tender?"
BETA_DOCUMENT_NAME = "Project B Offshore Wind Tender Bid Strategy CONFIDENTIAL"
BETA_ONLY_SNIPPETS = ["5.9 million", "Meridian Marine", "Rodrigo Faria", "Costa Norte", BETA_DOCUMENT_NAME]


@pytest.fixture
def echo_llm(monkeypatch) -> list[str]:
    """Replace the LLM with a fake that echoes the full prompt and cites every document it was given.

    If any Project B text reached the prompt, it would therefore appear in the API response.

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
        with get_connection() as connection:
            every_document_name = [row["name"] for row in connection.execute("SELECT name FROM documents")]
        cited_names = [name for name in every_document_name if f'name="{name}"' in user_prompt]
        return json.dumps({"answer": user_prompt, "sources": cited_names})

    monkeypatch.setattr(chat, "generate", fake_generate)
    return received_prompts


def test_employee_never_sees_project_b_content(client, echo_llm):
    login_as(client, "employee", "employee123")

    response = client.post("/api/ask", json={"question": BETA_QUESTION})

    assert response.status_code == 200
    response_text = response.text
    for beta_snippet in BETA_ONLY_SNIPPETS:
        assert beta_snippet not in response_text
        assert beta_snippet not in echo_llm[0]
    cited_names = [source["name"] for source in response.json()["sources"]]
    assert BETA_DOCUMENT_NAME not in cited_names
    assert "Project A Linha Verde Metro Extension Execution Plan" in echo_llm[0]


def test_admin_prompt_includes_project_b(client, echo_llm):
    login_as(client, "admin", "admin123")

    response = client.post("/api/ask", json={"question": BETA_QUESTION})

    assert "5.9 million" in echo_llm[0]
    assert BETA_DOCUMENT_NAME in [source["name"] for source in response.json()["sources"]]


def test_employee_cannot_open_project_b_document(client):
    login_as(client, "employee", "employee123")
    with get_connection() as connection:
        beta_document_id = connection.execute(
            "SELECT id FROM documents WHERE name = %s", (BETA_DOCUMENT_NAME,)
        ).fetchone()["id"]

    assert client.get(f"/api/documents/{beta_document_id}").status_code == 404


def test_employee_cannot_use_admin_api(client):
    login_as(client, "employee", "employee123")

    assert client.get("/api/admin/documents").status_code == 403


def test_ask_requires_login(client):
    assert client.post("/api/ask", json={"question": "hi"}).status_code == 401

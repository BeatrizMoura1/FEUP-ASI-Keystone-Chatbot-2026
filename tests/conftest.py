import json

import pytest
from fastapi.testclient import TestClient

from app import chat
from app.config import settings
from app.db import get_connection
from app.main import app
from db.reset import reset_database

TEST_ACCOUNT_PASSWORDS = {
    "employee_password": "employee123",
    "newhire_password": "newhire123",
    "admin_password": "admin123",
}
CITED_DOCUMENT_NAME = "Employee Handbook Leave and Hybrid Work"


@pytest.fixture
def client(monkeypatch) -> TestClient:
    """A test client backed by the local test database, reset to the seed data before each test.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Used to point the app at TEST_DATABASE_URL and set the test account passwords.

    Returns
    -------
    TestClient
        Client for the app, with the employee, newhire and admin accounts and the 7 sample documents.
    """
    monkeypatch.setattr(settings, "database_url", settings.test_database_url)
    for setting_name, password in TEST_ACCOUNT_PASSWORDS.items():
        monkeypatch.setattr(settings, setting_name, password)
    reset_database(settings.test_database_url)
    with TestClient(app) as test_client:
        yield test_client


def login_as(client: TestClient, username: str, password: str) -> None:
    """Log the client in, failing the test if the login is rejected.

    Parameters
    ----------
    client : TestClient
        The test client (keeps the session cookie).
    username : str
        Test account username.
    password : str
        Test account password.
    """
    response = client.post("/api/login", json={"username": username, "password": password})
    assert response.status_code == 200


class FakeLLM:
    """Stand-in for the LLM: replies with queued raw strings and records every prompt it receives."""

    def __init__(self) -> None:
        """Start with no queued replies and no recorded prompts."""
        self.queued_replies: list[str] = []
        self.received_prompts: list[str] = []

    def reply_with(self, answer: str, sources: list[str]) -> None:
        """Queue a well-formed JSON reply.

        Parameters
        ----------
        answer : str
            Answer text.
        sources : list of str
            Cited document names.
        """
        self.queued_replies.append(json.dumps({"answer": answer, "sources": sources}))

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Record the prompt and return the next queued reply (or a default one).

        Parameters
        ----------
        system_prompt : str
            Unused.
        user_prompt : str
            The prompt sent to the model.

        Returns
        -------
        str
            Raw reply text.
        """
        self.received_prompts.append(user_prompt)
        if self.queued_replies:
            return self.queued_replies.pop(0)
        return json.dumps({"answer": f"Default answer {len(self.received_prompts)}", "sources": []})


def names_of_documents_in_prompt(user_prompt: str) -> list[str]:
    """List the documents whose text was put in the prompt, as a model that cites everything would.

    Parameters
    ----------
    user_prompt : str
        The prompt sent to the model.

    Returns
    -------
    list of str
        Names of the documents in the prompt.
    """
    with get_connection() as connection:
        every_document_name = [row["name"] for row in connection.execute("SELECT name FROM documents")]
    return [name for name in every_document_name if f'name="{name}"' in user_prompt]


@pytest.fixture
def numbered_llm(monkeypatch) -> list[str]:
    """Replace the LLM with a fake that numbers its answers and always cites CITED_DOCUMENT_NAME.

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
        return json.dumps({"answer": f"Answer number {len(received_prompts)}", "sources": [CITED_DOCUMENT_NAME]})

    monkeypatch.setattr(chat, "generate", fake_generate)
    return received_prompts


@pytest.fixture
def echo_llm(monkeypatch) -> list[str]:
    """Replace the LLM with a fake that echoes the full prompt and cites every document it was given.

    If any restricted text reached the prompt, it would therefore appear in the API response.

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
        return json.dumps({"answer": user_prompt, "sources": names_of_documents_in_prompt(user_prompt)})

    monkeypatch.setattr(chat, "generate", fake_generate)
    return received_prompts


@pytest.fixture
def citing_llm(monkeypatch) -> list[str]:
    """Replace the LLM with a fake that gives a fixed answer citing every document it was given.

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
        cited_names = names_of_documents_in_prompt(user_prompt)
        return json.dumps({"answer": "Answer from the documents.", "sources": cited_names})

    monkeypatch.setattr(chat, "generate", fake_generate)
    return received_prompts


@pytest.fixture
def queued_llm(monkeypatch) -> FakeLLM:
    """Replace the LLM with a FakeLLM whose replies each test queues.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Used to replace `chat.generate`.

    Returns
    -------
    FakeLLM
        The fake, to queue replies and inspect prompts.
    """
    llm_stand_in = FakeLLM()
    monkeypatch.setattr(chat, "generate", llm_stand_in.generate)
    return llm_stand_in

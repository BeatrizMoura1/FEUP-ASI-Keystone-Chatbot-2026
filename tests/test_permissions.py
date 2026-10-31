from app.db import get_connection
from tests.conftest import login_as

BETA_QUESTION = "What is our walk-away price for the offshore wind substation tender?"
BETA_DOCUMENT_NAME = "Project B Offshore Wind Tender Bid Strategy CONFIDENTIAL"
BETA_ONLY_SNIPPETS = ["5.9 million", "Meridian Marine", "Rodrigo Faria", "Costa Norte", BETA_DOCUMENT_NAME]


def test_employee_never_sees_project_b_content(client, echo_llm):
    """No Project B text or citation reaches an employee's prompt or response (M3 leak test)."""
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
    """Admins get Project B documents in their prompt and citations."""
    login_as(client, "admin", "admin123")

    response = client.post("/api/ask", json={"question": BETA_QUESTION})

    assert "5.9 million" in echo_llm[0]
    assert BETA_DOCUMENT_NAME in [source["name"] for source in response.json()["sources"]]


def test_employee_cannot_open_project_b_document(client):
    """An employee cannot open a Project B document by its id (M3)."""
    login_as(client, "employee", "employee123")
    with get_connection() as connection:
        beta_document_id = connection.execute(
            "SELECT id FROM documents WHERE name = %s", (BETA_DOCUMENT_NAME,)
        ).fetchone()["id"]

    assert client.get(f"/api/documents/{beta_document_id}").status_code == 404


def test_employee_cannot_use_admin_api(client):
    """Employees get 403 on the admin API (M4)."""
    login_as(client, "employee", "employee123")

    assert client.get("/api/admin/documents").status_code == 403


def test_ask_requires_login(client):
    """Asking a question needs a login."""
    assert client.post("/api/ask", json={"question": "hi"}).status_code == 401


PROJECT_A_DOCUMENT_NAMES = [
    "Project A Linha Verde Metro Extension Execution Plan",
    "Project A Design Review Minutes 2026-09-24",
]
PROJECT_A_ONLY_SNIPPETS = ["Alameda Norte", "Quinta das Flores", *PROJECT_A_DOCUMENT_NAMES]


def test_newhire_never_sees_project_a_or_b_content(client, echo_llm):
    """No Project A or B text or citation reaches newhire's prompt or response (M3 leak test)."""
    login_as(client, "newhire", "newhire123")

    response = client.post("/api/ask", json={"question": "What settlement triggers a red alert on Linha Verde?"})

    assert response.status_code == 200
    for restricted_snippet in [*PROJECT_A_ONLY_SNIPPETS, *BETA_ONLY_SNIPPETS]:
        assert restricted_snippet not in echo_llm[0]
        assert restricted_snippet not in response.text
    assert "Employee Handbook Leave and Hybrid Work" in echo_llm[0]


def test_newhire_cannot_open_project_a_document(client):
    """newhire cannot open a Project A document by its id (M3)."""
    login_as(client, "newhire", "newhire123")
    with get_connection() as connection:
        project_a_document_id = connection.execute(
            "SELECT id FROM documents WHERE name = %s", (PROJECT_A_DOCUMENT_NAMES[0],)
        ).fetchone()["id"]

    assert client.get(f"/api/documents/{project_a_document_id}").status_code == 404

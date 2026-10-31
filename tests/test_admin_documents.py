from tests.conftest import login_as

UPLOADED_FILE_NAME = "Company_Car_Policy.txt"
UPLOADED_DOCUMENT_NAME = "Company Car Policy"
UPLOADED_TEXT = b"Contoso does not offer company cars. Employees receive a mobility allowance of 150 EUR per month."


def upload(client, file_name: str, file_bytes: bytes, project: str):
    """Upload a document through the admin API.

    Parameters
    ----------
    client : TestClient
        Client logged in as admin.
    file_name : str
        Name of the uploaded file.
    file_bytes : bytes
        File content.
    project : str
        Project code to assign.

    Returns
    -------
    httpx.Response
        The API response.
    """
    return client.post("/api/admin/documents", files={"file": (file_name, file_bytes)}, data={"project": project})


def test_uploaded_document_is_searchable_right_away(client, citing_llm):
    """A document uploaded to General reaches the next employee prompt and is cited (M5)."""
    login_as(client, "admin", "admin123")
    upload_response = upload(client, UPLOADED_FILE_NAME, UPLOADED_TEXT, "GENERAL")
    login_as(client, "employee", "employee123")

    answer = client.post("/api/ask", json={"question": "Is there a company car?"}).json()

    assert upload_response.status_code == 200
    assert upload_response.json()["name"] == UPLOADED_DOCUMENT_NAME
    assert "150 EUR per month" in citing_llm[0]
    assert UPLOADED_DOCUMENT_NAME in [source["name"] for source in answer["sources"]]


def test_document_uploaded_to_project_b_stays_hidden_from_employee(client, citing_llm):
    """A document uploaded to Project B never reaches an employee's prompt (M3)."""
    login_as(client, "admin", "admin123")
    upload(client, UPLOADED_FILE_NAME, UPLOADED_TEXT, "B")
    login_as(client, "employee", "employee123")

    client.post("/api/ask", json={"question": "Is there a company car?"})

    assert "150 EUR per month" not in citing_llm[0]


def test_deleted_document_never_reaches_the_prompt(client, citing_llm):
    """After deletion a document is in neither the admin's nor the employee's prompt, list or drawer (M5)."""
    login_as(client, "admin", "admin123")
    document_id = upload(client, UPLOADED_FILE_NAME, UPLOADED_TEXT, "GENERAL").json()["id"]

    delete_response = client.delete(f"/api/admin/documents/{document_id}")
    client.post("/api/ask", json={"question": "Is there a company car?"})
    listed_names = [document["name"] for document in client.get("/api/admin/documents").json()["documents"]]
    admin_open_status = client.get(f"/api/documents/{document_id}").status_code
    login_as(client, "employee", "employee123")
    client.post("/api/ask", json={"question": "Is there a company car?"})

    assert delete_response.status_code == 200
    assert "150 EUR per month" not in citing_llm[0]
    assert "150 EUR per month" not in citing_llm[1]
    assert UPLOADED_DOCUMENT_NAME not in listed_names
    assert admin_open_status == 404
    assert client.get(f"/api/documents/{document_id}").status_code == 404


def test_deleting_twice_returns_404(client):
    """Deleting an already deleted document returns 404."""
    login_as(client, "admin", "admin123")
    document_id = upload(client, UPLOADED_FILE_NAME, UPLOADED_TEXT, "GENERAL").json()["id"]
    client.delete(f"/api/admin/documents/{document_id}")

    assert client.delete(f"/api/admin/documents/{document_id}").status_code == 404


def test_deleted_document_name_can_be_uploaded_again(client, citing_llm):
    """A deleted document's name can be reused, and only the new text reaches the prompt."""
    login_as(client, "admin", "admin123")
    first_id = upload(client, UPLOADED_FILE_NAME, UPLOADED_TEXT, "GENERAL").json()["id"]
    client.delete(f"/api/admin/documents/{first_id}")

    second_response = upload(client, UPLOADED_FILE_NAME, b"The mobility allowance is now 200 EUR per month.", "GENERAL")
    client.post("/api/ask", json={"question": "What is the mobility allowance?"})

    assert second_response.status_code == 200
    assert second_response.json()["id"] != first_id
    assert "200 EUR per month" in citing_llm[0]
    assert "150 EUR per month" not in citing_llm[0]


def test_unsupported_file_type_is_rejected(client):
    """An upload that is not .txt, .md or .pdf is rejected with a readable message."""
    login_as(client, "admin", "admin123")

    response = upload(client, "photo.png", b"not a document", "GENERAL")

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_empty_file_is_rejected(client):
    """An upload with no extractable text is rejected with a readable message."""
    login_as(client, "admin", "admin123")

    response = upload(client, "Empty.txt", b"", "GENERAL")

    assert response.status_code == 400
    assert "No text could be extracted" in response.json()["detail"]


def test_unknown_project_is_rejected(client):
    """An upload to a project that does not exist is rejected."""
    login_as(client, "admin", "admin123")

    response = upload(client, UPLOADED_FILE_NAME, UPLOADED_TEXT, "Z")

    assert response.status_code == 400
    assert "Unknown project" in response.json()["detail"]


def test_admin_list_shows_projects_with_general_first(client):
    """The admin list has the 7 sample documents and offers General as the first project."""
    login_as(client, "admin", "admin123")

    listing = client.get("/api/admin/documents").json()

    assert listing["projects"] == ["GENERAL", "A", "B"]
    assert len(listing["documents"]) == 7


def test_employee_cannot_upload_or_delete(client):
    """Employees get 403 on document upload and delete (M4)."""
    login_as(client, "employee", "employee123")

    assert upload(client, UPLOADED_FILE_NAME, UPLOADED_TEXT, "GENERAL").status_code == 403
    assert client.delete("/api/admin/documents/1").status_code == 403

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from db.reset import reset_database

TEST_ACCOUNT_PASSWORDS = {
    "employee_password": "employee123",
    "newhire_password": "newhire123",
    "admin_password": "admin123",
}


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

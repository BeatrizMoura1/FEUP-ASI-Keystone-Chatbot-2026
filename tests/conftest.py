import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    """A test client backed by a fresh temporary database seeded from the real docs folder.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest temporary directory.
    monkeypatch : pytest.MonkeyPatch
        Used to point the app at the temporary database.

    Returns
    -------
    TestClient
        Client with the app's startup (DB init + seeding) already run.
    """
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "test.db"))
    with TestClient(app) as test_client:
        yield test_client


def login_as(client: TestClient, username: str, password: str) -> None:
    """Log the client in, failing the test if the login is rejected.

    Parameters
    ----------
    client : TestClient
        The test client (keeps the session cookie).
    username : str
        Demo username.
    password : str
        Demo password.
    """
    response = client.post("/api/login", json={"username": username, "password": password})
    assert response.status_code == 200

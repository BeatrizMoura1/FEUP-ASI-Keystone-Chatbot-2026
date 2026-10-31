from app.auth import SESSION_COOKIE_NAME
from app.db import get_connection
from tests.conftest import login_as


def test_wrong_password_is_rejected(client):
    """A wrong password gets 401, the plain message, and no session cookie (M4)."""
    response = client.post("/api/login", json={"username": "employee", "password": "wrong-password"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Wrong username or password"
    assert SESSION_COOKIE_NAME not in client.cookies


def test_unknown_user_is_rejected(client):
    """An unknown username gets 401."""
    response = client.post("/api/login", json={"username": "nobody", "password": "employee123"})

    assert response.status_code == 401


def test_login_returns_the_user_role(client):
    """After login, /api/me returns the username and role."""
    login_as(client, "newhire", "newhire123")

    assert client.get("/api/me").json() == {"username": "newhire", "role": "employee"}


def test_logout_ends_the_session(client):
    """After logout the old session token no longer works, even if sent again."""
    login_as(client, "employee", "employee123")
    session_token = client.cookies[SESSION_COOKIE_NAME]

    client.post("/api/logout")
    client.cookies.set(SESSION_COOKIE_NAME, session_token)

    assert client.get("/api/me").status_code == 401


def test_expired_session_is_rejected(client):
    """A session past its expiry time is refused."""
    login_as(client, "employee", "employee123")
    with get_connection() as connection:
        connection.execute("UPDATE sessions SET expires_at = now() - interval '1 minute'")

    assert client.get("/api/me").status_code == 401


def test_employee_is_sent_from_admin_page_to_chat(client):
    """An employee opening /admin is redirected to the chat (M4)."""
    login_as(client, "employee", "employee123")

    response = client.get("/admin", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/"


def test_admin_page_requires_login(client):
    """Opening /admin without a login redirects to the login page."""
    response = client.get("/admin", follow_redirects=False)

    assert response.headers["location"] == "/login"


def test_admin_can_open_admin_page(client):
    """An admin can open /admin."""
    login_as(client, "admin", "admin123")

    assert client.get("/admin", follow_redirects=False).status_code == 200

import secrets
import sqlite3

from fastapi import Depends, HTTPException, Request

from app.db import get_connection, verify_password

SESSION_COOKIE_NAME = "kf_session"


def login(username: str, password: str) -> str | None:
    """Check credentials and create a session.

    Parameters
    ----------
    username : str
        Login name.
    password : str
        Plain-text password.

    Returns
    -------
    str or None
        New session token, or None if the credentials are wrong.
    """
    with get_connection() as connection:
        user = connection.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user is None or not verify_password(password, user["password_hash"]):
            return None
        session_token = secrets.token_urlsafe(32)
        connection.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (session_token, user["id"]))
        return session_token


def logout(session_token: str | None) -> None:
    """Delete a session.

    Parameters
    ----------
    session_token : str or None
        Token from the session cookie.
    """
    if session_token:
        with get_connection() as connection:
            connection.execute("DELETE FROM sessions WHERE token = ?", (session_token,))


def get_user_from_session(session_token: str | None) -> sqlite3.Row | None:
    """Look up the user that owns a session token.

    Parameters
    ----------
    session_token : str or None
        Token from the session cookie.

    Returns
    -------
    sqlite3.Row or None
        The user, or None if the token is missing or unknown.
    """
    if not session_token:
        return None
    with get_connection() as connection:
        return connection.execute(
            "SELECT u.* FROM users u JOIN sessions s ON s.user_id = u.id WHERE s.token = ?", (session_token,)
        ).fetchone()


def get_current_user(request: Request) -> sqlite3.Row:
    """FastAPI dependency: the logged-in user from the session cookie.

    Parameters
    ----------
    request : Request
        Incoming request.

    Returns
    -------
    sqlite3.Row
        The logged-in user.

    Raises
    ------
    HTTPException
        401 if not logged in.
    """
    user = get_user_from_session(request.cookies.get(SESSION_COOKIE_NAME))
    if user is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    return user


def require_admin(user: sqlite3.Row = Depends(get_current_user)) -> sqlite3.Row:
    """FastAPI dependency: the logged-in user, who must be an admin.

    Parameters
    ----------
    user : sqlite3.Row
        The logged-in user.

    Returns
    -------
    sqlite3.Row
        The admin user.

    Raises
    ------
    HTTPException
        403 if the user is not an admin.
    """
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    return user

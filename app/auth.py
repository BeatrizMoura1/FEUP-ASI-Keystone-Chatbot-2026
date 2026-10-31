import hashlib
import hmac
import secrets
from datetime import timedelta

from fastapi import Depends, HTTPException, Request

from app.db import get_connection

SESSION_COOKIE_NAME = "kf_session"
SESSION_LIFETIME = timedelta(days=7)


def hash_password(password: str, salt_hex: str | None = None) -> str:
    """Hash a password with PBKDF2-SHA256 and a random salt.

    Parameters
    ----------
    password : str
        Plain-text password.
    salt_hex : str, optional
        Existing salt (hex) to reuse when verifying; a new one is generated if omitted.

    Returns
    -------
    str
        "salt_hex$hash_hex".
    """
    salt_hex = salt_hex or secrets.token_hex(16)
    password_digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 200_000)
    return f"{salt_hex}${password_digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Check a plain-text password against a stored PBKDF2 hash.

    Parameters
    ----------
    password : str
        Plain-text password to check.
    stored_hash : str
        Value produced by `hash_password`.

    Returns
    -------
    bool
        True if the password matches.
    """
    salt_hex, _ = stored_hash.split("$", 1)
    return hmac.compare_digest(hash_password(password, salt_hex), stored_hash)


def login(username: str, password: str) -> str | None:
    """Check credentials and create a session that expires after SESSION_LIFETIME.

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
        user = connection.execute("SELECT * FROM users WHERE username = %s", (username,)).fetchone()
        if user is None or not verify_password(password, user["password_hash"]):
            return None
        session_token = secrets.token_urlsafe(32)
        connection.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (%s, %s, now() + %s)",
            (session_token, user["id"], SESSION_LIFETIME),
        )
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
            connection.execute("DELETE FROM sessions WHERE token = %s", (session_token,))


def get_user_from_session(session_token: str | None) -> dict | None:
    """Look up the user that owns a session token that has not expired.

    Parameters
    ----------
    session_token : str or None
        Token from the session cookie.

    Returns
    -------
    dict or None
        The user (id, username, role), or None if the token is missing, unknown or expired.
    """
    if not session_token:
        return None
    with get_connection() as connection:
        return connection.execute(
            "SELECT u.id, u.username, u.role FROM users u JOIN sessions s ON s.user_id = u.id "
            "WHERE s.token = %s AND s.expires_at > now()",
            (session_token,),
        ).fetchone()


def get_current_user(request: Request) -> dict:
    """FastAPI dependency: the logged-in user from the session cookie.

    Parameters
    ----------
    request : Request
        Incoming request.

    Returns
    -------
    dict
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


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """FastAPI dependency: the logged-in user, who must be an admin.

    Parameters
    ----------
    user : dict
        The logged-in user.

    Returns
    -------
    dict
        The admin user.

    Raises
    ------
    HTTPException
        403 if the user is not an admin.
    """
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    return user

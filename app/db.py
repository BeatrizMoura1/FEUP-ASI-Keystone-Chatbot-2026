import hashlib
import hmac
import secrets

import psycopg
from psycopg.rows import dict_row

from app.config import settings


def get_connection() -> psycopg.Connection:
    """Open a PostgreSQL connection that returns rows as dicts.

    Use it as `with get_connection() as connection:`; the transaction is committed and the connection closed
    when the block ends (rolled back if it raises).

    Returns
    -------
    psycopg.Connection
        Connection to DATABASE_URL.
    """
    return psycopg.connect(settings.database_url, row_factory=dict_row)


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

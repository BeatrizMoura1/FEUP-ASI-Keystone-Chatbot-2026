import hashlib
import hmac
import secrets
import sqlite3

from app.config import PROJECTS, settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('employee', 'admin'))
);
CREATE TABLE IF NOT EXISTS user_projects (
    user_id INTEGER NOT NULL REFERENCES users(id),
    project TEXT NOT NULL,
    PRIMARY KEY (user_id, project)
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    project TEXT NOT NULL,
    content TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    sources_json TEXT NOT NULL DEFAULT '[]',
    context_document_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ratings (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    is_positive INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL
);
"""

RATINGS_MESSAGE_INDEX = (
    "CREATE UNIQUE INDEX IF NOT EXISTS ratings_one_per_message ON ratings (message_id) WHERE message_id IS NOT NULL"
)

# Demo users: (username, password, role, allowed projects). Admins see every project regardless.
DEMO_USERS = [
    ("employee", "employee123", "employee", ["GENERAL", "A"]),
    ("admin", "admin123", "admin", PROJECTS),
]


def get_connection() -> sqlite3.Connection:
    """Open a SQLite connection that returns rows as dict-like objects.

    Returns
    -------
    sqlite3.Connection
        Connection to the configured database file.
    """
    connection = sqlite3.connect(settings.database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


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


def init_db() -> None:
    """Create the tables (adding columns missing from older databases) and insert the demo users."""
    with get_connection() as connection:
        connection.executescript(SCHEMA)
        rating_columns = [column["name"] for column in connection.execute("PRAGMA table_info(ratings)")]
        if "message_id" not in rating_columns:
            connection.execute(
                "ALTER TABLE ratings ADD COLUMN message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL"
            )
        connection.execute(RATINGS_MESSAGE_INDEX)
        message_columns = [column["name"] for column in connection.execute("PRAGMA table_info(messages)")]
        if "context_document_ids_json" not in message_columns:
            connection.execute("ALTER TABLE messages ADD COLUMN context_document_ids_json TEXT NOT NULL DEFAULT '[]'")
        for username, password, role, allowed_projects in DEMO_USERS:
            existing_user = connection.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if existing_user:
                continue
            cursor = connection.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, hash_password(password), role),
            )
            connection.executemany(
                "INSERT INTO user_projects (user_id, project) VALUES (?, ?)",
                [(cursor.lastrowid, project) for project in allowed_projects],
            )

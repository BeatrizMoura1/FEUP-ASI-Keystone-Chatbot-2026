import psycopg
import pytest

from app.config import settings
from db.reset import reset_database


@pytest.fixture
def test_database(monkeypatch) -> psycopg.Connection:
    """Reset the local test database with known passwords and return an autocommit connection to it.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Used to set the test account passwords.

    Returns
    -------
    psycopg.Connection
        Connection to TEST_DATABASE_URL, closed after the test.
    """
    for setting_name in ("employee_password", "newhire_password", "admin_password"):
        monkeypatch.setattr(settings, setting_name, "test-password")
    reset_database(settings.test_database_url)
    with psycopg.connect(settings.test_database_url, autocommit=True) as connection:
        yield connection


def insert_message_with_rating(connection: psycopg.Connection) -> tuple[int, int]:
    """Create a chat for `employee` with one answer that cites a document and has a rating.

    Parameters
    ----------
    connection : psycopg.Connection
        Connection to the test database.

    Returns
    -------
    tuple of (int, int)
        The conversation id and the rating id.
    """
    employee_id = connection.execute("SELECT id FROM users WHERE username = 'employee'").fetchone()[0]
    document_id = connection.execute("SELECT min(id) FROM documents").fetchone()[0]
    conversation_id = connection.execute(
        "INSERT INTO conversations (user_id, title) VALUES (%s, 'Leave') RETURNING id", (employee_id,)
    ).fetchone()[0]
    message_id = connection.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (%s, 'assistant', '5 days.') RETURNING id",
        (conversation_id,),
    ).fetchone()[0]
    connection.execute("INSERT INTO message_sources VALUES (%s, %s)", (message_id, document_id))
    connection.execute("INSERT INTO message_context_documents VALUES (%s, %s)", (message_id, document_id))
    rating_id = connection.execute(
        "INSERT INTO ratings (message_id, user_id, is_positive, question, answer) "
        "VALUES (%s, %s, true, 'Carry-over?', '5 days.') RETURNING id",
        (message_id, employee_id),
    ).fetchone()[0]
    return conversation_id, rating_id


def test_reset_seeds_projects_accounts_and_documents(test_database):
    """The reset creates the three projects, the three test accounts with their projects, and 7 documents."""
    account_projects = dict(
        test_database.execute(
            "SELECT u.username, coalesce(string_agg(p.code, ',' ORDER BY p.code), '') FROM users u "
            "LEFT JOIN user_projects up ON up.user_id = u.id LEFT JOIN projects p ON p.id = up.project_id "
            "GROUP BY u.username"
        ).fetchall()
    )
    assert account_projects == {"employee": "A,GENERAL", "newhire": "GENERAL", "admin": ""}
    assert test_database.execute("SELECT count(*) FROM projects").fetchone()[0] == 3
    assert test_database.execute("SELECT count(*) FROM documents").fetchone()[0] == 7


def test_reset_wipes_existing_data(test_database):
    """Running the reset again deletes chats and ratings and restores the same seed data."""
    insert_message_with_rating(test_database)
    reset_database(settings.test_database_url)
    assert test_database.execute("SELECT count(*) FROM conversations").fetchone()[0] == 0
    assert test_database.execute("SELECT count(*) FROM ratings").fetchone()[0] == 0
    assert test_database.execute("SELECT count(*) FROM documents").fetchone()[0] == 7


def test_reset_refuses_without_passwords(monkeypatch):
    """The reset stops before touching the database when a test account password is missing."""
    monkeypatch.setattr(settings, "admin_password", "")
    with pytest.raises(ValueError, match="ADMIN_PASSWORD"):
        reset_database(settings.test_database_url)


def test_active_document_names_are_unique(test_database):
    """Two non-deleted documents cannot share a name."""
    with pytest.raises(psycopg.errors.UniqueViolation):
        test_database.execute(
            "INSERT INTO documents (name, content, project_id) "
            "SELECT name, 'copy', project_id FROM documents ORDER BY id LIMIT 1"
        )


def test_deleted_document_name_can_be_uploaded_again(test_database):
    """After a soft delete, a new document with the same name is accepted."""
    document_id = test_database.execute("SELECT min(id) FROM documents").fetchone()[0]
    test_database.execute("UPDATE documents SET deleted_at = now() WHERE id = %s", (document_id,))
    test_database.execute(
        "INSERT INTO documents (name, content, project_id) "
        "SELECT name, 'new version', project_id FROM documents WHERE id = %s",
        (document_id,),
    )
    assert test_database.execute("SELECT count(*) FROM documents").fetchone()[0] == 8


def test_deleting_a_chat_keeps_its_rating(test_database):
    """Deleting a chat removes its messages and citations; the rating stays, unlinked from the message."""
    conversation_id, rating_id = insert_message_with_rating(test_database)
    test_database.execute("DELETE FROM conversations WHERE id = %s", (conversation_id,))
    assert test_database.execute("SELECT count(*) FROM messages").fetchone()[0] == 0
    assert test_database.execute("SELECT count(*) FROM message_sources").fetchone()[0] == 0
    assert test_database.execute("SELECT count(*) FROM message_context_documents").fetchone()[0] == 0
    assert test_database.execute("SELECT message_id FROM ratings WHERE id = %s", (rating_id,)).fetchone() == (None,)


def test_unknown_role_is_rejected(test_database):
    """A user role other than employee or admin is refused by the database."""
    with pytest.raises(psycopg.errors.CheckViolation):
        test_database.execute("INSERT INTO users (username, password_hash, role) VALUES ('x', 'hash', 'manager')")

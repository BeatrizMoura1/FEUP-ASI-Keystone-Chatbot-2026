import logging
from pathlib import Path

import psycopg

from app.config import PROJECTS, settings
from app.auth import hash_password
from app.documents import SUPPORTED_EXTENSIONS, detect_project, document_name_from_filename, extract_text

logger = logging.getLogger("knowledge_finder")

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

TABLES = [
    "ratings",
    "message_context_documents",
    "message_sources",
    "messages",
    "conversations",
    "sessions",
    "documents",
    "user_projects",
    "users",
    "projects",
]

# Test accounts: (username, role, projects, password setting). Admins see every project without user_projects rows.
TEST_ACCOUNTS = [
    ("employee", "employee", ["GENERAL", "A"], "employee_password"),
    ("newhire", "employee", ["GENERAL"], "newhire_password"),
    ("admin", "admin", [], "admin_password"),
]


def read_test_account_passwords() -> dict[str, str]:
    """Read the test account passwords from the settings.

    Returns
    -------
    dict of str to str
        Password per username.

    Raises
    ------
    ValueError
        If any of EMPLOYEE_PASSWORD, NEWHIRE_PASSWORD or ADMIN_PASSWORD is empty.
    """
    passwords = {username: getattr(settings, setting_name) for username, _, _, setting_name in TEST_ACCOUNTS}
    missing_variables = [
        setting_name.upper() for username, _, _, setting_name in TEST_ACCOUNTS if not passwords[username]
    ]
    if missing_variables:
        raise ValueError(f"Set these environment variables before the reset: {', '.join(missing_variables)}")
    return passwords


def load_sample_documents(docs_dir: str) -> list[tuple[str, str, str]]:
    """Read every supported file in the sample documents folder.

    Parameters
    ----------
    docs_dir : str
        Folder with the sample documents.

    Returns
    -------
    list of tuple of (str, str, str)
        (document name, project code, text) per file, sorted by file name.

    Raises
    ------
    FileNotFoundError
        If the folder does not exist.
    """
    docs_folder = Path(docs_dir)
    if not docs_folder.is_dir():
        raise FileNotFoundError(f"Sample documents folder '{docs_folder}' not found.")
    sample_documents = []
    for document_path in sorted(docs_folder.iterdir()):
        if document_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        document_text = extract_text(document_path.name, document_path.read_bytes())
        sample_documents.append(
            (document_name_from_filename(document_path.name), detect_project(document_text), document_text)
        )
    return sample_documents


def reset_database(database_url: str) -> dict[str, int]:
    """Drop every Keystone table, recreate the schema and insert the projects, test accounts and sample documents.

    All existing data (chats, ratings, uploaded documents, sessions) is deleted. Everything runs in one
    transaction, so a failure leaves the database as it was.

    Parameters
    ----------
    database_url : str
        PostgreSQL connection string.

    Returns
    -------
    dict of str to int
        Number of projects, users and documents inserted.

    Raises
    ------
    ValueError
        If a test account password is not set.
    FileNotFoundError
        If the sample documents folder does not exist.
    psycopg.Error
        If a database statement fails.
    """
    passwords = read_test_account_passwords()
    sample_documents = load_sample_documents(settings.docs_dir)
    with psycopg.connect(database_url) as connection:
        connection.execute(f"DROP TABLE IF EXISTS {', '.join(TABLES)} CASCADE")
        connection.execute(SCHEMA_PATH.read_text())
        project_ids = {}
        for project_code, project_name in PROJECTS.items():
            project_ids[project_code] = connection.execute(
                "INSERT INTO projects (code, name) VALUES (%s, %s) RETURNING id", (project_code, project_name)
            ).fetchone()[0]
        user_ids = {}
        for username, role, project_codes, _ in TEST_ACCOUNTS:
            user_ids[username] = connection.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s) RETURNING id",
                (username, hash_password(passwords[username]), role),
            ).fetchone()[0]
            for project_code in project_codes:
                connection.execute(
                    "INSERT INTO user_projects (user_id, project_id) VALUES (%s, %s)",
                    (user_ids[username], project_ids[project_code]),
                )
        for document_name, project_code, document_text in sample_documents:
            connection.execute(
                "INSERT INTO documents (name, content, project_id, uploaded_by) VALUES (%s, %s, %s, %s)",
                (document_name, document_text, project_ids[project_code], user_ids["admin"]),
            )
    inserted_counts = {"projects": len(PROJECTS), "users": len(TEST_ACCOUNTS), "documents": len(sample_documents)}
    logger.info("Database reset: %s.", inserted_counts)
    return inserted_counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    reset_database(settings.database_url)

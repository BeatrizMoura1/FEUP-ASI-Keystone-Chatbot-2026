import io
import logging
import re
import sqlite3
from pathlib import Path

from pypdf import PdfReader

from app.config import PROJECTS, settings
from app.db import get_connection

logger = logging.getLogger("knowledge_finder")

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}
PROJECT_TAG_PATTERN = re.compile(r"visibility tag:\s*(?:PROJECT\s+)?(GENERAL|[A-Z])\b", re.IGNORECASE)


def extract_text(file_name: str, file_bytes: bytes) -> str:
    """Extract plain text from a txt, md or pdf file.

    Parameters
    ----------
    file_name : str
        Original file name, used to pick the parser from its extension.
    file_bytes : bytes
        Raw file content.

    Returns
    -------
    str
        Extracted text.

    Raises
    ------
    ValueError
        If the extension is not supported or no text could be extracted.
    """
    extension = Path(file_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{extension}'. Use .txt, .md or .pdf.")
    if extension == ".pdf":
        pdf_reader = PdfReader(io.BytesIO(file_bytes))
        document_text = "\n".join(page.extract_text() or "" for page in pdf_reader.pages)
    else:
        document_text = file_bytes.decode("utf-8", errors="replace")
    if not document_text.strip():
        raise ValueError(f"No text could be extracted from '{file_name}'.")
    return document_text.strip()


def document_name_from_filename(file_name: str) -> str:
    """Turn a file name into a readable document name, e.g. "Site_Safety_Rules.txt" -> "Site Safety Rules".

    Parameters
    ----------
    file_name : str
        Original file name.

    Returns
    -------
    str
        File name without extension, with underscores replaced by spaces.
    """
    return " ".join(Path(file_name).stem.replace("_", " ").split())


def detect_project(document_text: str) -> str:
    """Read the project from a "Project / visibility tag:" line, defaulting to GENERAL.

    Parameters
    ----------
    document_text : str
        Full document text.

    Returns
    -------
    str
        One of PROJECTS.
    """
    tag_match = PROJECT_TAG_PATTERN.search(document_text)
    detected_project = tag_match.group(1).upper() if tag_match else "GENERAL"
    return detected_project if detected_project in PROJECTS else "GENERAL"


def add_document(name: str, project: str, content: str) -> int:
    """Insert a document, or replace the one with the same name.

    Parameters
    ----------
    name : str
        Document name shown to users and used in citations.
    project : str
        Project the document belongs to.
    content : str
        Full document text.

    Returns
    -------
    int
        The document id.

    Raises
    ------
    ValueError
        If the project is unknown.
    """
    if project not in PROJECTS:
        raise ValueError(f"Unknown project '{project}'. Choose one of {PROJECTS}.")
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO documents (name, project, content) VALUES (?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET project = excluded.project, content = excluded.content "
            "RETURNING id",
            (name, project, content),
        )
        return cursor.fetchone()["id"]


def seed_documents() -> int:
    """Load every supported file in DOCS_DIR into the database (only when it holds no documents yet).

    Returns
    -------
    int
        Number of documents loaded.
    """
    with get_connection() as connection:
        if connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] > 0:
            return 0
    docs_folder = Path(settings.docs_dir)
    if not docs_folder.is_dir():
        logger.warning("Docs folder '%s' not found, no documents seeded.", docs_folder)
        return 0
    num_loaded = 0
    for document_path in sorted(docs_folder.iterdir()):
        if document_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        try:
            document_text = extract_text(document_path.name, document_path.read_bytes())
        except Exception as error:
            logger.error("Failed to load '%s': %s", document_path, error)
            raise
        add_document(document_name_from_filename(document_path.name), detect_project(document_text), document_text)
        num_loaded += 1
    logger.info("Seeded %d documents from '%s'.", num_loaded, docs_folder)
    return num_loaded


def get_allowed_documents(user: sqlite3.Row) -> list[sqlite3.Row]:
    """Fetch only the documents the user may see; the permission filter is part of the SQL query.

    Parameters
    ----------
    user : sqlite3.Row
        Row from the users table (needs `id` and `role`).

    Returns
    -------
    list of sqlite3.Row
        Documents with id, name, project and content.
    """
    with get_connection() as connection:
        if user["role"] == "admin":
            return connection.execute("SELECT id, name, project, content FROM documents ORDER BY name").fetchall()
        return connection.execute(
            "SELECT d.id, d.name, d.project, d.content FROM documents d "
            "JOIN user_projects up ON up.project = d.project "
            "WHERE up.user_id = ? ORDER BY d.name",
            (user["id"],),
        ).fetchall()


def get_allowed_document_ids(user: sqlite3.Row) -> set[int]:
    """Fetch the ids of the documents the user may see (same SQL permission filter, without the text).

    Parameters
    ----------
    user : sqlite3.Row
        Row from the users table (needs `id` and `role`).

    Returns
    -------
    set of int
        Ids of the visible documents.
    """
    with get_connection() as connection:
        if user["role"] == "admin":
            id_rows = connection.execute("SELECT id FROM documents").fetchall()
        else:
            id_rows = connection.execute(
                "SELECT d.id FROM documents d JOIN user_projects up ON up.project = d.project WHERE up.user_id = ?",
                (user["id"],),
            ).fetchall()
    return {id_row["id"] for id_row in id_rows}

def delete_document(document_id: int) -> bool:
    """Delete a document by id.

    Parameters
    ----------
    document_id : int
        Id of the document to delete.

    Returns
    -------
    bool
        True if a document was deleted.
    """
    with get_connection() as connection:
        return connection.execute("DELETE FROM documents WHERE id = ?", (document_id,)).rowcount > 0


def get_allowed_document(user: sqlite3.Row, document_id: int) -> sqlite3.Row | None:
    """Fetch one document by id, only if the user may see it (permission filter in the SQL query).

    Parameters
    ----------
    user : sqlite3.Row
        Row from the users table (needs `id` and `role`).
    document_id : int
        Id of the requested document.

    Returns
    -------
    sqlite3.Row or None
        The document, or None if it does not exist or the user may not see it.
    """
    with get_connection() as connection:
        if user["role"] == "admin":
            return connection.execute(
                "SELECT id, name, project, content FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
        return connection.execute(
            "SELECT d.id, d.name, d.project, d.content FROM documents d "
            "JOIN user_projects up ON up.project = d.project "
            "WHERE up.user_id = ? AND d.id = ?",
            (user["id"], document_id),
        ).fetchone()

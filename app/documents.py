import io
import re
from pathlib import Path

from pypdf import PdfReader

from app.config import PROJECTS
from app.db import get_connection

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


DOCUMENT_COLUMNS = "d.id, d.name, p.code AS project, d.content"


def list_project_codes() -> list[str]:
    """List the codes of the projects a document can be assigned to.

    Returns
    -------
    list of str
        Project codes in creation order (GENERAL first, so it is the upload default).
    """
    with get_connection() as connection:
        return [row["code"] for row in connection.execute("SELECT code FROM projects ORDER BY id")]


def add_document(name: str, project: str, content: str, uploaded_by: int | None = None) -> int:
    """Insert a document, or replace the text and project of the active document with the same name.

    Parameters
    ----------
    name : str
        Document name shown to users and used in citations.
    project : str
        Code of the project the document belongs to.
    content : str
        Full document text.
    uploaded_by : int, optional
        Id of the admin who uploaded it.

    Returns
    -------
    int
        The document id.

    Raises
    ------
    ValueError
        If the project is unknown.
    """
    with get_connection() as connection:
        project_row = connection.execute("SELECT id FROM projects WHERE code = %s", (project,)).fetchone()
        if project_row is None:
            raise ValueError(f"Unknown project '{project}'. Choose one of {list_project_codes()}.")
        return connection.execute(
            "INSERT INTO documents (name, content, project_id, uploaded_by) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (name) WHERE deleted_at IS NULL "
            "DO UPDATE SET content = excluded.content, project_id = excluded.project_id, "
            "uploaded_by = excluded.uploaded_by "
            "RETURNING id",
            (name, content, project_row["id"], uploaded_by),
        ).fetchone()["id"]


def get_allowed_documents(user: dict) -> list[dict]:
    """Fetch only the documents the user may see; the permission filter is part of the SQL query.

    Deleted documents are never returned.

    Parameters
    ----------
    user : dict
        Row from the users table (needs `id` and `role`).

    Returns
    -------
    list of dict
        Documents with id, name, project and content.
    """
    with get_connection() as connection:
        if user["role"] == "admin":
            return connection.execute(
                f"SELECT {DOCUMENT_COLUMNS} FROM documents d JOIN projects p ON p.id = d.project_id "
                "WHERE d.deleted_at IS NULL ORDER BY d.name"
            ).fetchall()
        return connection.execute(
            f"SELECT {DOCUMENT_COLUMNS} FROM documents d JOIN projects p ON p.id = d.project_id "
            "JOIN user_projects up ON up.project_id = d.project_id "
            "WHERE up.user_id = %s AND d.deleted_at IS NULL ORDER BY d.name",
            (user["id"],),
        ).fetchall()


def get_allowed_document_ids(user: dict) -> set[int]:
    """Fetch the ids of the documents the user may see (same SQL permission filter, without the text).

    Parameters
    ----------
    user : dict
        Row from the users table (needs `id` and `role`).

    Returns
    -------
    set of int
        Ids of the visible, non-deleted documents.
    """
    with get_connection() as connection:
        if user["role"] == "admin":
            id_rows = connection.execute("SELECT id FROM documents WHERE deleted_at IS NULL").fetchall()
        else:
            id_rows = connection.execute(
                "SELECT d.id FROM documents d JOIN user_projects up ON up.project_id = d.project_id "
                "WHERE up.user_id = %s AND d.deleted_at IS NULL",
                (user["id"],),
            ).fetchall()
    return {id_row["id"] for id_row in id_rows}


def delete_document(document_id: int) -> bool:
    """Mark a document as deleted, so it is never sent to the LLM or shown again.

    The row is kept so that saved answers citing it keep valid keys (and are then hidden).

    Parameters
    ----------
    document_id : int
        Id of the document to delete.

    Returns
    -------
    bool
        True if an active document was deleted.
    """
    with get_connection() as connection:
        return connection.execute(
            "UPDATE documents SET deleted_at = now() WHERE id = %s AND deleted_at IS NULL", (document_id,)
        ).rowcount > 0


def get_allowed_document(user: dict, document_id: int) -> dict | None:
    """Fetch one document by id, only if the user may see it (permission filter in the SQL query).

    Parameters
    ----------
    user : dict
        Row from the users table (needs `id` and `role`).
    document_id : int
        Id of the requested document.

    Returns
    -------
    dict or None
        The document, or None if it does not exist, was deleted or the user may not see it.
    """
    with get_connection() as connection:
        if user["role"] == "admin":
            return connection.execute(
                f"SELECT {DOCUMENT_COLUMNS} FROM documents d JOIN projects p ON p.id = d.project_id "
                "WHERE d.id = %s AND d.deleted_at IS NULL",
                (document_id,),
            ).fetchone()
        return connection.execute(
            f"SELECT {DOCUMENT_COLUMNS} FROM documents d JOIN projects p ON p.id = d.project_id "
            "JOIN user_projects up ON up.project_id = d.project_id "
            "WHERE up.user_id = %s AND d.id = %s AND d.deleted_at IS NULL",
            (user["id"], document_id),
        ).fetchone()

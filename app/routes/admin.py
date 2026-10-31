import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth import require_admin
from app.documents import (
    add_document,
    delete_document,
    document_name_from_filename,
    extract_text,
    get_allowed_documents,
    list_project_codes,
)
from app.ratings import list_ratings

logger = logging.getLogger("knowledge_finder")

router = APIRouter()


@router.get("/api/admin/documents")
def list_documents(admin_user: dict = Depends(require_admin)) -> dict:
    """List all documents (without their text) and the available projects.

    Parameters
    ----------
    admin_user : dict
        The logged-in admin.

    Returns
    -------
    dict
        {"documents": [{"id", "name", "project", "num_chars"}], "projects": [...]}.
    """
    document_summaries = [
        {"id": document["id"], "name": document["name"], "project": document["project"],
         "num_chars": len(document["content"])}
        for document in get_allowed_documents(admin_user)
    ]
    return {"documents": document_summaries, "projects": list_project_codes()}


@router.post("/api/admin/documents")
async def upload_document(
    file: UploadFile = File(...),
    project: str = Form(...),
    admin_user: dict = Depends(require_admin),
) -> dict:
    """Upload a txt/md/pdf document and assign it to a project.

    Parameters
    ----------
    file : UploadFile
        The uploaded file.
    project : str
        Project to assign the document to.
    admin_user : dict
        The logged-in admin.

    Returns
    -------
    dict
        {"id", "name", "project"}.

    Raises
    ------
    HTTPException
        400 if the file type or project is invalid or no text could be extracted.
    """
    try:
        document_text = extract_text(file.filename or "", await file.read())
        document_name = document_name_from_filename(file.filename)
        document_id = add_document(document_name, project, document_text, admin_user["id"])
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    logger.info("Admin '%s' uploaded '%s' to project %s.", admin_user["username"], document_name, project)
    return {"id": document_id, "name": document_name, "project": project}


@router.get("/api/admin/ratings")
def ratings_list(admin_user: dict = Depends(require_admin)) -> list[dict]:
    """List every answer rating, newest first, for the admin ratings view.

    Parameters
    ----------
    admin_user : dict
        The logged-in admin.

    Returns
    -------
    list of dict
        [{"id", "is_positive", "question", "answer", "username", "created_at", "is_chat_deleted"}].
    """
    return list_ratings()


@router.delete("/api/admin/documents/{document_id}")
def remove_document(document_id: int, admin_user: dict = Depends(require_admin)) -> dict:
    """Delete a document (it is marked as deleted and never used again).

    Parameters
    ----------
    document_id : int
        Id of the document to delete.
    admin_user : dict
        The logged-in admin.

    Returns
    -------
    dict
        {"status": "deleted"}.

    Raises
    ------
    HTTPException
        404 if the document does not exist.
    """
    if not delete_document(document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    logger.info("Admin '%s' deleted document %d.", admin_user["username"], document_id)
    return {"status": "deleted"}

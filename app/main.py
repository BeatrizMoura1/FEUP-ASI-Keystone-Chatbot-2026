import logging

import psycopg

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.auth import SESSION_COOKIE_NAME, get_current_user, get_user_from_session, login, logout, require_admin
from app.chat import answer_question
from app.config import settings
from app.conversations import (
    delete_conversation,
    get_conversation,
    get_recent_history,
    list_conversations,
    list_ratings,
    rate_message,
    save_exchange,
    user_owns_conversation,
)
from app.documents import (
    add_document,
    delete_document,
    document_name_from_filename,
    extract_text,
    get_allowed_document,
    get_allowed_documents,
    list_project_codes,
)
from app.llm import LLMError, RateLimitError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("knowledge_finder")


BUSY_MESSAGE = "Keystone is busy, please try again in a minute."
AI_FAILED_MESSAGE = "The AI service failed, please try again."
DATABASE_UNAVAILABLE_MESSAGE = "Keystone cannot reach its database right now, please try again in a minute."
UNEXPECTED_ERROR_MESSAGE = "Something went wrong on our side, please try again."

app = FastAPI(title="Keystone")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.exception_handler(psycopg.OperationalError)
def database_unavailable(request: Request, error: psycopg.OperationalError) -> JSONResponse:
    """Answer 503 with a plain message when the database cannot be reached; the details go to the log.

    Parameters
    ----------
    request : Request
        The request that failed.
    error : psycopg.OperationalError
        The connection or server error.

    Returns
    -------
    JSONResponse
        {"detail": DATABASE_UNAVAILABLE_MESSAGE} with HTTP 503.
    """
    logger.error("Database unavailable during %s %s: %s", request.method, request.url.path, error)
    return JSONResponse({"detail": DATABASE_UNAVAILABLE_MESSAGE}, status_code=503)


@app.exception_handler(Exception)
def unexpected_error(request: Request, error: Exception) -> JSONResponse:
    """Answer 500 with a plain JSON message for any unhandled error; the traceback goes to the log.

    Parameters
    ----------
    request : Request
        The request that failed.
    error : Exception
        The unhandled error.

    Returns
    -------
    JSONResponse
        {"detail": UNEXPECTED_ERROR_MESSAGE} with HTTP 500.
    """
    logger.exception("Unhandled error during %s %s: %s", request.method, request.url.path, error)
    return JSONResponse({"detail": UNEXPECTED_ERROR_MESSAGE}, status_code=500)


class AskRequest(BaseModel):
    """Body of POST /api/ask."""

    question: str = Field(min_length=1, max_length=2000)
    conversation_id: int | None = None


class LoginRequest(BaseModel):
    """Body of POST /api/login."""

    username: str
    password: str


class RatingRequest(BaseModel):
    """Body of POST /api/ratings."""

    message_id: int
    is_positive: bool


@app.get("/", response_model=None)
def chat_page(request: Request) -> FileResponse | RedirectResponse:
    """Serve the chat page, or redirect to the login page when not logged in.

    Parameters
    ----------
    request : Request
        Incoming request.

    Returns
    -------
    FileResponse or RedirectResponse
        static/index.html, or a redirect to /login.
    """
    if get_user_from_session(request.cookies.get(SESSION_COOKIE_NAME)) is None:
        return RedirectResponse("/login")
    return FileResponse("static/index.html")


@app.get("/login")
def login_page() -> FileResponse:
    """Serve the login page.

    Returns
    -------
    FileResponse
        static/login.html.
    """
    return FileResponse("static/login.html")


@app.post("/api/login")
def login_endpoint(login_request: LoginRequest, response: Response) -> dict:
    """Log in and set the session cookie.

    Parameters
    ----------
    login_request : LoginRequest
        Username and password.
    response : Response
        Used to set the cookie.

    Returns
    -------
    dict
        {"status": "ok"}.

    Raises
    ------
    HTTPException
        401 if the credentials are wrong.
    """
    session_token = login(login_request.username, login_request.password)
    if session_token is None:
        raise HTTPException(status_code=401, detail="Wrong username or password")
    response.set_cookie(SESSION_COOKIE_NAME, session_token, httponly=True, samesite="strict")
    return {"status": "ok"}


@app.post("/api/logout")
def logout_endpoint(request: Request, response: Response) -> dict:
    """Delete the session and clear the cookie.

    Parameters
    ----------
    request : Request
        Incoming request (carries the cookie).
    response : Response
        Used to clear the cookie.

    Returns
    -------
    dict
        {"status": "ok"}.
    """
    logout(request.cookies.get(SESSION_COOKIE_NAME))
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"status": "ok"}


@app.get("/api/me")
def me(user: dict = Depends(get_current_user)) -> dict:
    """Return the logged-in user's name and role.

    Parameters
    ----------
    user : dict
        The logged-in user.

    Returns
    -------
    dict
        {"username", "role"}.
    """
    return {"username": user["username"], "role": user["role"]}


@app.post("/api/ask")
def ask(ask_request: AskRequest, user: dict = Depends(get_current_user)) -> JSONResponse:
    """Answer a question from the documents the user may access and save it in a conversation.

    The last CHAT_HISTORY_MESSAGES messages of the conversation are sent along so follow-up questions work.

    Parameters
    ----------
    ask_request : AskRequest
        The question, and the conversation to add it to (None starts a new conversation).
    user : dict
        The logged-in user.

    Returns
    -------
    JSONResponse
        {"answer", "sources", "conversation_id", "title", "message_id"} on success,
        {"error"} with HTTP 429 (BUSY_MESSAGE) or 502 (AI_FAILED_MESSAGE) on LLM failure; nothing is saved then.

    Raises
    ------
    HTTPException
        404 if the conversation does not exist or belongs to another user.
    """
    if ask_request.conversation_id is not None and not user_owns_conversation(user, ask_request.conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation_history = []
    if ask_request.conversation_id is not None:
        conversation_history = get_recent_history(user, ask_request.conversation_id, settings.chat_history_messages)
    try:
        answer_data = answer_question(user, ask_request.question, conversation_history)
    except RateLimitError:
        logger.warning("LLM still rate-limited after retries for user '%s'.", user["username"])
        return JSONResponse({"error": BUSY_MESSAGE}, status_code=429)
    except LLMError as error:
        logger.error("LLM call failed for user '%s': %s", user["username"], error)
        return JSONResponse({"error": AI_FAILED_MESSAGE}, status_code=502)
    saved_exchange = save_exchange(
        user,
        ask_request.conversation_id,
        ask_request.question,
        answer_data["answer"],
        answer_data["sources"],
        answer_data.pop("context_document_ids"),
    )
    return JSONResponse({**answer_data, **saved_exchange})


@app.get("/api/conversations")
def conversations_list(user: dict = Depends(get_current_user)) -> list[dict]:
    """List the logged-in user's conversations, most recent first.

    Parameters
    ----------
    user : dict
        The logged-in user.

    Returns
    -------
    list of dict
        [{"id", "title", "updated_at"}].
    """
    return list_conversations(user)


@app.get("/api/conversations/{conversation_id}")
def conversation_detail(conversation_id: int, user: dict = Depends(get_current_user)) -> dict:
    """Return one of the user's conversations with its messages.

    Parameters
    ----------
    conversation_id : int
        Conversation to open.
    user : dict
        The logged-in user.

    Returns
    -------
    dict
        {"id", "title", "messages"}.

    Raises
    ------
    HTTPException
        404 if the conversation does not exist or belongs to another user.
    """
    conversation = get_conversation(user, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.delete("/api/conversations/{conversation_id}")
def conversation_delete(conversation_id: int, user: dict = Depends(get_current_user)) -> dict:
    """Delete one of the user's conversations.

    Parameters
    ----------
    conversation_id : int
        Conversation to delete.
    user : dict
        The logged-in user.

    Returns
    -------
    dict
        {"status": "deleted"}.

    Raises
    ------
    HTTPException
        404 if the conversation does not exist or belongs to another user.
    """
    if not delete_conversation(user, conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted"}


@app.get("/api/documents/{document_id}")
def read_document(document_id: int, user: dict = Depends(get_current_user)) -> dict:
    """Return a document's full text for the side panel, if the user may see it.

    Parameters
    ----------
    document_id : int
        Id of the document.
    user : dict
        The logged-in user.

    Returns
    -------
    dict
        {"id", "name", "project", "content"}.

    Raises
    ------
    HTTPException
        404 if the document does not exist or is not visible to the user.
    """
    document = get_allowed_document(user, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return dict(document)


@app.post("/api/ratings")
def rate_answer(rating_request: RatingRequest, user: dict = Depends(get_current_user)) -> dict:
    """Store (or change) a thumbs up / thumbs down rating for one of the user's answers.

    Parameters
    ----------
    rating_request : RatingRequest
        The rated answer's message id and whether the rating is positive.
    user : dict
        The logged-in user.

    Returns
    -------
    dict
        {"status": "saved"}.

    Raises
    ------
    HTTPException
        404 if the message is not one of the user's answers.
    """
    if not rate_message(user, rating_request.message_id, rating_request.is_positive):
        raise HTTPException(status_code=404, detail="Answer not found")
    return {"status": "saved"}


@app.get("/admin", response_model=None)
def admin_page(request: Request) -> FileResponse | RedirectResponse:
    """Serve the admin page to admins; send everyone else back to the chat or login page.

    Parameters
    ----------
    request : Request
        Incoming request.

    Returns
    -------
    FileResponse or RedirectResponse
        static/admin.html, or a redirect.
    """
    user = get_user_from_session(request.cookies.get(SESSION_COOKIE_NAME))
    if user is None:
        return RedirectResponse("/login")
    if user["role"] != "admin":
        return RedirectResponse("/")
    return FileResponse("static/admin.html")


@app.get("/api/admin/documents")
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


@app.post("/api/admin/documents")
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


@app.get("/api/admin/ratings")
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


@app.delete("/api/admin/documents/{document_id}")
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

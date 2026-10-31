import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.chat import answer_question
from app.config import settings
from app.conversations import (
    delete_conversation,
    get_conversation,
    get_recent_history,
    list_conversations,
    save_exchange,
    user_owns_conversation,
)
from app.documents import get_allowed_document
from app.llm import LLMError, RateLimitError
from app.ratings import rate_message

logger = logging.getLogger("knowledge_finder")

BUSY_MESSAGE = "Keystone is busy, please try again in a minute."
AI_FAILED_MESSAGE = "The AI service failed, please try again."

router = APIRouter()


class AskRequest(BaseModel):
    """Body of POST /api/ask."""

    question: str = Field(min_length=1, max_length=2000)
    conversation_id: int | None = None


class RatingRequest(BaseModel):
    """Body of POST /api/ratings."""

    message_id: int
    is_positive: bool


@router.post("/api/ask")
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


@router.get("/api/conversations")
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


@router.get("/api/conversations/{conversation_id}")
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


@router.delete("/api/conversations/{conversation_id}")
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


@router.get("/api/documents/{document_id}")
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


@router.post("/api/ratings")
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

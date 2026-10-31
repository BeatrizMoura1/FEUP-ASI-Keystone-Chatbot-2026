import json
import sqlite3

from app.config import NO_ANSWER_TEXT
from app.db import get_connection
from app.documents import get_allowed_document_ids

MAX_TITLE_LENGTH = 60
HIDDEN_ANSWER_TEXT = (
    "This answer is no longer available because it was based on a document that has been removed "
    "or that you no longer have access to."
)


def make_title(question: str) -> str:
    """Build a conversation title from its first question.

    Parameters
    ----------
    question : str
        The first question asked in the conversation.

    Returns
    -------
    str
        The question on one line, cut to MAX_TITLE_LENGTH characters.
    """
    single_line_question = " ".join(question.split())
    if len(single_line_question) <= MAX_TITLE_LENGTH:
        return single_line_question
    return single_line_question[: MAX_TITLE_LENGTH - 1].rstrip() + "…"


def is_answer_visible(
    answer: str, cited_document_ids: list[int], context_document_ids: list[int], allowed_document_ids: set[int]
) -> bool:
    """Decide if a saved answer may still be shown to (and reused for) the user, given their current access.

    An answer that cites documents is visible only while the user can still see every cited document.
    An answer without citations (other than "No answer found.") could contain text from any document that
    was in its prompt, so it is visible only while the user can still see all of those documents.

    Parameters
    ----------
    answer : str
        The saved answer text.
    cited_document_ids : list of int
        Ids of the documents the answer cited.
    context_document_ids : list of int
        Ids of every document that was in the prompt when the answer was generated.
    allowed_document_ids : set of int
        Ids of the documents the user may see now.

    Returns
    -------
    bool
        True if the answer can be shown.
    """
    if cited_document_ids:
        return set(cited_document_ids) <= allowed_document_ids
    if answer == NO_ANSWER_TEXT:
        return True
    return set(context_document_ids) <= allowed_document_ids


def list_conversations(user: sqlite3.Row) -> list[dict]:
    """List the user's conversations, most recently active first.

    Parameters
    ----------
    user : sqlite3.Row
        The logged-in user.

    Returns
    -------
    list of dict
        [{"id", "title", "updated_at"}].
    """
    with get_connection() as connection:
        conversation_rows = connection.execute(
            "SELECT id, title, updated_at FROM conversations WHERE user_id = ? ORDER BY updated_at DESC, id DESC",
            (user["id"],),
        ).fetchall()
    return [dict(conversation_row) for conversation_row in conversation_rows]


def user_owns_conversation(user: sqlite3.Row, conversation_id: int) -> bool:
    """Check that a conversation exists and belongs to the user.

    Parameters
    ----------
    user : sqlite3.Row
        The logged-in user.
    conversation_id : int
        Conversation to check.

    Returns
    -------
    bool
        True if the user owns the conversation.
    """
    with get_connection() as connection:
        return connection.execute(
            "SELECT 1 FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user["id"])
        ).fetchone() is not None


def get_conversation(user: sqlite3.Row, conversation_id: int) -> dict | None:
    """Fetch one of the user's conversations with its messages, hiding answers the user may no longer see.

    Hidden answers are replaced on the server, so their text never reaches the browser.

    Parameters
    ----------
    user : sqlite3.Row
        The logged-in user.
    conversation_id : int
        Conversation to fetch.

    Returns
    -------
    dict or None
        {"id", "title", "messages": [{"id", "role", "content", "sources", "rating", "is_hidden"}]},
        or None if the conversation does not exist or belongs to someone else.
        "rating" is True (thumbs up), False (thumbs down) or None (not rated).
    """
    with get_connection() as connection:
        conversation_row = connection.execute(
            "SELECT id, title FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user["id"])
        ).fetchone()
        if conversation_row is None:
            return None
        message_rows = connection.execute(
            "SELECT m.id, m.role, m.content, m.sources_json, m.context_document_ids_json, r.is_positive "
            "FROM messages m LEFT JOIN ratings r ON r.message_id = m.id "
            "WHERE m.conversation_id = ? ORDER BY m.id",
            (conversation_id,),
        ).fetchall()
    allowed_document_ids = get_allowed_document_ids(user)
    conversation_messages = []
    for message_row in message_rows:
        message_sources = json.loads(message_row["sources_json"])
        is_hidden = message_row["role"] == "assistant" and not is_answer_visible(
            message_row["content"],
            [source["id"] for source in message_sources],
            json.loads(message_row["context_document_ids_json"]),
            allowed_document_ids,
        )
        conversation_messages.append(
            {
                "id": message_row["id"],
                "role": message_row["role"],
                "content": HIDDEN_ANSWER_TEXT if is_hidden else message_row["content"],
                "sources": [] if is_hidden else message_sources,
                "rating": None if message_row["is_positive"] is None else bool(message_row["is_positive"]),
                "is_hidden": is_hidden,
            }
        )
    return {"id": conversation_row["id"], "title": conversation_row["title"], "messages": conversation_messages}


def get_recent_history(user: sqlite3.Row, conversation_id: int, max_messages: int) -> list[dict]:
    """Return the last messages of a conversation to give the model context for a follow-up question.

    Answers the user may no longer see are left out, so revoked or deleted documents never reach the prompt
    through the chat history.

    Parameters
    ----------
    user : sqlite3.Row
        The logged-in user.
    conversation_id : int
        Conversation the new question belongs to.
    max_messages : int
        Maximum number of messages to return (0 returns none).

    Returns
    -------
    list of dict
        [{"role": "user" | "assistant", "content": str}], oldest first.
    """
    conversation = get_conversation(user, conversation_id)
    if conversation is None or max_messages <= 0:
        return []
    usable_messages = [
        {"role": message["role"], "content": message["content"]}
        for message in conversation["messages"]
        if not message["is_hidden"]
    ]
    return usable_messages[-max_messages:]


def save_exchange(
    user: sqlite3.Row,
    conversation_id: int | None,
    question: str,
    answer: str,
    sources: list[dict],
    context_document_ids: list[int],
) -> dict:
    """Store a question and its answer, creating the conversation first if needed.

    Parameters
    ----------
    user : sqlite3.Row
        The logged-in user.
    conversation_id : int or None
        Existing conversation (must belong to the user), or None to start a new one titled after the question.
    question : str
        The user's question.
    answer : str
        The assistant's answer.
    sources : list of dict
        Cited documents as [{"id", "name"}].
    context_document_ids : list of int
        Ids of every document that was in the prompt, used later to decide if the answer may still be shown.

    Returns
    -------
    dict
        {"conversation_id", "title", "message_id"} where message_id is the stored answer's id.

    Raises
    ------
    ValueError
        If conversation_id is given but does not belong to the user.
    """
    with get_connection() as connection:
        if conversation_id is None:
            conversation_title = make_title(question)
            conversation_id = connection.execute(
                "INSERT INTO conversations (user_id, title) VALUES (?, ?)", (user["id"], conversation_title)
            ).lastrowid
        else:
            conversation_row = connection.execute(
                "SELECT title FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user["id"])
            ).fetchone()
            if conversation_row is None:
                raise ValueError(f"Conversation {conversation_id} not found for user '{user['username']}'")
            conversation_title = conversation_row["title"]
            connection.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (conversation_id,)
            )
        connection.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'user', ?)", (conversation_id, question)
        )
        answer_message_id = connection.execute(
            "INSERT INTO messages (conversation_id, role, content, sources_json, context_document_ids_json) "
            "VALUES (?, 'assistant', ?, ?, ?)",
            (conversation_id, answer, json.dumps(sources), json.dumps(context_document_ids)),
        ).lastrowid
    return {"conversation_id": conversation_id, "title": conversation_title, "message_id": answer_message_id}


def delete_conversation(user: sqlite3.Row, conversation_id: int) -> bool:
    """Delete one of the user's conversations and its messages (ratings are kept, unlinked).

    Parameters
    ----------
    user : sqlite3.Row
        The logged-in user.
    conversation_id : int
        Conversation to delete.

    Returns
    -------
    bool
        True if a conversation was deleted.
    """
    with get_connection() as connection:
        return connection.execute(
            "DELETE FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user["id"])
        ).rowcount > 0


def rate_message(user: sqlite3.Row, message_id: int, is_positive: bool) -> bool:
    """Store (or change) the user's thumbs up / down for one of their assistant answers.

    Parameters
    ----------
    user : sqlite3.Row
        The logged-in user.
    message_id : int
        The assistant message being rated.
    is_positive : bool
        True for thumbs up.

    Returns
    -------
    bool
        False if the message does not exist, is not an answer, or belongs to another user's conversation.
    """
    with get_connection() as connection:
        answer_row = connection.execute(
            "SELECT m.content AS answer, "
            "(SELECT q.content FROM messages q WHERE q.conversation_id = m.conversation_id AND q.id < m.id "
            " AND q.role = 'user' ORDER BY q.id DESC LIMIT 1) AS question "
            "FROM messages m JOIN conversations c ON c.id = m.conversation_id "
            "WHERE m.id = ? AND m.role = 'assistant' AND c.user_id = ?",
            (message_id, user["id"]),
        ).fetchone()
        if answer_row is None:
            return False
        connection.execute(
            "INSERT INTO ratings (user_id, question, answer, is_positive, message_id) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (message_id) WHERE message_id IS NOT NULL "
            "DO UPDATE SET is_positive = excluded.is_positive, created_at = CURRENT_TIMESTAMP",
            (user["id"], answer_row["question"] or "", answer_row["answer"], int(is_positive), message_id),
        )
    return True

from app.db import get_connection


def rate_message(user: dict, message_id: int, is_positive: bool) -> bool:
    """Store (or change) the user's thumbs up / down for one of their assistant answers.

    Parameters
    ----------
    user : dict
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
            "WHERE m.id = %s AND m.role = 'assistant' AND c.user_id = %s",
            (message_id, user["id"]),
        ).fetchone()
        if answer_row is None:
            return False
        connection.execute(
            "INSERT INTO ratings (user_id, question, answer, is_positive, message_id) VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (message_id) DO UPDATE SET is_positive = excluded.is_positive, created_at = now()",
            (user["id"], answer_row["question"] or "", answer_row["answer"], is_positive, message_id),
        )
    return True


def list_ratings() -> list[dict]:
    """List every rating for the admin, newest first, including ratings whose chat was deleted.

    Returns
    -------
    list of dict
        [{"id", "is_positive", "question", "answer", "username", "created_at", "is_chat_deleted"}].
    """
    with get_connection() as connection:
        return connection.execute(
            "SELECT r.id, r.is_positive, r.question, r.answer, u.username, r.created_at, "
            "r.message_id IS NULL AS is_chat_deleted "
            "FROM ratings r JOIN users u ON u.id = r.user_id ORDER BY r.created_at DESC, r.id DESC"
        ).fetchall()

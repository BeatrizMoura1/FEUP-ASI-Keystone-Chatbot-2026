from tests.conftest import login_as


def ask_and_rate(client, question: str, is_positive: bool) -> dict:
    """Ask a question as the logged-in user and rate its answer.

    Parameters
    ----------
    client : TestClient
        Logged-in client.
    question : str
        Question to ask.
    is_positive : bool
        True for thumbs up.

    Returns
    -------
    dict
        The /api/ask response.
    """
    answer = client.post("/api/ask", json={"question": question}).json()
    client.post("/api/ratings", json={"message_id": answer["message_id"], "is_positive": is_positive})
    return answer


def test_admin_sees_ratings_newest_first(client, numbered_llm):
    """The admin sees every user's ratings, newest first, with question, answer and user (S1)."""
    login_as(client, "employee", "employee123")
    ask_and_rate(client, "Carry-over days?", True)
    login_as(client, "newhire", "newhire123")
    ask_and_rate(client, "Remote work abroad?", False)
    login_as(client, "admin", "admin123")

    ratings = client.get("/api/admin/ratings").json()

    rating_rows = [
        (rating["username"], rating["question"], rating["answer"], rating["is_positive"]) for rating in ratings
    ]
    assert rating_rows == [
        ("newhire", "Remote work abroad?", "Answer number 2", False),
        ("employee", "Carry-over days?", "Answer number 1", True),
    ]
    assert all(rating["created_at"] and rating["is_chat_deleted"] is False for rating in ratings)


def test_changed_rating_shows_its_latest_value_once(client, numbered_llm):
    """Changing a rating updates it in place instead of adding a second one."""
    login_as(client, "employee", "employee123")
    answer = ask_and_rate(client, "Carry-over days?", True)
    client.post("/api/ratings", json={"message_id": answer["message_id"], "is_positive": False})
    login_as(client, "admin", "admin123")

    ratings = client.get("/api/admin/ratings").json()

    assert len(ratings) == 1
    assert ratings[0]["is_positive"] is False


def test_rating_stays_visible_after_its_chat_is_deleted(client, numbered_llm):
    """A rating stays listed, marked as from a deleted chat, after the user deletes the chat."""
    login_as(client, "employee", "employee123")
    answer = ask_and_rate(client, "Carry-over days?", False)
    client.delete(f"/api/conversations/{answer['conversation_id']}")
    login_as(client, "admin", "admin123")

    ratings = client.get("/api/admin/ratings").json()

    assert [(rating["question"], rating["is_chat_deleted"]) for rating in ratings] == [("Carry-over days?", True)]


def test_no_ratings_gives_an_empty_list(client):
    """With no ratings the admin list is empty."""
    login_as(client, "admin", "admin123")

    assert client.get("/api/admin/ratings").json() == []


def test_employee_cannot_read_ratings(client, numbered_llm):
    """Employees get 403 on the admin ratings list."""
    login_as(client, "employee", "employee123")
    ask_and_rate(client, "Carry-over days?", True)

    assert client.get("/api/admin/ratings").status_code == 403


def test_ratings_require_login(client):
    """The ratings list needs a login."""
    assert client.get("/api/admin/ratings").status_code == 401

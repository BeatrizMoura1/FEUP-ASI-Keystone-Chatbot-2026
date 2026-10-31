from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.auth import SESSION_COOKIE_NAME, get_current_user, login, logout

router = APIRouter()


class LoginRequest(BaseModel):
    """Body of POST /api/login."""

    username: str
    password: str


@router.post("/api/login")
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


@router.post("/api/logout")
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


@router.get("/api/me")
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

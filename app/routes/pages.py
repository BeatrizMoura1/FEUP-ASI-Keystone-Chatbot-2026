from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, RedirectResponse

from app.auth import SESSION_COOKIE_NAME, get_user_from_session

router = APIRouter()


@router.get("/", response_model=None)
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


@router.get("/login")
def login_page() -> FileResponse:
    """Serve the login page.

    Returns
    -------
    FileResponse
        static/login.html.
    """
    return FileResponse("static/login.html")


@router.get("/admin", response_model=None)
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

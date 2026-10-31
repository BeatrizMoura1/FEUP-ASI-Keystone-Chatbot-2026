import logging

import psycopg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routes import account, admin, chat, pages

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("knowledge_finder")

DATABASE_UNAVAILABLE_MESSAGE = "Keystone cannot reach its database right now, please try again in a minute."
UNEXPECTED_ERROR_MESSAGE = "Something went wrong on our side, please try again."

app = FastAPI(title="Keystone")
app.mount("/static", StaticFiles(directory="static"), name="static")
for router_module in (pages, account, chat, admin):
    app.include_router(router_module.router)


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

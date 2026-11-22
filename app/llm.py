import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger("knowledge_finder")

GEMINI_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
REQUEST_TIMEOUT_SECONDS = 120
TRANSIENT_STATUS_CODES = {500, 502, 503, 504}


class RateLimitError(Exception):
    """Raised when the LLM provider keeps answering HTTP 429 after all retries."""


class LLMError(Exception):
    """Raised for any other LLM provider failure (bad config, HTTP error, unexpected response)."""


class TransientLLMError(LLMError):
    """Raised for a brief provider failure that usually works on the next try (HTTP 5xx, refused or dropped
    connection)."""


def generate(system_prompt: str, user_prompt: str) -> str:
    """Send one prompt to Gemini and return its raw text reply.

    This is the single entry point for LLM calls.
    HTTP 429 responses are retried LLM_MAX_RETRIES times, LLM_RETRY_WAIT_SECONDS apart. Brief failures
    (HTTP 500, 502, 503, 504, or a refused or dropped connection) are retried LLM_TRANSIENT_RETRIES times,
    LLM_TRANSIENT_RETRY_WAIT_SECONDS apart. A timeout and any other error are not retried.

    Parameters
    ----------
    system_prompt : str
        Instructions for the model.
    user_prompt : str
        Documents plus the user's question.

    Returns
    -------
    str
        The model's raw text output (expected to be JSON).

    Raises
    ------
    RateLimitError
        If the provider still rate-limits after LLM_MAX_RETRIES retries.
    TransientLLMError
        If a brief failure persists after LLM_TRANSIENT_RETRIES retries.
    LLMError
        For configuration errors or any other provider failure.
    """
    num_rate_limit_retries = 0
    num_transient_retries = 0
    while True:
        try:
            return _call_gemini(system_prompt, user_prompt)
        except RateLimitError:
            if num_rate_limit_retries == settings.llm_max_retries:
                logger.error("LLM rate limit persisted after %d retries.", settings.llm_max_retries)
                raise
            num_rate_limit_retries += 1
            logger.warning("LLM rate limited (429), retrying in %.0fs...", settings.llm_retry_wait_seconds)
            time.sleep(settings.llm_retry_wait_seconds)
        except TransientLLMError as error:
            if num_transient_retries == settings.llm_transient_retries:
                logger.error("LLM failure persisted after %d retries: %s", settings.llm_transient_retries, error)
                raise
            num_transient_retries += 1
            logger.warning(
                "LLM brief failure (%s), retrying in %.0fs...", error, settings.llm_transient_retry_wait_seconds
            )
            time.sleep(settings.llm_transient_retry_wait_seconds)


def _call_gemini(system_prompt: str, user_prompt: str) -> str:
    """Call the Gemini generateContent REST endpoint.

    Parameters
    ----------
    system_prompt : str
        Sent as `systemInstruction`.
    user_prompt : str
        Sent as the single user turn.

    Returns
    -------
    str
        Text of the first candidate.

    Raises
    ------
    RateLimitError
        On HTTP 429.
    TransientLLMError
        On HTTP 500, 502, 503 or 504, or a refused or dropped connection.
    LLMError
        On missing config, a timeout, other HTTP errors or an empty/blocked response.
    """
    if not settings.gemini_api_key or not settings.gemini_model:
        raise LLMError("GEMINI_API_KEY and GEMINI_MODEL must be set in .env")
    request_body = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
    }
    try:
        response = httpx.post(
            GEMINI_URL_TEMPLATE.format(model=settings.gemini_model),
            headers={"x-goog-api-key": settings.gemini_api_key},
            json=request_body,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError) as error:
        raise TransientLLMError(f"Cannot reach Gemini: {error}") from error
    except httpx.TimeoutException as error:
        raise LLMError(f"Gemini did not answer within {REQUEST_TIMEOUT_SECONDS}s") from error
    except httpx.HTTPError as error:
        raise LLMError(f"Cannot reach Gemini: {error}") from error
    if response.status_code == 429:
        raise RateLimitError("Gemini rate limit reached")
    if response.status_code in TRANSIENT_STATUS_CODES:
        raise TransientLLMError(f"Gemini returned HTTP {response.status_code}: {response.text[:300]}")
    if response.status_code != 200:
        raise LLMError(f"Gemini returned HTTP {response.status_code}: {response.text[:300]}")
    try:
        response_parts = response.json()["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError) as error:
        raise LLMError(f"Unexpected Gemini response: {response.text[:300]}") from error
    return "".join(part.get("text", "") for part in response_parts)

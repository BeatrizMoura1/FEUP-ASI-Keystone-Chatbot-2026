import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger("knowledge_finder")

GEMINI_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
REQUEST_TIMEOUT_SECONDS = 120


class RateLimitError(Exception):
    """Raised when the LLM provider keeps answering HTTP 429 after all retries."""


class LLMError(Exception):
    """Raised for any other LLM provider failure (bad config, HTTP error, unexpected response)."""


def generate(system_prompt: str, user_prompt: str) -> str:
    """Send one prompt to Gemini and return its raw text reply.

    This is the single entry point for LLM calls.
    HTTP 429 responses are retried a few times with a short wait before giving up.

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
    LLMError
        For configuration errors or any other provider failure.
    """
    for attempt_number in range(settings.llm_max_retries + 1):
        try:
            return _call_gemini(system_prompt, user_prompt)
        except RateLimitError:
            if attempt_number == settings.llm_max_retries:
                logger.error("LLM rate limit persisted after %d retries.", settings.llm_max_retries)
                raise
            logger.warning("LLM rate limited (429), retrying in %.0fs...", settings.llm_retry_wait_seconds)
            time.sleep(settings.llm_retry_wait_seconds)
    raise LLMError("Unreachable")


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
    LLMError
        On missing config, a timeout or connection failure, other HTTP errors or an empty/blocked response.
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
    except httpx.TimeoutException as error:
        raise LLMError(f"Gemini did not answer within {REQUEST_TIMEOUT_SECONDS}s") from error
    except httpx.HTTPError as error:
        raise LLMError(f"Cannot reach Gemini: {error}") from error
    if response.status_code == 429:
        raise RateLimitError("Gemini rate limit reached")
    if response.status_code != 200:
        raise LLMError(f"Gemini returned HTTP {response.status_code}: {response.text[:300]}")
    try:
        response_parts = response.json()["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError) as error:
        raise LLMError(f"Unexpected Gemini response: {response.text[:300]}") from error
    return "".join(part.get("text", "") for part in response_parts)

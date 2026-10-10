"""Server-side Dify client. The browser NEVER calls Dify — only this backend does.

Uses the Dify Chat App "Send Chat Message" API (blocking mode):

    POST {DIFY_BASE_URL}/chat-messages
    Authorization: Bearer {DIFY_API_KEY}
    {
      "query": "<user message>",
      "inputs": {},
      "response_mode": "blocking",
      "conversation_id": "<id or empty to start>",
      "user": "<end-user id>"
    }

Blocking response (JSON) includes:
    { "answer": "<reply text>", "conversation_id": "...", "message_id": "...", ... }

Field mapping to our contract:
    our `message`  -> Dify `query`
    our reply      <- Dify `answer`
    conversation_id is tracked per session_id (see router).

Reference: Dify docs — Chat App API / Send Chat Message (blocking mode returns the
full reply once finished). Keys come from .env (DIFY_API_KEY, DIFY_BASE_URL).
"""

from __future__ import annotations

import httpx

from app.config import get_settings

settings = get_settings()

# Reasonable timeouts for a demo: connect quickly, allow the model time to answer.
_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)


class DifyError(Exception):
    """Raised when Dify is misconfigured or returns an error/timeout."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _base_url() -> str:
    base = (settings.dify_base_url or "").rstrip("/")
    if not base:
        raise DifyError("Chatbot is not configured (DIFY_BASE_URL missing).", 503)
    return base


def _headers() -> dict:
    if not settings.dify_api_key:
        raise DifyError("Chatbot is not configured (DIFY_API_KEY missing).", 503)
    return {
        "Authorization": f"Bearer {settings.dify_api_key}",
        "Content-Type": "application/json",
    }


def send_chat_message(
    *,
    query: str,
    user: str,
    conversation_id: str | None = None,
    inputs: dict | None = None,
) -> dict:
    """Call Dify chat-messages (blocking). Returns the parsed JSON dict.

    Raises DifyError on configuration problems, timeouts, or non-2xx responses.
    """
    url = f"{_base_url()}/chat-messages"
    payload = {
        "query": query,
        "inputs": inputs or {},
        "response_mode": "blocking",
        # Dify starts a new conversation when conversation_id is an empty string.
        "conversation_id": conversation_id or "",
        "user": user,
    }

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(url, headers=_headers(), json=payload)
    except httpx.TimeoutException:
        raise DifyError("The assistant took too long to respond. Please try again.", 504)
    except httpx.RequestError as exc:
        raise DifyError(f"Could not reach the assistant service: {exc}", 502)

    if resp.status_code >= 400:
        # Surface Dify's error message when present, without leaking the key.
        detail = ""
        try:
            body = resp.json()
            detail = body.get("message") or body.get("error") or ""
        except Exception:
            detail = resp.text[:200]
        raise DifyError(
            f"Assistant service error ({resp.status_code}): {detail}".strip(),
            502 if resp.status_code >= 500 else 400,
        )

    try:
        return resp.json()
    except ValueError:
        raise DifyError("Assistant returned an unreadable response.", 502)

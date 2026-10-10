"""Maps our session_id -> Dify conversation_id so multi-turn context is kept.

In-memory store (fine for a hackathon / single process). For a multi-worker
deployment this would move to Redis or a DB table.
"""

from __future__ import annotations

import threading

_lock = threading.Lock()
_session_to_conversation: dict[str, str] = {}


def get_conversation_id(session_id: str) -> str | None:
    with _lock:
        return _session_to_conversation.get(session_id)


def set_conversation_id(session_id: str, conversation_id: str) -> None:
    if not conversation_id:
        return
    with _lock:
        _session_to_conversation[session_id] = conversation_id


def reset(session_id: str) -> None:
    with _lock:
        _session_to_conversation.pop(session_id, None)

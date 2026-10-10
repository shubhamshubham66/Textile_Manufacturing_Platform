"""Chatbot proxy route — POST /api/chatbot/message.

Flow: Chat UI -> this backend -> Dify. The browser never calls Dify directly.

- Public mode (no/invalid token): FAQ + how-to only; no private factory data.
- Logged-in mode (valid token): a role-scoped live-data facts block is attached,
  limited by role (a buyer only sees their own orders).

Request:  { "message": str, "session_id": str }
Response: { "reply": str }
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import decode_access_token

from chatbot import sessions
from chatbot.context import build_context
from chatbot.dify_client import DifyError, send_chat_message

router = APIRouter(prefix="/api/chatbot", tags=["chatbot"])

_optional_bearer = HTTPBearer(auto_error=False)


class ChatRequest(BaseModel):
    message: str
    session_id: str

    @field_validator("message", "session_id")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


def _resolve_optional_user(
    creds: HTTPAuthorizationCredentials | None, db: Session
) -> User | None:
    """Resolve a user if a valid token is present; otherwise None (public mode).

    Never raises for a missing/invalid token — the chatbot is usable logged-out.
    """
    if creds is None or not creds.credentials:
        return None
    payload = decode_access_token(creds.credentials)
    if not payload or "sub" not in payload:
        return None
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if user is None or not user.is_active:
        return None
    return user


@router.post("/message")
def chatbot_message(
    body: ChatRequest,
    creds: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    db: Session = Depends(get_db),
):
    user = _resolve_optional_user(creds, db)

    # Build the query. In logged-in mode, prepend a role-scoped facts block so the
    # assistant can answer from live data (limited by role). Public mode sends the
    # raw message only — no private data.
    context = build_context(db, user)
    if context:
        query = (
            "You have access to the following live data for the current user. "
            "Only use it to answer; do not reveal data about other users.\n"
            f"---\n{context}\n---\n\nUser question: {body.message}"
        )
    else:
        query = body.message

    # Stable per-session end-user id for Dify; include role for traceability.
    dify_user = f"session:{body.session_id}"
    if user is not None:
        dify_user = f"user:{user.id}:{user.role.name}"

    conversation_id = sessions.get_conversation_id(body.session_id)

    try:
        result = send_chat_message(
            query=query,
            user=dify_user,
            conversation_id=conversation_id,
        )
    except DifyError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "CHATBOT_ERROR", "message": exc.message}},
        )

    # Persist the conversation id so the next turn keeps context.
    new_conv = result.get("conversation_id")
    if new_conv:
        sessions.set_conversation_id(body.session_id, new_conv)

    reply = result.get("answer", "")
    return {"reply": reply}

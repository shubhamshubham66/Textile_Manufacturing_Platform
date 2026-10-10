"""Password hashing and JWT helpers.

- Passwords are hashed with bcrypt (via passlib). Plaintext is never stored.
- Auth uses stateless JWT bearer tokens signed with JWT_SECRET from settings.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


def create_access_token(subject: str, extra: dict | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expire_minutes
    )
    payload: dict = {"sub": str(subject), "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError:
        return None


# Short-lived proof that an email address passed the signup OTP check. It is a
# separate token type ("purpose") so it can never be used as a login token.
SIGNUP_PURPOSE = "signup_email"


def create_email_token(email: str, minutes: int = 15) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"email": email, "purpose": SIGNUP_PURPOSE, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def read_email_token(token: str) -> str | None:
    """Return the verified email, or None if the token is bad or expired."""
    data = decode_access_token(token)
    if not data or data.get("purpose") != SIGNUP_PURPOSE:
        return None
    return data.get("email")


# One-minute ticket for opening the live event stream. EventSource cannot send
# an Authorization header, and putting the login token in the URL would leak it
# into access logs; this ticket is short-lived and has no "sub", so it can never
# be used to log in or call any other API.
LIVE_PURPOSE = "live_stream"


def create_live_ticket(user_id: int, seconds: int = 60) -> str:
    expire = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    payload = {"uid": int(user_id), "purpose": LIVE_PURPOSE, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def read_live_ticket(ticket: str) -> int | None:
    data = decode_access_token(ticket)
    if not data or data.get("purpose") != LIVE_PURPOSE or "uid" not in data:
        return None
    return int(data["uid"])

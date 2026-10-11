"""Forgot password for buyer accounts (email OTP).

  1. POST /api/auth/forgot/send-otp  {email}                    -> code emailed
  2. POST /api/auth/forgot/reset     {email, otp, password,
                                      confirm_password}         -> password changed

Only buyer logins (self-signup with an email) can reset here. Staff logins are
reset by the owner / Supermanager. The send step answers the same way whether
or not the email has a buyer account, so it can't be used to discover emails.
Reuses the signup OTP table: a signup code needs NO account and a reset code
needs one, so the two never clash for the same email.
"""

from __future__ import annotations

import re
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app import rbac
from app.config import get_settings
from app.database import get_db
from app.models import EmailOtp, User
from app.routers.signup import _clean_email, _now
from app.security import hash_password, verify_password
from app.services.email import EmailNotConfigured, EmailSendFailed, email_configured, send_reset_otp

router = APIRouter(prefix="/api/auth/forgot", tags=["forgot-password"])

GENERIC = "If a buyer account exists for this email, a reset code has been sent."


class SendIn(BaseModel):
    email: str

    _e = field_validator("email")(classmethod(lambda cls, v: _clean_email(v)))


class ResetIn(BaseModel):
    email: str
    otp: str
    password: str
    confirm_password: str

    _e = field_validator("email")(classmethod(lambda cls, v: _clean_email(v)))
    @field_validator("password")
    @classmethod
    def password_ok(cls, v: str) -> str:
        if len(v or "") < 8 or not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("Password needs at least 8 characters, with letters and numbers")
        return v

    @field_validator("otp")
    @classmethod
    def six_digits(cls, v: str) -> str:
        v = (v or "").strip()
        if not re.fullmatch(r"\d{6}", v):
            raise ValueError("Enter the 6-digit code")
        return v


def _buyer(db: Session, email: str) -> User | None:
    u = db.query(User).filter(User.email == email).first()
    if u is None or not u.is_active or u.role is None or u.role.name != rbac.ROLE_BUYER:
        return None
    return u


@router.post("/send-otp")
def send_otp(body: SendIn, db: Session = Depends(get_db)):
    s = get_settings()
    dev_mode = s.signup_dev_otp and not email_configured()
    if not email_configured() and not dev_mode:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Email sending is not set up on the server yet.")

    out = {"message": GENERIC, "resend_after": s.otp_resend_seconds}
    if _buyer(db, body.email) is None:
        return out

    now = _now()
    row = db.query(EmailOtp).filter(EmailOtp.email == body.email).first()
    if row and (now - row.sent_at).total_seconds() < s.otp_resend_seconds:
        wait = s.otp_resend_seconds - int((now - row.sent_at).total_seconds())
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Please wait {wait}s before asking for a new code.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    if row is None:
        row = EmailOtp(email=body.email)
        db.add(row)
    row.code_hash = hash_password(code)
    row.expires_at = now + timedelta(minutes=s.otp_expire_minutes)
    row.sent_at = now
    row.attempts = 0

    if not dev_mode:
        try:
            send_reset_otp(body.email, code, s.otp_expire_minutes)
        except (EmailNotConfigured, EmailSendFailed) as exc:
            db.rollback()
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"{exc} Please try again.") from exc
    db.commit()
    if dev_mode:
        out["dev_otp"] = code  # local development only
    return out


@router.post("/reset")
def reset(body: ResetIn, db: Session = Depends(get_db)):
    s = get_settings()
    if body.password != body.confirm_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Passwords do not match")
    user = _buyer(db, body.email)
    row = db.query(EmailOtp).filter(EmailOtp.email == body.email).first()
    if user is None or row is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No reset code was sent to this email. Ask for a new code.")
    if _now() > row.expires_at:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This code has expired. Ask for a new code.")
    if row.attempts >= s.otp_max_attempts:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many wrong tries. Ask for a new code.")
    if not verify_password(body.otp, row.code_hash):
        row.attempts += 1
        db.commit()
        left = s.otp_max_attempts - row.attempts
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Wrong code. {left} {'try' if left == 1 else 'tries'} left." if left > 0 else "Too many wrong tries. Ask for a new code.",
        )

    user.password_hash = hash_password(body.password)
    db.delete(row)  # one use only
    db.commit()
    return {"message": "Password changed. You can now sign in."}

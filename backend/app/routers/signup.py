"""Self-service signup with an email OTP.

Flow (each step needs the previous one):
  1. POST /api/auth/signup/send-otp    {email}            -> code emailed
  2. POST /api/auth/signup/verify-otp  {email, otp}       -> email_token
  3. POST /api/auth/signup             {name, email, role, password,
                                        confirm_password, email_token}
                                                           -> account created

The OTP is 6 digits, stored only as a bcrypt hash, expires after
OTP_EXPIRE_MINUTES, allows OTP_MAX_ATTEMPTS wrong tries, and can be re-sent
after OTP_RESEND_SECONDS. A buyer signup also creates its buyer record, so the
new buyer sees only their own orders.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app import rbac
from app.config import get_settings
from app.database import get_db
from app.models import Buyer, EmailOtp, Role, User
from app.security import create_email_token, hash_password, read_email_token, verify_password
from app.services.email import EmailNotConfigured, EmailSendFailed, email_configured, send_signup_otp

router = APIRouter(prefix="/api/auth/signup", tags=["signup"])

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _now() -> datetime:
    # Naive UTC, matching how DateTime columns are stored (see models._utcnow
    # and the UTC session timezone on Postgres).
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _clean_email(v: str) -> str:
    v = (v or "").strip().lower()
    if not EMAIL_RE.match(v):
        raise ValueError("Enter a valid email address")
    return v


# ---- Schemas ----
class SendOtpIn(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def email_ok(cls, v: str) -> str:
        return _clean_email(v)


class VerifyOtpIn(BaseModel):
    email: str
    otp: str

    @field_validator("email")
    @classmethod
    def email_ok(cls, v: str) -> str:
        return _clean_email(v)

    @field_validator("otp")
    @classmethod
    def six_digits(cls, v: str) -> str:
        v = (v or "").strip()
        if not re.fullmatch(r"\d{6}", v):
            raise ValueError("Enter the 6-digit code")
        return v


class SignupIn(BaseModel):
    name: str
    email: str
    role: str
    password: str
    confirm_password: str
    email_token: str

    @field_validator("email")
    @classmethod
    def email_ok(cls, v: str) -> str:
        return _clean_email(v)

    @field_validator("name")
    @classmethod
    def name_ok(cls, v: str) -> str:
        v = " ".join((v or "").split())
        if len(v) < 2 or len(v) > 120:
            raise ValueError("Name must be 2 to 120 characters")
        return v

    @field_validator("role")
    @classmethod
    def role_ok(cls, v: str) -> str:
        if v not in rbac.ALL_ROLES:
            raise ValueError("Choose a role from the list")
        return v

    @field_validator("password")
    @classmethod
    def password_ok(cls, v: str) -> str:
        if len(v or "") < 8 or not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("Password needs at least 8 characters, with letters and numbers")
        return v


# ---- Endpoints ----
@router.post("/send-otp")
def send_otp(body: SendOtpIn, db: Session = Depends(get_db)):
    s = get_settings()
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists. Please sign in.")

    row = db.query(EmailOtp).filter(EmailOtp.email == body.email).first()
    now = _now()
    if row and (now - row.sent_at).total_seconds() < s.otp_resend_seconds:
        wait = s.otp_resend_seconds - int((now - row.sent_at).total_seconds())
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Please wait {wait}s before asking for a new code.")

    dev_mode = s.signup_dev_otp and not email_configured()
    if not email_configured() and not dev_mode:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Email sending is not set up on the server yet.")

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
            send_signup_otp(body.email, code, s.otp_expire_minutes)
        except (EmailNotConfigured, EmailSendFailed) as exc:
            db.rollback()
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"{exc} Please try again.") from exc
    db.commit()

    out = {"message": f"Code sent to {body.email}", "resend_after": s.otp_resend_seconds}
    if dev_mode:
        out["dev_otp"] = code  # local development only (SIGNUP_DEV_OTP=true, no Brevo key)
    return out


@router.post("/verify-otp")
def verify_otp(body: VerifyOtpIn, db: Session = Depends(get_db)):
    s = get_settings()
    row = db.query(EmailOtp).filter(EmailOtp.email == body.email).first()
    if row is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No code was sent to this email. Ask for a new code.")
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

    db.delete(row)  # one use only
    db.commit()
    return {"message": "Email verified", "email_token": create_email_token(body.email)}


@router.post("", status_code=status.HTTP_201_CREATED)
def signup(body: SignupIn, db: Session = Depends(get_db)):
    if body.password != body.confirm_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Passwords do not match")
    if read_email_token(body.email_token) != body.email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Please verify your email again.")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists. Please sign in.")

    role = db.query(Role).filter(Role.name == body.role).first()
    if role is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Choose a role from the list")

    user = User(name=body.name, email=body.email, password_hash=hash_password(body.password), role=role)
    if body.role == rbac.ROLE_BUYER:
        # A buyer login must point at a buyer record; that's what limits a buyer
        # to their own orders and invoices.
        buyer = Buyer(name=body.name, contact_person=body.name, email=body.email)
        db.add(buyer)
        user.buyer = buyer
    db.add(user)
    db.commit()
    return {"message": "Account created. You can now sign in.", "email": user.email, "role": role.name}

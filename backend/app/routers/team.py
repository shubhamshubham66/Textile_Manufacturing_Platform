"""Owner's team: create and list managers.

- GET  /api/team/managers          -> managers, newest first, plus a suggested next ID
- POST /api/team/managers          -> create a manager with a login ID + password

Only roles allowed the "team" resource (the owner) may call these. A manager
signs in with the login ID (e.g. MGR-001) or, if given, their email.
"""

from __future__ import annotations

import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app import rbac
from app.database import get_db
from app.deps import require_resource
from app.models import Role, User
from app.security import hash_password

router = APIRouter(prefix="/api/team", tags=["team"])

ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{2,19}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
# Managers created with only a login ID still need a unique email row value;
# this internal address is never shown and can't receive mail.
STAFF_EMAIL_DOMAIN = "staff.everest.local"


class ManagerIn(BaseModel):
    name: str
    login_id: str
    password: str
    confirm_password: str
    email: str | None = None

    @field_validator("name")
    @classmethod
    def name_ok(cls, v: str) -> str:
        v = " ".join((v or "").split())
        if len(v) < 2 or len(v) > 120:
            raise ValueError("Name must be 2 to 120 characters")
        return v

    @field_validator("login_id")
    @classmethod
    def id_ok(cls, v: str) -> str:
        v = (v or "").strip().upper()
        if not ID_RE.match(v):
            raise ValueError("Login ID: 3 to 20 letters, numbers or dashes, e.g. MGR-001")
        return v

    @field_validator("password")
    @classmethod
    def password_ok(cls, v: str) -> str:
        if len(v or "") < 8 or not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("Password needs at least 8 characters, with letters and numbers")
        return v

    @field_validator("email")
    @classmethod
    def email_ok(cls, v: str | None) -> str | None:
        v = (v or "").strip().lower()
        if not v:
            return None
        if not EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address, or leave it empty")
        return v


class ManagerOut(BaseModel):
    id: int
    name: str
    login_id: str | None
    email: str | None
    is_active: bool
    created_at: datetime | None


def _out(u: User) -> ManagerOut:
    email = None if u.email.endswith("@" + STAFF_EMAIL_DOMAIN) else u.email
    return ManagerOut(id=u.id, name=u.name, login_id=u.login_id, email=email,
                      is_active=u.is_active, created_at=u.created_at)


def _next_id(db: Session) -> str:
    nums = []
    for (lid,) in db.query(User.login_id).filter(User.login_id.like("MGR-%")):
        m = re.fullmatch(r"MGR-(\d+)", lid or "")
        if m:
            nums.append(int(m.group(1)))
    return f"MGR-{(max(nums) + 1) if nums else 1:03d}"


@router.get("/managers")
def list_managers(_=Depends(require_resource("team")), db: Session = Depends(get_db)):
    rows = (
        db.query(User).join(Role).filter(Role.name == rbac.ROLE_MANAGER)
        .order_by(User.created_at.desc(), User.id.desc()).all()
    )
    return {"managers": [_out(u) for u in rows], "next_login_id": _next_id(db)}


@router.post("/managers", status_code=status.HTTP_201_CREATED, response_model=ManagerOut)
def create_manager(body: ManagerIn, _=Depends(require_resource("team")), db: Session = Depends(get_db)):
    if body.password != body.confirm_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Passwords do not match")
    if db.query(User).filter(User.login_id == body.login_id).first():
        raise HTTPException(status.HTTP_409_CONFLICT, f"Login ID {body.login_id} is already taken")
    email = body.email or f"{body.login_id.lower()}@{STAFF_EMAIL_DOMAIN}"
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "That email already has an account")
    role = db.query(Role).filter(Role.name == rbac.ROLE_MANAGER).first()
    if role is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Manager role is not set up yet; restart the server")

    user = User(name=body.name, email=email, login_id=body.login_id,
                password_hash=hash_password(body.password), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _out(user)

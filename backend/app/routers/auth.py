"""Authentication + role endpoints.

- POST /api/auth/login   -> validate credentials, return JWT + user + menu
- GET  /api/auth/me      -> current user, role and role-based menu
- POST /api/auth/logout  -> stateless; client discards the token

Role enforcement (403 for unauthorized roles) lives on the real resource
routers, e.g. /api/payments/* via require_resource("payments").
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app import rbac
from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.security import create_access_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---- Schemas ----
class LoginRequest(BaseModel):
    # Plain string, not EmailStr: EmailStr needs the extra email-validator package
    # and rejects reserved demo domains like `everest.test`, which broke every
    # demo login. A light check is enough here — the DB lookup decides.
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def email_looks_valid(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if "@" not in v or v.startswith("@") or v.endswith("@") or " " in v:
            raise ValueError("Enter a valid email address")
        return v

    @field_validator("password")
    @classmethod
    def password_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Password is required")
        return v


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    buyer_id: int | None = None


class MeOut(BaseModel):
    user: UserOut
    menu: list[dict]


class LoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    user: UserOut
    menu: list[dict]


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role.name,
        buyer_id=user.buyer_id,
    )


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    # Same message whether email or password is wrong (don't leak which).
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is disabled",
        )

    token = create_access_token(subject=user.id, extra={"role": user.role.name})
    return LoginResponse(
        token=token,
        user=_user_out(user),
        menu=rbac.menu_for(user.role.name),
    )


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    return MeOut(user=_user_out(user), menu=rbac.menu_for(user.role.name))


@router.post("/logout")
def logout(user: User = Depends(get_current_user)):
    # Stateless JWT: the client discards the token. Endpoint exists so the UI has
    # a definite action and so we could add server-side token revocation later.
    return {"message": "Logged out"}

"""Shared FastAPI auth dependencies.

- `get_current_user`  -> resolves the bearer token to a User (401 if invalid).
- `require_roles(...)` -> dependency factory; 403 unless the user has a role.
- `require_resource(r)`-> dependency factory keyed on the RBAC resource table.

Enforcement lives on the BACKEND here — hiding menus on the frontend is not the
security boundary. Forbidden access returns 403.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import rbac
from app.database import get_db
from app.models import User
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _forbidden(detail: str = "You do not have access to this resource") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if creds is None or not creds.credentials:
        raise _unauthorized()
    payload = decode_access_token(creds.credentials)
    if not payload or "sub" not in payload:
        raise _unauthorized("Invalid or expired token")

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if user is None or not user.is_active:
        raise _unauthorized("User not found or inactive")
    return user


def current_role(user: User = Depends(get_current_user)) -> str:
    return user.role.name


def require_roles(*allowed_roles: str):
    """Dependency: allow only the given roles, else 403."""

    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role.name not in allowed_roles:
            raise _forbidden(
                f"Role '{user.role.name}' may not access this endpoint"
            )
        return user

    return _dep


def require_resource(resource: str):
    """Dependency: allow only roles permitted for an RBAC resource, else 403."""

    def _dep(user: User = Depends(get_current_user)) -> User:
        if not rbac.can_access(user.role.name, resource):
            raise _forbidden(
                f"Role '{user.role.name}' may not access '{resource}'"
            )
        return user

    return _dep


def get_current_buyer(user: User = Depends(get_current_user)) -> User:
    """Dependency for buyer-portal endpoints.

    Requires the user to be a buyer AND linked to a buyer record. Returns the
    user; callers must scope every query to `user.buyer_id`. This is the single
    place that guarantees a buyer can only ever reach their own data.
    """
    if user.role.name != rbac.ROLE_BUYER:
        raise _forbidden("Only buyers may access the buyer portal")
    if user.buyer_id is None:
        raise _forbidden("This buyer login is not linked to a buyer account")
    return user

"""Startup steps that keep a live database in line with the code.

- ensure_roles: every role in rbac.ALL_ROLES has a row (a database made before
  a new role was added gets it, e.g. "manager").
- ensure_owner_account: if OWNER_EMAIL and OWNER_PASSWORD are set in the
  environment, that email is an owner login with that password. Re-running
  only updates the password when it changed, so it is safe on every start.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app import rbac
from app.config import get_settings
from app.models import Role, User
from app.security import hash_password, verify_password

log = logging.getLogger(__name__)


def ensure_roles(db: Session) -> list[str]:
    have = {r.name for r in db.query(Role).all()}
    added = [name for name in rbac.ALL_ROLES if name not in have]
    for name in added:
        db.add(Role(name=name))
    if added:
        db.commit()
        log.info("Added roles: %s", ", ".join(added))
    return added


def ensure_demo_managers(db: Session) -> list[str]:
    """Ensure the demo department-manager logins exist on ANY database.

    The seed only runs on an empty DB, so on an already-populated (e.g. live)
    database the production / sales manager demo logins would be missing and
    sign-in fails with "Invalid email/ID or password". This adds them if absent
    (idempotent) so those roles can always be demoed and the Supermanager has a
    real department manager to assign work to. Passwords are bcrypt-hashed.
    """
    demos = [
        ("production_manager", "Vikram Singh", "production@everest.test", "production123", "production"),
        ("sales_manager", "Neha Kapoor", "sales@everest.test", "sales123", "dispatch"),
    ]
    added: list[str] = []
    for role_name, name, email, password, department in demos:
        if db.query(User).filter(User.email == email).first():
            continue
        role = db.query(Role).filter(Role.name == role_name).first()
        if role is None:
            continue  # ensure_roles runs first, but be safe
        db.add(User(name=name, email=email, password_hash=hash_password(password),
                    role=role, department=department, is_active=True))
        added.append(email)
    if added:
        db.commit()
        log.info("Added demo manager logins: %s", ", ".join(added))
    return added


def ensure_owner_account(db: Session) -> str | None:
    """Create or update the owner login from settings. Returns what happened."""
    s = get_settings()
    email = (s.owner_email or "").strip().lower()
    password = s.owner_password or ""
    if not email or not password:
        return None
    owner_role = db.query(Role).filter(Role.name == rbac.ROLE_OWNER).first()
    if owner_role is None:
        return None

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        db.add(User(name=s.owner_name or "Owner", email=email,
                    password_hash=hash_password(password), role=owner_role))
        db.commit()
        log.info("Created owner account for %s", email)
        return "created"

    changed = False
    if user.role_id != owner_role.id:
        user.role = owner_role
        user.buyer_id = None
        changed = True
    if not verify_password(password, user.password_hash):
        user.password_hash = hash_password(password)
        changed = True
    if not user.is_active:
        user.is_active = True
        changed = True
    if changed:
        db.commit()
        log.info("Updated owner account for %s", email)
        return "updated"
    return "unchanged"

"""The six mill departments and which login role runs each.

Department managers are the existing staff logins; the department decides
which role (and so which screens) the account gets.
"""

from __future__ import annotations

from app import rbac

DEPARTMENTS: list[tuple[str, str]] = [
    ("purchase", "Purchase & Raw Material"),
    ("production", "Production"),
    ("qc", "Quality Control (QC)"),
    ("store", "Store / Inventory"),
    ("dispatch", "Sales & Dispatch"),
    ("accounts", "Accounts & Finance"),
]
DEPT_LABEL = dict(DEPARTMENTS)

# Department -> role that has the screens for that work.
DEPT_ROLE = {
    "purchase": rbac.ROLE_STORE_MANAGER,
    "production": rbac.ROLE_FLOOR_SUPERVISOR,
    "qc": rbac.ROLE_QUALITY_INSPECTOR,
    "store": rbac.ROLE_STORE_MANAGER,
    "dispatch": rbac.ROLE_STORE_MANAGER,
    "accounts": rbac.ROLE_ACCOUNTANT,
}

# Role -> department used when a user has none set (e.g. seeded logins).
ROLE_DEFAULT_DEPT = {
    rbac.ROLE_STORE_MANAGER: "store",
    rbac.ROLE_FLOOR_SUPERVISOR: "production",
    rbac.ROLE_QUALITY_INSPECTOR: "qc",
    rbac.ROLE_ACCOUNTANT: "accounts",
}

DEPT_MANAGER_ROLES = set(ROLE_DEFAULT_DEPT)


def dept_of(user) -> str | None:
    role = user.role.name if user.role else None
    if role not in DEPT_MANAGER_ROLES:
        return None
    return user.department or ROLE_DEFAULT_DEPT[role]

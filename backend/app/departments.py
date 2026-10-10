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

# Department -> role that MANAGES that work (gets its department instructions
# and runs its workers). Production is run by the Production manager; sales &
# dispatch by the Sales & Dispatch manager.
DEPT_ROLE = {
    "purchase": rbac.ROLE_STORE_MANAGER,
    "production": rbac.ROLE_PRODUCTION_MANAGER,
    "qc": rbac.ROLE_QUALITY_INSPECTOR,
    "store": rbac.ROLE_STORE_MANAGER,
    "dispatch": rbac.ROLE_SALES_MANAGER,
    "accounts": rbac.ROLE_ACCOUNTS_MANAGER,
}

# Role -> department used when a user has none set (e.g. seeded logins).
# The production manager is the production department's manager, so it is listed
# as the owner of the "production" default below. The store manager keeps
# "store" as its default even though it can still open the shared dispatch
# screens.
ROLE_DEFAULT_DEPT = {
    rbac.ROLE_STORE_MANAGER: "store",
    rbac.ROLE_PRODUCTION_MANAGER: "production",
    rbac.ROLE_QUALITY_INSPECTOR: "qc",
    rbac.ROLE_ACCOUNTANT: "accounts",
    rbac.ROLE_ACCOUNTS_MANAGER: "accounts",
    rbac.ROLE_SALES_MANAGER: "dispatch",
}

DEPT_MANAGER_ROLES = set(ROLE_DEFAULT_DEPT)


def dept_of(user) -> str | None:
    role = user.role.name if user.role else None
    if role not in DEPT_MANAGER_ROLES:
        return None
    return user.department or ROLE_DEFAULT_DEPT[role]

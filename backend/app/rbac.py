"""Single source of truth for roles → menus and roles → allowed resources.

Both the backend (enforcement) and the frontend (menu rendering) use this one
config. The frontend fetches the menu for the logged-in role from
`GET /api/auth/me`, so there is NO per-role code duplication anywhere.
"""

from __future__ import annotations

# Canonical role keys (match the `roles.name` values seeded in the DB).
ROLE_OWNER = "owner"
ROLE_STORE_MANAGER = "store_manager"
ROLE_FLOOR_SUPERVISOR = "floor_supervisor"
ROLE_QUALITY_INSPECTOR = "quality_inspector"
ROLE_ACCOUNTANT = "accountant"
ROLE_BUYER = "buyer"
# General manager: created by the owner from the Team page (no self-signup).
ROLE_MANAGER = "manager"

ALL_ROLES = [
    ROLE_OWNER,
    ROLE_STORE_MANAGER,
    ROLE_FLOOR_SUPERVISOR,
    ROLE_QUALITY_INSPECTOR,
    ROLE_ACCOUNTANT,
    ROLE_BUYER,
    ROLE_MANAGER,
]

# One role -> menu config. `path` is the frontend route; `resource` ties the menu
# item to a backend resource used for authorization (see RESOURCE_ACCESS below).
MENU_CONFIG: dict[str, list[dict]] = {
    ROLE_OWNER: [
        {"label": "Dashboard", "path": "/app/dashboard", "resource": "dashboard"},
        {"label": "Orders", "path": "/app/orders", "resource": "orders"},
        {"label": "Reports", "path": "/app/reports", "resource": "reports"},
        {"label": "Payments", "path": "/app/payments", "resource": "payments"},
        {"label": "Master data", "path": "/app/master", "resource": "master_data"},
        {"label": "Team", "path": "/app/team", "resource": "team"},
    ],
    ROLE_MANAGER: [
        {"label": "Home", "path": "/app/home", "resource": "manager_home"},
    ],
    ROLE_STORE_MANAGER: [
        {"label": "Yarn store", "path": "/app/yarn", "resource": "yarn"},
        {"label": "Stock", "path": "/app/stock", "resource": "stock"},
        {"label": "Purchase", "path": "/app/purchase", "resource": "purchase"},
        {"label": "Dispatch", "path": "/app/dispatch", "resource": "dispatch"},
    ],
    ROLE_FLOOR_SUPERVISOR: [
        {"label": "Production", "path": "/app/production", "resource": "production"},
        {"label": "Machines", "path": "/app/machines", "resource": "machines"},
    ],
    ROLE_QUALITY_INSPECTOR: [
        {"label": "Quality", "path": "/app/quality", "resource": "quality"},
        {"label": "Rolls", "path": "/app/rolls", "resource": "rolls"},
    ],
    ROLE_ACCOUNTANT: [
        {"label": "Payments", "path": "/app/payments", "resource": "payments"},
        {"label": "Attendance", "path": "/app/attendance", "resource": "attendance"},
        {"label": "Wages", "path": "/app/wages", "resource": "wages"},
    ],
    ROLE_BUYER: [
        {"label": "My orders", "path": "/app/my-orders", "resource": "my_orders"},
        {"label": "Invoices", "path": "/app/invoices", "resource": "invoices"},
    ],
}

# Derived: resource -> set of roles allowed to access it. Built from MENU_CONFIG
# so menus and backend permissions can never drift apart.
RESOURCE_ACCESS: dict[str, set[str]] = {}
for _role, _items in MENU_CONFIG.items():
    for _item in _items:
        RESOURCE_ACCESS.setdefault(_item["resource"], set()).add(_role)


def menu_for(role: str) -> list[dict]:
    """Return the menu items for a role (empty list if unknown)."""
    return MENU_CONFIG.get(role, [])


def roles_for_resource(resource: str) -> set[str]:
    """Return the set of roles permitted to access a resource."""
    return RESOURCE_ACCESS.get(resource, set())


def can_access(role: str, resource: str) -> bool:
    return role in RESOURCE_ACCESS.get(resource, set())

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
# Production manager: owns the production floor end-to-end — plans production,
# assigns machines/workers/shifts, tracks output/downtime, raises material
# shortage requests, hands finished batches to QC, and reports to the
# Supermanager. Cannot touch finance, stock levels or dispatch directly.
ROLE_PRODUCTION_MANAGER = "production_manager"
# Sales & Dispatch manager: receives QC-approved stock, matches it to confirmed
# buyer orders, plans dispatches, generates delivery challans, confirms
# deliveries and hands off to Accounts for payment. Cannot confirm orders,
# approve QC, or edit financial records.
ROLE_SALES_MANAGER = "sales_manager"

ALL_ROLES = [
    ROLE_OWNER,
    ROLE_STORE_MANAGER,
    ROLE_FLOOR_SUPERVISOR,
    ROLE_QUALITY_INSPECTOR,
    ROLE_ACCOUNTANT,
    ROLE_BUYER,
    ROLE_MANAGER,
    ROLE_PRODUCTION_MANAGER,
    ROLE_SALES_MANAGER,
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
    # Shown as "Supermanager": the central control panel. Orders are written
    # here (order_desk); the owner only views them (resource "orders").
    ROLE_MANAGER: [
        {"label": "Dashboard", "path": "/app/super", "resource": "super_dashboard"},
        {"label": "Order management", "path": "/app/order-desk", "resource": "order_desk"},
        {"label": "Department managers", "path": "/app/super-managers", "resource": "super_managers"},
        {"label": "Workers", "path": "/app/super-workers", "resource": "super_workers"},
        {"label": "Assign instructions", "path": "/app/super-tasks", "resource": "super_tasks"},
        {"label": "Production", "path": "/app/super-production", "resource": "super_production"},
        {"label": "Inventory", "path": "/app/super-inventory", "resource": "super_inventory"},
        {"label": "Quality control", "path": "/app/super-quality", "resource": "super_quality"},
        {"label": "Dispatch", "path": "/app/super-dispatch", "resource": "super_dispatch"},
        {"label": "Attendance", "path": "/app/super-attendance", "resource": "super_attendance"},
        {"label": "Accounts & reports", "path": "/app/super-accounts", "resource": "super_accounts"},
        {"label": "Alerts", "path": "/app/super-alerts", "resource": "super_alerts"},
        {"label": "Activity log", "path": "/app/super-activity", "resource": "super_activity"},
        {"label": "Settings", "path": "/app/super-settings", "resource": "super_settings"},
    ],
    # Production manager: the production floor control panel. Receives confirmed
    # orders/instructions from the Supermanager, plans and assigns work, tracks
    # output and downtime, requests short material, hands batches to QC and
    # reports progress. All 12 screens are its own resources (`pm_*`) so its
    # permissions are isolated from the floor-supervisor screens.
    ROLE_PRODUCTION_MANAGER: [
        {"label": "Dashboard", "path": "/app/pm-dashboard", "resource": "pm_dashboard"},
        {"label": "Production Orders", "path": "/app/pm-orders", "resource": "pm_orders"},
        {"label": "Production Planning", "path": "/app/pm-planning", "resource": "pm_planning"},
        {"label": "Production Stages", "path": "/app/pm-stages", "resource": "pm_stages"},
        {"label": "Machine Management", "path": "/app/pm-machines", "resource": "pm_machines"},
        {"label": "Worker & Task Assignment", "path": "/app/pm-workers", "resource": "pm_workers"},
        {"label": "Production Monitoring", "path": "/app/pm-monitoring", "resource": "pm_monitoring"},
        {"label": "Material Requests", "path": "/app/pm-materials", "resource": "pm_materials"},
        {"label": "QC Handover", "path": "/app/pm-qc", "resource": "pm_qc"},
        {"label": "Production Reports", "path": "/app/pm-reports", "resource": "pm_reports"},
        {"label": "Notifications", "path": "/app/pm-notifications", "resource": "pm_notifications"},
        {"label": "Activity Logs", "path": "/app/pm-activity", "resource": "pm_activity"},
    ],
    # Sales & Dispatch manager: 13-screen panel. Its own `sd_*` resources keep
    # permissions isolated from the store's `dispatch` screens.
    ROLE_SALES_MANAGER: [
        {"label": "Dashboard", "path": "/app/sd-dashboard", "resource": "sd_dashboard"},
        {"label": "Buyer Orders", "path": "/app/sd-orders", "resource": "sd_orders"},
        {"label": "Buyer Management", "path": "/app/sd-buyers", "resource": "sd_buyers"},
        {"label": "Order Status Tracking", "path": "/app/sd-tracking", "resource": "sd_tracking"},
        {"label": "QC-Approved Stock", "path": "/app/sd-stock", "resource": "sd_stock"},
        {"label": "Dispatch Planning", "path": "/app/sd-planning", "resource": "sd_planning"},
        {"label": "Create Delivery Challan", "path": "/app/sd-challan", "resource": "sd_challan"},
        {"label": "Dispatch History", "path": "/app/sd-history", "resource": "sd_history"},
        {"label": "Invoice Details", "path": "/app/sd-invoices", "resource": "sd_invoices"},
        {"label": "Delivery Confirmation", "path": "/app/sd-delivery", "resource": "sd_delivery"},
        {"label": "Notifications", "path": "/app/sd-notifications", "resource": "sd_notifications"},
        {"label": "Reports", "path": "/app/sd-reports", "resource": "sd_reports"},
        {"label": "Activity Logs", "path": "/app/sd-activity", "resource": "sd_activity"},
    ],
    # Purchase & raw material desk (+ dispatch, which the store also runs).
    ROLE_STORE_MANAGER: [
        {"label": "Dashboard", "path": "/app/purchase-dashboard", "resource": "purchase_dashboard"},
        {"label": "Suppliers", "path": "/app/suppliers", "resource": "suppliers_desk"},
        {"label": "Raw material inventory", "path": "/app/stock", "resource": "stock"},
        {"label": "Purchase requests", "path": "/app/purchase-requests", "resource": "purchase_requests"},
        {"label": "Purchase orders", "path": "/app/purchase", "resource": "purchase"},
        {"label": "Material receiving", "path": "/app/yarn", "resource": "yarn"},
        {"label": "Low-stock alerts", "path": "/app/low-stock", "resource": "low_stock"},
        {"label": "Production requirements", "path": "/app/material-requirements", "resource": "material_requirements"},
        {"label": "Reports", "path": "/app/purchase-reports", "resource": "purchase_reports"},
        {"label": "Notifications", "path": "/app/purchase-notifications", "resource": "purchase_notifications"},
        {"label": "My tasks", "path": "/app/my-tasks", "resource": "my_tasks"},
        {"label": "Dispatch", "path": "/app/dispatch", "resource": "dispatch"},
    ],
    ROLE_FLOOR_SUPERVISOR: [
        {"label": "Production", "path": "/app/production", "resource": "production"},
        {"label": "Machines", "path": "/app/machines", "resource": "machines"},
        {"label": "My tasks", "path": "/app/my-tasks", "resource": "my_tasks"},
    ],
    ROLE_QUALITY_INSPECTOR: [
        {"label": "Quality", "path": "/app/quality", "resource": "quality"},
        {"label": "Rolls", "path": "/app/rolls", "resource": "rolls"},
        {"label": "My tasks", "path": "/app/my-tasks", "resource": "my_tasks"},
    ],
    ROLE_ACCOUNTANT: [
        {"label": "Payments", "path": "/app/payments", "resource": "payments"},
        {"label": "Attendance", "path": "/app/attendance", "resource": "attendance"},
        {"label": "Wages", "path": "/app/wages", "resource": "wages"},
        {"label": "My tasks", "path": "/app/my-tasks", "resource": "my_tasks"},
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

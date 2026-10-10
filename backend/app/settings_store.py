"""Small key/value settings kept in the app_settings table (JSON values)."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models import AppSetting

ALERT_KINDS = [
    ("new_orders", "New buyer orders to review"),
    ("low_stock", "Low raw-material stock"),
    ("delayed", "Delayed production"),
    ("breakdown", "Machine breakdowns"),
    ("qc_pending", "Pending quality inspections"),
    ("dispatch", "Dispatch problems"),
    ("attendance", "Attendance exceptions"),
    ("overdue_tasks", "Overdue department tasks"),
    ("purchase_approvals", "Purchase requests to approve"),
]

DEFAULTS = {
    # Woven metres one running weaving machine makes in a day (capacity check).
    "capacity_m_per_machine_day": 400,
    # Purchase requests up to this many kg are approved automatically
    # (0 = every request needs Supermanager approval).
    "purchase_auto_approve_kg": 0,
    # Alert categories shown on the Supermanager dashboard and Alerts page.
    "alerts": {k: True for k, _ in ALERT_KINDS},
}


def get_setting(db: Session, key: str):
    row = db.get(AppSetting, key)
    if row is None:
        return DEFAULTS.get(key)
    try:
        val = json.loads(row.value)
    except ValueError:
        return DEFAULTS.get(key)
    if isinstance(DEFAULTS.get(key), dict) and isinstance(val, dict):
        return {**DEFAULTS[key], **val}
    return val


def set_setting(db: Session, key: str, value) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=json.dumps(value)))
    else:
        row.value = json.dumps(value)

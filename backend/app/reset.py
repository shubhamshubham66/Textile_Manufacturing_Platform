"""One-time data reset, driven by the RESET_DATA env flag (see config.py).

  RESET_DATA=empty  -> delete all BUSINESS data; keep roles and the owner login
                       created from OWNER_EMAIL / OWNER_PASSWORD. The result is a
                       clean mill with no orders/payments/etc., ready for judges
                       to enter real data live.
  RESET_DATA=demo   -> same wipe, then reload the clean October 2026 demo seed.

Why this exists: `seed_if_empty` only runs on a totally empty database, so a
Render database that already holds the OLD demo seed + test junk (e.g. a supplier
payment of ₹20,13,22,110 driving the dashboard to a −₹20 crore loss) never gets
the clean data. This flag is the deliberate, logged way to fix that.

Safety:
  - Runs ONLY when RESET_DATA is exactly "empty" or "demo"; any other value is a
    no-op (logged as ignored).
  - It is destructive by design, so it must be set on purpose and then removed.
  - Roles are preserved; the env owner is re-ensured by bootstrap right after.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app import models as m

log = logging.getLogger(__name__)

# Delete order: children before parents so foreign keys never block a delete.
# Everything the business creates is here; `roles` is deliberately NOT included.
_WIPE_ORDER = [
    # Supermanager / purchase / audit tables (no foreign keys into them).
    m.TaskUpdate,
    m.Task,
    m.Notification,
    m.ActivityLog,
    m.StockMovement,
    m.PurchaseRequest,
    m.Payment,
    m.DispatchItem,
    m.Dispatch,
    m.Invoice,
    m.QualityInspection,
    m.Roll,
    m.ProductionLog,
    m.MachineStatusLog,
    m.Attendance,
    m.Wage,
    m.YarnReceipt,
    m.OrderItem,
    m.PurchaseOrder,
    m.Order,
    m.Employee,
    m.Machine,
    m.YarnStock,
    m.Supplier,
    m.EmailOtp,
    m.User,
    m.Buyer,
]


def wipe_business_data(db: Session) -> dict[str, int]:
    """Delete all business rows (keeps `roles`). Returns {table: rows_deleted}."""
    deleted: dict[str, int] = {}
    for model in _WIPE_ORDER:
        n = db.query(model).delete(synchronize_session=False)
        if n:
            deleted[model.__tablename__] = int(n)
    db.commit()
    return deleted


def run_reset_if_requested() -> None:
    """Act on RESET_DATA. No-op unless it is exactly 'empty' or 'demo'."""
    from app.config import get_settings
    from app.database import SessionLocal

    mode = (get_settings().reset_data or "").strip().lower()
    if not mode:
        return
    if mode not in ("empty", "demo"):
        log.warning("RESET_DATA=%r ignored (expected 'empty' or 'demo')", mode)
        return

    db = SessionLocal()
    try:
        deleted = wipe_business_data(db)
    finally:
        db.close()
    total = sum(deleted.values())
    log.warning(
        "RESET_DATA=%s: wiped %d business rows across %d tables (%s). "
        "Roles kept; owner account re-ensured from env. "
        "REMOVE RESET_DATA now so the next restart does not wipe again.",
        mode, total, len(deleted),
        ", ".join(f"{k}={v}" for k, v in deleted.items()) or "nothing to delete",
    )

    if mode == "demo":
        from app.seed import seed

        log.warning("RESET_DATA=demo: reloading the clean October 2026 seed")
        seed()

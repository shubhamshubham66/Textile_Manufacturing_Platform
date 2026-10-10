"""Production helpers: order progress and idle-machine loss (our USP).

Kept separate from the router so the idle-loss math is easy to read and verify
against a hand calculation.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import MachineStatusLog, Order, ProductionLog

# Statuses that count as lost (non-productive) machine time.
LOSS_STATUSES = ("idle", "breakdown")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime) -> datetime:
    """Treat naive timestamps (SQLite) as UTC so subtraction is safe."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def log_duration_hours(log: MachineStatusLog, until: datetime | None = None) -> float:
    """Duration of a status-log window in hours.

    Uses end_time when the window is closed, otherwise `until` (default: now) for
    an open window.
    """
    start = _as_aware(log.start_time)
    end = _as_aware(log.end_time) if log.end_time else (until or _now())
    seconds = (end - start).total_seconds()
    return max(0.0, seconds / 3600.0)


def log_hours_in_window(
    log: MachineStatusLog,
    window: tuple[datetime, datetime] | None,
    until: datetime | None = None,
) -> float:
    """Hours of a status-log window that fall inside `window` (start, end).

    With window=None this is the same as log_duration_hours. An open window
    runs up to `until` (default: now), so time in the future is never counted.
    """
    if window is None:
        return log_duration_hours(log, until=until)
    now = until or _now()
    start = _as_aware(log.start_time)
    end = _as_aware(log.end_time) if log.end_time else now
    lo = max(start, _as_aware(window[0]))
    hi = min(end, _as_aware(window[1]), now)
    return max(0.0, (hi - lo).total_seconds() / 3600.0)


def order_progress_percent(db: Session, order: Order) -> float:
    """Percent complete = produced metres / ordered metres (capped at 100)."""
    produced = (
        db.query(func.coalesce(func.sum(ProductionLog.output_meters), 0))
        .filter(ProductionLog.order_id == order.id)
        .scalar()
        or 0
    )
    ordered = float(order.quantity_meters) or 0
    if ordered <= 0:
        return 0.0
    return round(min(100.0, float(produced) / ordered * 100.0), 1)


# Once an order reaches quality or later its production is finished, so show
# 100% instead of a figure computed from (possibly incomplete) production logs.
ORDER_DONE_PRODUCING = {"in_quality", "ready_to_ship", "dispatched", "closed"}


def order_display_progress(db: Session, order: Order) -> float:
    if order.status in ORDER_DONE_PRODUCING:
        return 100.0
    return order_progress_percent(db, order)


def idle_loss_for_machine(
    db: Session,
    machine_id: int,
    hourly_cost: float,
    now: datetime | None = None,
    window: tuple[datetime, datetime] | None = None,
) -> dict:
    """Idle+breakdown hours and rupee loss for a single machine.

    loss = Σ(window hours) × hourly_cost over idle/breakdown logs. With a
    `window` (owner month reports) only the hours inside it count; without one
    (floor screens) every log counts, as before.
    """
    now = now or _now()
    logs = (
        db.query(MachineStatusLog)
        .filter(
            MachineStatusLog.machine_id == machine_id,
            MachineStatusLog.status.in_(LOSS_STATUSES),
        )
        .all()
    )
    idle_hours = 0.0
    breakdown_hours = 0.0
    for log in logs:
        hrs = log_hours_in_window(log, window, until=now)
        if log.status == "idle":
            idle_hours += hrs
        else:
            breakdown_hours += hrs
    total_hours = idle_hours + breakdown_hours
    return {
        "idle_hours": round(idle_hours, 2),
        "breakdown_hours": round(breakdown_hours, 2),
        "lost_hours": round(total_hours, 2),
        "loss_rupees": round(total_hours * float(hourly_cost), 2),
    }

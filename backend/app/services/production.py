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
    db: Session, machine_id: int, hourly_cost: float, now: datetime | None = None
) -> dict:
    """Idle+breakdown hours and rupee loss for a single machine.

    loss = Σ(window hours) × hourly_cost over idle/breakdown logs.
    """
    now = now or _now()
    # All status logs (running + idle + breakdown) so we can report running hours.
    all_logs = (
        db.query(MachineStatusLog)
        .filter(MachineStatusLog.machine_id == machine_id)
        .all()
    )
    idle_hours = 0.0
    breakdown_hours = 0.0
    running_hours = 0.0
    reason_hours: dict[str, float] = {}
    for log in all_logs:
        hrs = log_duration_hours(log, until=now)
        if log.status == "idle":
            idle_hours += hrs
            key = log.reason or "Unspecified"
            reason_hours[key] = reason_hours.get(key, 0.0) + hrs
        elif log.status == "breakdown":
            breakdown_hours += hrs
            key = log.reason or "Unspecified"
            reason_hours[key] = reason_hours.get(key, 0.0) + hrs
        elif log.status == "running":
            running_hours += hrs
    total_hours = idle_hours + breakdown_hours
    top_reason = (
        max(reason_hours.items(), key=lambda kv: kv[1])[0] if reason_hours else "—"
    )
    return {
        "idle_hours": round(idle_hours, 2),
        "breakdown_hours": round(breakdown_hours, 2),
        "running_hours": round(running_hours, 2),
        "lost_hours": round(total_hours, 2),
        "loss_rupees": round(total_hours * float(hourly_cost), 2),
        "top_reason": top_reason,
    }


def idle_loss_by_reason(db: Session, now: datetime | None = None) -> list[dict]:
    """Total idle/breakdown rupee loss grouped by reason, across all machines.

    Used by the dashboard idle-loss-by-reason chart.
    """
    from app.models import Machine

    now = now or _now()
    machines = {mc.id: float(mc.hourly_cost or 0) for mc in db.query(Machine).all()}
    logs = (
        db.query(MachineStatusLog)
        .filter(MachineStatusLog.status.in_(LOSS_STATUSES))
        .all()
    )
    by_reason: dict[str, float] = {}
    for log in logs:
        hrs = log_duration_hours(log, until=now)
        rupees = hrs * machines.get(log.machine_id, 0.0)
        key = log.reason or "Unspecified"
        by_reason[key] = by_reason.get(key, 0.0) + rupees
    return sorted(
        [{"reason": r, "rupees": round(v, 2)} for r, v in by_reason.items()],
        key=lambda x: x["rupees"], reverse=True,
    )

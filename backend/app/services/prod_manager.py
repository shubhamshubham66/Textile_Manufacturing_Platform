"""Read-only aggregations for the Production Manager screens.

Every figure is computed from the live tables (orders, machines, production
logs, status logs, rolls, inspections, tasks, employees, purchase requests,
yarn stock) — nothing is hard-coded. The Production Manager plans and runs the
floor; money, stock levels and dispatch are owned by other roles, so this
service never reads or writes them beyond what the floor needs to see.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    ActivityLog,
    Employee,
    Machine,
    MachineStatusLog,
    Notification,
    Order,
    ProductionLog,
    PurchaseRequest,
    QualityInspection,
    Roll,
    Task,
    User,
    YarnStock,
)
from app.services.production import (
    idle_loss_for_machine,
    order_display_progress,
    order_progress_percent,
)
from app.services.tasks import is_overdue, shown_status

# Orders the production manager actively works on.
PRODUCTION_ORDERS = ("confirmed", "in_production", "in_quality")
STAGES = ("spinning", "weaving", "dyeing")
LOSS_STATUSES = ("idle", "breakdown")
# Yarn weight per metre of fabric (same assumption as orders/yarn modules).
KG_PER_METER = 0.2


def _f(v) -> float:
    return round(float(v or 0), 2)


def _iso(v) -> str | None:
    return v.isoformat() if v else None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _produced_meters(db: Session, order_id: int) -> float:
    return _f(
        db.query(func.coalesce(func.sum(ProductionLog.output_meters), 0))
        .filter(ProductionLog.order_id == order_id)
        .scalar()
    )


def stage_metres(db: Session, order_id: int) -> dict:
    rows = (
        db.query(ProductionLog.stage, func.coalesce(func.sum(ProductionLog.output_meters), 0))
        .filter(ProductionLog.order_id == order_id)
        .group_by(ProductionLog.stage)
        .all()
    )
    got = {s: _f(v) for s, v in rows}
    return {s: got.get(s, 0.0) for s in STAGES}


def order_row(db: Session, o: Order) -> dict:
    today = date.today()
    progress = order_display_progress(db, o)
    produced = _produced_meters(db, o.id)
    days_left = (o.deadline - today).days if o.deadline else None
    late = bool(o.deadline and o.deadline < today and o.status in PRODUCTION_ORDERS)
    at_risk = bool(
        not late
        and o.deadline
        and days_left is not None
        and days_left <= 3
        and progress < 80
        and o.status in ("confirmed", "in_production")
    )
    return {
        "id": o.id,
        "order_no": o.order_no,
        "buyer": o.buyer.name if o.buyer else "",
        "fabric_type": o.fabric_type,
        "colour": o.colour,
        "quantity_meters": _f(o.quantity_meters),
        "produced_meters": produced,
        "deadline": _iso(o.deadline),
        "days_left": days_left,
        "status": o.status,
        "progress": progress,
        "stages": stage_metres(db, o.id),
        "late": late,
        "at_risk": at_risk,
        "delay": "late" if late else ("at_risk" if at_risk else None),
        "review_note": o.review_note,
        "created_at": _iso(o.created_at),
    }


# --------------------------------------------------------------------------- #
# Machines
# --------------------------------------------------------------------------- #
def machine_row(db: Session, m: Machine) -> dict:
    cur = db.get(Order, m.current_order_id) if m.current_order_id else None
    made = _produced_meters_for_machine(db, m.id)
    last_break = (
        db.query(MachineStatusLog)
        .filter(MachineStatusLog.machine_id == m.id, MachineStatusLog.status == "breakdown")
        .order_by(MachineStatusLog.id.desc())
        .first()
    )
    loss = idle_loss_for_machine(db, m.id, float(m.hourly_cost or 0), now=_now())
    progress = order_progress_percent(db, cur) if cur else 0.0
    return {
        "id": m.id,
        "name": m.name,
        "type": m.type,
        # "breakdown" is shown as "maintenance" on the manager screens.
        "status": "maintenance" if m.current_status == "breakdown" else m.current_status,
        "raw_status": m.current_status,
        "since": _iso(m.status_since),
        "order_id": m.current_order_id,
        "order_no": cur.order_no if cur else None,
        "stage": m.current_stage,
        "progress": progress,
        "hourly_cost": float(m.hourly_cost or 0),
        "total_meters": made,
        "lost_hours": loss["lost_hours"],
        "loss_rupees": loss["loss_rupees"],
        "last_breakdown_reason": last_break.reason if last_break else None,
    }


def _produced_meters_for_machine(db: Session, machine_id: int) -> float:
    return _f(
        db.query(func.coalesce(func.sum(ProductionLog.output_meters), 0))
        .filter(ProductionLog.machine_id == machine_id)
        .scalar()
    )


# --------------------------------------------------------------------------- #
# Material availability (yarn vs confirmed order needs)
# --------------------------------------------------------------------------- #
def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def material_shortages(db: Session) -> list[dict]:
    """Confirmed/in-production orders whose colour of yarn is short in the store,
    net of what every earlier order has already claimed. Mirrors the store's
    requirement logic but keyed on colour (the field production works with)."""
    stock_by_colour: dict[str, float] = {}
    for s in db.query(YarnStock).all():
        stock_by_colour[_norm(s.colour)] = stock_by_colour.get(_norm(s.colour), 0.0) + float(s.quantity_kg or 0)
    left = dict(stock_by_colour)
    orders = (
        db.query(Order)
        .filter(Order.status.in_(PRODUCTION_ORDERS))
        .order_by(Order.deadline.is_(None), Order.deadline, Order.id)
        .all()
    )
    out = []
    for o in orders:
        remaining_m = max(0.0, float(o.quantity_meters or 0) - _produced_meters(db, o.id))
        need = round(remaining_m * KG_PER_METER, 2)
        if need <= 0:
            continue
        have = left.get(_norm(o.colour), 0.0)
        covered = min(have, need)
        left[_norm(o.colour)] = have - covered
        short = round(need - covered, 2)
        if short <= 0:
            continue
        # Has a request already been raised for this order?
        existing = (
            db.query(PurchaseRequest)
            .filter(
                PurchaseRequest.order_id == o.id,
                PurchaseRequest.status.in_(("pending", "approved", "ordered")),
            )
            .order_by(PurchaseRequest.id.desc())
            .first()
        )
        days = (o.deadline - date.today()).days if o.deadline else None
        out.append(
            {
                "order_id": o.id,
                "order_no": o.order_no,
                "buyer": o.buyer.name if o.buyer else "",
                "colour": o.colour,
                "fabric_type": o.fabric_type,
                "need_kg": need,
                "available_kg": round(covered, 2),
                "short_kg": short,
                "deadline": _iso(o.deadline),
                "days_left": days,
                "urgent": bool(days is not None and days <= 7),
                "request": (
                    {"pr_no": existing.pr_no, "status": existing.status, "quantity_kg": _f(existing.quantity_kg)}
                    if existing
                    else None
                ),
            }
        )
    return out


# --------------------------------------------------------------------------- #
# QC handover: batches made but not yet given to QC / inspected
# --------------------------------------------------------------------------- #
def qc_pending(db: Session) -> list[dict]:
    """Rolls submitted to QC (status 'pending') that QC has not yet inspected,
    grouped by order. These are the manager's handovers awaiting a result."""
    rolls = db.query(Roll).filter(Roll.status == "pending").order_by(Roll.id).all()
    by_order: dict[int, dict] = {}
    for r in rolls:
        o = db.get(Order, r.order_id)
        key = r.order_id
        row = by_order.setdefault(
            key,
            {
                "order_id": r.order_id,
                "order_no": o.order_no if o else None,
                "fabric": f"{o.fabric_type} {o.colour}" if o else "",
                "rolls": 0,
                "meters": 0.0,
            },
        )
        row["rolls"] += 1
        row["meters"] = round(row["meters"] + float(r.length_meters or 0), 2)
    return list(by_order.values())


def rejected_rolls(db: Session) -> list[dict]:
    """Rolls QC marked rework/reject — the manager assigns rework for these."""
    out = []
    for r in db.query(Roll).filter(Roll.status.in_(("rework", "reject"))).order_by(Roll.id.desc()).all():
        o = db.get(Order, r.order_id)
        mch = db.get(Machine, r.machine_id)
        insp = (
            db.query(QualityInspection)
            .filter(QualityInspection.roll_id == r.id)
            .order_by(QualityInspection.id.desc())
            .first()
        )
        out.append(
            {
                "roll_id": r.id,
                "roll_no": r.roll_no,
                "order_no": o.order_no if o else None,
                "machine": mch.name if mch else "",
                "length_meters": _f(r.length_meters),
                "result": r.status,
                "defect": insp.defect_type if insp else None,
                "notes": insp.notes if insp else None,
                "inspected_at": _iso(insp.inspected_at) if insp else None,
            }
        )
    return out


# --------------------------------------------------------------------------- #
# Tasks (worker assignments) for the production department
# --------------------------------------------------------------------------- #
def task_row(db: Session, t: Task) -> dict:
    order = db.get(Order, t.order_id) if t.order_id else None
    worker = db.get(Employee, t.worker_employee_id) if t.worker_employee_id else None
    return {
        "id": t.id,
        "title": t.title,
        "details": t.details,
        "order_id": t.order_id,
        "order_no": order.order_no if order else None,
        "worker": {"id": worker.id, "name": worker.name} if worker else None,
        "priority": t.priority,
        "deadline": _iso(t.deadline),
        "status": t.status,
        "shown_status": shown_status(t),
        "auto": bool(t.auto),
        "created_at": _iso(t.created_at),
        "updated_at": _iso(t.updated_at),
    }


# --------------------------------------------------------------------------- #
# Dashboard overview (the 7 cards + supporting lists)
# --------------------------------------------------------------------------- #
def dashboard(db: Session) -> dict:
    today = date.today()
    counts = dict(db.query(Order.status, func.count(Order.id)).group_by(Order.status).all())

    active_orders = (
        db.query(Order)
        .filter(Order.status.in_(PRODUCTION_ORDERS))
        .order_by(Order.deadline.is_(None), Order.deadline, Order.id)
        .all()
    )
    active_rows = [order_row(db, o) for o in active_orders]
    delayed = [r for r in active_rows if r["late"]]

    # Today's output across all production logs vs a simple target: the sum of
    # remaining metres on in-production orders spread over the days left, capped
    # so the target is always a positive, believable number.
    today_actual = _f(
        db.query(func.coalesce(func.sum(ProductionLog.output_meters), 0))
        .filter(ProductionLog.log_date == today)
        .scalar()
    )
    today_target = 0.0
    for o in active_orders:
        if o.status not in ("confirmed", "in_production"):
            continue
        remaining = max(0.0, float(o.quantity_meters or 0) - _produced_meters(db, o.id))
        days = max(1, (o.deadline - today).days) if o.deadline and o.deadline > today else 1
        today_target += remaining / days
    today_target = round(today_target, 0)

    machines = [machine_row(db, m) for m in db.query(Machine).order_by(Machine.type, Machine.name).all()]
    machine_counts = {s: sum(1 for m in machines if m["status"] == s) for s in ("running", "idle", "maintenance")}

    # Worker tasks for the production department.
    prod_tasks = (
        db.query(Task)
        .filter(Task.department == "production")
        .order_by(Task.id.desc())
        .all()
    )
    open_tasks = [t for t in prod_tasks if t.status != "completed"]

    shortages = material_shortages(db)
    qc_batches = qc_pending(db)
    qc_rolls_waiting = sum(b["rolls"] for b in qc_batches)
    rejects = rejected_rolls(db)

    cards = {
        "active_orders": len(active_rows),
        "today_target": today_target,
        "today_actual": today_actual,
        "today_percent": round(today_actual / today_target * 100) if today_target else 0,
        "machines_running": machine_counts["running"],
        "machines_idle": machine_counts["idle"],
        "machines_down": machine_counts["maintenance"],
        "machine_total": len(machines),
        "worker_tasks_open": len(open_tasks),
        "worker_tasks_overdue": sum(1 for t in open_tasks if is_overdue(t)),
        "material_shortages": len(shortages),
        "delayed_orders": len(delayed),
        "qc_pending_batches": len(qc_batches),
        "qc_pending_rolls": qc_rolls_waiting,
        "rework_rejects": len(rejects),
    }

    acts = (
        db.query(ActivityLog)
        .filter(ActivityLog.category.in_(("production", "task", "qc", "order", "worker", "stock")))
        .order_by(ActivityLog.id.desc())
        .limit(10)
        .all()
    )

    return {
        "cards": cards,
        "active_orders": active_rows[:8],
        "delayed_orders": delayed,
        "machines": machines,
        "worker_tasks": [task_row(db, t) for t in open_tasks[:6]],
        "material_shortages": shortages[:6],
        "qc_pending": qc_batches,
        "rework_rejects": rejects[:6],
        "today": {"target": today_target, "actual": today_actual},
        "activity": [activity_row(a) for a in acts],
        "order_pipeline": [
            {"status": s, "count": counts.get(s, 0)}
            for s in ("confirmed", "in_production", "in_quality", "ready_to_ship", "dispatched")
            if counts.get(s, 0)
        ],
    }


def activity_row(a: ActivityLog) -> dict:
    return {
        "id": a.id,
        "at": _iso(a.at),
        "user": a.user_name or "System",
        "role": a.user_role,
        "category": a.category,
        "action": a.action,
        "details": a.details,
    }

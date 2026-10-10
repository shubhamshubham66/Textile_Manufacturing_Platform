"""Read-only aggregations for the Supermanager screens.

Every figure is computed from the live tables; nothing is hard-coded.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.departments import DEPARTMENTS, DEPT_LABEL, DEPT_MANAGER_ROLES, dept_of
from app.models import (
    ActivityLog,
    Attendance,
    Dispatch,
    DispatchItem,
    Employee,
    Invoice,
    Machine,
    Order,
    Payment,
    ProductionLog,
    PurchaseOrder,
    QualityInspection,
    Role,
    Roll,
    Task,
    User,
    YarnReceipt,
    YarnStock,
)
from app.services.production import order_display_progress
from app.services.tasks import is_overdue, shown_status
from app.settings_store import ALERT_KINDS, get_setting

ACTIVE_ORDER = ("confirmed", "in_production", "in_quality", "ready_to_ship")
PIPELINE = ["pending_review", "draft", "clarification", "confirmed", "in_production",
            "in_quality", "ready_to_ship", "dispatched", "closed", "rejected", "cancelled"]
STAGES = ("spinning", "weaving", "dyeing")


def _f(v) -> float:
    return round(float(v or 0), 2)


def _d(v) -> date | None:
    if v is None:
        return None
    return v.date() if isinstance(v, datetime) else v


def month_window(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    start = today.replace(day=1)
    nxt = (start + timedelta(days=32)).replace(day=1)
    return start, nxt - timedelta(days=1)


# --------------------------------------------------------------------------- #
# People
# --------------------------------------------------------------------------- #
def dept_managers(db: Session) -> list[User]:
    return (db.query(User).join(Role).filter(Role.name.in_(DEPT_MANAGER_ROLES))
            .order_by(User.name).all())


def user_brief(u: User | None) -> dict | None:
    if u is None:
        return None
    return {"id": u.id, "name": u.name, "department": dept_of(u)}


def present_today(db: Session, day: date | None = None) -> int:
    day = day or date.today()
    return (db.query(func.count(Attendance.id))
            .filter(Attendance.work_date == day, Attendance.status.in_(("present", "half_day")))
            .scalar() or 0)


# --------------------------------------------------------------------------- #
# Department performance (one dict per department, for a date window)
# --------------------------------------------------------------------------- #
def department_performance(db: Session, start: date, end: date) -> list[dict]:
    end_dt = datetime.combine(end, datetime.max.time())
    start_dt = datetime.combine(start, datetime.min.time())
    tasks = db.query(Task).all()
    out = []
    for key, label in DEPARTMENTS:
        mine = [t for t in tasks if t.department == key]
        open_t = [t for t in mine if t.status != "completed"]
        metrics: list[tuple[str, str]] = []
        if key == "purchase":
            pos = db.query(PurchaseOrder).filter(PurchaseOrder.created_at.between(start_dt, end_dt)).all()
            kg_in = db.query(func.coalesce(func.sum(YarnReceipt.quantity_kg), 0)).filter(
                YarnReceipt.received_at.between(start_dt, end_dt)).scalar()
            metrics = [("Purchase orders", str(len(pos))),
                       ("Yarn received", f"{_f(kg_in):,.0f} kg")]
        elif key == "production":
            m = db.query(func.coalesce(func.sum(ProductionLog.output_meters), 0)).filter(
                ProductionLog.log_date.between(start, end)).scalar()
            broken = db.query(Machine).filter(Machine.current_status == "breakdown").count()
            metrics = [("Metres produced", f"{_f(m):,.0f} m"), ("Machines down now", str(broken))]
        elif key == "qc":
            res = dict(db.query(QualityInspection.result, func.count(QualityInspection.id))
                       .filter(QualityInspection.inspected_at.between(start_dt, end_dt))
                       .group_by(QualityInspection.result).all())
            done = sum(res.values())
            rate = round(res.get("pass", 0) / done * 100) if done else 0
            metrics = [("Rolls inspected", str(done)), ("Pass rate", f"{rate}%")]
        elif key == "store":
            stocks = db.query(YarnStock).all()
            low = sum(1 for s in stocks if float(s.quantity_kg or 0) <= float(s.reorder_level_kg or 0))
            kg = sum(float(s.quantity_kg or 0) for s in stocks)
            metrics = [("Yarn in stock", f"{kg:,.0f} kg"), ("Low-stock lines", str(low))]
        elif key == "dispatch":
            ds = db.query(Dispatch).filter(Dispatch.dispatched_at.between(start_dt, end_dt)).all()
            metrics = [("Dispatches", str(len(ds))),
                       ("Metres shipped", f"{sum(float(d.total_meters or 0) for d in ds):,.0f} m")]
        elif key == "accounts":
            pays = db.query(Payment).filter(Payment.voided_at.is_(None),
                                            Payment.paid_at.between(start_dt, end_dt)).all()
            inn = sum(float(p.amount) for p in pays if p.direction == "incoming")
            metrics = [("Payments recorded", str(len(pays))), ("Received", f"₹{inn:,.0f}")]
        mgrs = [u for u in dept_managers(db) if dept_of(u) == key and u.is_active]
        out.append({
            "department": key, "label": label,
            "managers": [u.name for u in mgrs],
            "metrics": [{"label": a, "value": b} for a, b in metrics],
            "tasks_open": len(open_t),
            "tasks_overdue": sum(1 for t in open_t if is_overdue(t)),
            "tasks_done": len(mine) - len(open_t),
        })
    return out


# --------------------------------------------------------------------------- #
# Orders
# --------------------------------------------------------------------------- #
def order_row(db: Session, o: Order) -> dict:
    return {
        "id": o.id, "order_no": o.order_no,
        "buyer": o.buyer.name if o.buyer else "",
        "fabric_type": o.fabric_type, "colour": o.colour,
        "quantity_meters": _f(o.quantity_meters), "unit_price": _f(o.unit_price),
        "deadline": o.deadline.isoformat() if o.deadline else None,
        "status": o.status, "progress": order_display_progress(db, o),
        "late": bool(o.deadline and o.deadline < date.today() and o.status in ACTIVE_ORDER),
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


def stage_metres(db: Session, order_id: int) -> dict:
    rows = (db.query(ProductionLog.stage, func.coalesce(func.sum(ProductionLog.output_meters), 0))
            .filter(ProductionLog.order_id == order_id).group_by(ProductionLog.stage).all())
    got = {s: _f(v) for s, v in rows}
    return {s: got.get(s, 0.0) for s in STAGES}


# --------------------------------------------------------------------------- #
# Inventory, quality and dispatch checks
# --------------------------------------------------------------------------- #
def low_stock(db: Session) -> list[YarnStock]:
    return [s for s in db.query(YarnStock).order_by(YarnStock.yarn_type).all()
            if float(s.quantity_kg or 0) <= float(s.reorder_level_kg or 0)]


def inventory_exceptions(db: Session) -> list[dict]:
    out = []
    for s in db.query(YarnStock).all():
        if float(s.quantity_kg or 0) < 0:
            out.append({"kind": "negative_stock", "detail": f"{s.yarn_type} {s.colour} shows {_f(s.quantity_kg)} kg (below zero)."})
    for po in db.query(PurchaseOrder).filter(PurchaseOrder.status == "received").all():
        got = db.query(func.coalesce(func.sum(YarnReceipt.quantity_kg), 0)).filter(
            YarnReceipt.purchase_order_id == po.id).scalar()
        if _f(got) == 0:
            out.append({"kind": "po_without_receipt", "detail": f"{po.po_no} is marked received but no yarn receipt is linked to it."})
        elif abs(_f(got) - _f(po.quantity_kg)) > 0.5:
            out.append({"kind": "receipt_mismatch", "detail": f"{po.po_no}: ordered {_f(po.quantity_kg):,.0f} kg, received {_f(got):,.0f} kg."})
    for r in db.query(Roll).filter(Roll.status == "dispatched").all():
        insp = db.query(QualityInspection).filter(QualityInspection.roll_id == r.id).first()
        if insp is not None and insp.result != "pass":
            out.append({"kind": "unapproved_dispatched", "detail": f"Roll {r.roll_no} was dispatched but its QC result is {insp.result}."})
    return out


def dispatch_exceptions(db: Session) -> list[dict]:
    out = []
    for d in db.query(Dispatch).all():
        items = db.query(DispatchItem).filter(DispatchItem.dispatch_id == d.id).all()
        order = db.get(Order, d.order_id)
        item_m = sum(float(i.length_meters or 0) for i in items)
        if items and abs(item_m - float(d.total_meters or 0)) > 0.5:
            out.append({"kind": "dispatch_total", "dispatch_no": d.dispatch_no,
                        "detail": f"{d.dispatch_no}: rolls add up to {item_m:,.0f} m but the dispatch says {_f(d.total_meters):,.0f} m."})
        if items and len(items) != int(d.total_rolls or 0):
            out.append({"kind": "dispatch_rolls", "dispatch_no": d.dispatch_no,
                        "detail": f"{d.dispatch_no}: {len(items)} rolls listed but the dispatch says {d.total_rolls}."})
        if order and d.buyer_id != order.buyer_id:
            out.append({"kind": "buyer_mismatch", "dispatch_no": d.dispatch_no,
                        "detail": f"{d.dispatch_no}: buyer differs from the buyer on {order.order_no}."})
        for i in items:
            insp = db.query(QualityInspection).filter(QualityInspection.roll_id == i.roll_id).first()
            if insp is not None and insp.result != "pass":
                roll = db.get(Roll, i.roll_id)
                out.append({"kind": "unapproved_roll", "dispatch_no": d.dispatch_no,
                            "detail": f"{d.dispatch_no}: roll {roll.roll_no if roll else i.roll_id} has QC result {insp.result}."})
        inv = db.query(Invoice).filter(Invoice.dispatch_id == d.id).first()
        if inv and order:
            expected = round(item_m * float(order.unit_price or 0), 2)
            if expected and abs(expected - float(inv.subtotal or 0)) > 1:
                out.append({"kind": "invoice_mismatch", "dispatch_no": d.dispatch_no,
                            "detail": f"{inv.invoice_no}: subtotal ₹{_f(inv.subtotal):,.2f} but {item_m:,.0f} m × ₹{_f(order.unit_price)} = ₹{expected:,.2f}."})
    for o in db.query(Order).all():
        sent = (db.query(func.coalesce(func.sum(Dispatch.total_meters), 0))
                .filter(Dispatch.order_id == o.id).scalar())
        n = db.query(Dispatch).filter(Dispatch.order_id == o.id).count()
        if n > 1 and _f(sent) > float(o.quantity_meters) * 1.05:
            out.append({"kind": "duplicate_dispatch", "dispatch_no": None,
                        "detail": f"{o.order_no}: {n} dispatches ship {_f(sent):,.0f} m against {_f(o.quantity_meters):,.0f} m ordered — possible duplicate."})
    return out


# --------------------------------------------------------------------------- #
# Alerts
# --------------------------------------------------------------------------- #
def alerts(db: Session, respect_settings: bool = True) -> list[dict]:
    prefs = get_setting(db, "alerts") if respect_settings else {k: True for k, _ in ALERT_KINDS}
    today = date.today()
    out: list[dict] = []

    def add(kind, severity, title, detail, page):
        if prefs.get(kind, True):
            out.append({"kind": kind, "severity": severity, "title": title, "detail": detail, "page": page})

    for o in db.query(Order).filter(Order.status == "pending_review").order_by(Order.id).all():
        add("new_orders", "info", f"New order {o.order_no} to review",
            f"{o.buyer.name if o.buyer else ''} · {o.fabric_type} {o.colour} · {_f(o.quantity_meters):,.0f} m", "/app/order-desk")
    for s in low_stock(db):
        add("low_stock", "warning", f"Low stock: {s.yarn_type} {s.colour}",
            f"{_f(s.quantity_kg):,.0f} kg left (reorder at {_f(s.reorder_level_kg):,.0f} kg)", "/app/super-inventory")
    for o in db.query(Order).filter(Order.status.in_(ACTIVE_ORDER)).all():
        if not o.deadline:
            continue
        prog = order_display_progress(db, o)
        if o.deadline < today:
            add("delayed", "critical", f"{o.order_no} is past its deadline",
                f"Due {o.deadline.strftime('%d/%m/%Y')} · {prog:.0f}% made · {o.status.replace('_', ' ')}", "/app/super-production")
        elif (o.deadline - today).days <= 3 and prog < 80 and o.status in ("confirmed", "in_production"):
            add("delayed", "warning", f"{o.order_no} may be late",
                f"Due in {(o.deadline - today).days} days · only {prog:.0f}% made", "/app/super-production")
    for mch in db.query(Machine).filter(Machine.current_status == "breakdown").all():
        hrs = None
        if mch.status_since:
            since = mch.status_since if mch.status_since.tzinfo else mch.status_since.replace(tzinfo=timezone.utc)
            hrs = (datetime.now(timezone.utc) - since).total_seconds() / 3600
        add("breakdown", "critical", f"{mch.name} has broken down",
            f"Down for {hrs:.1f} h" if hrs is not None else "Marked as broken down", "/app/super-production")
    pending = db.query(Roll).filter(Roll.status == "pending").count()
    if pending:
        add("qc_pending", "info", f"{pending} roll{'s' if pending != 1 else ''} waiting for inspection", "Quality has not checked them yet.", "/app/super-quality")
    for e in dispatch_exceptions(db):
        add("dispatch", "warning", "Dispatch problem", e["detail"], "/app/super-dispatch")
    absent = (db.query(Attendance).filter(Attendance.work_date == today, Attendance.status == "absent").count())
    marked = db.query(Attendance.employee_id).filter(Attendance.work_date == today).distinct().count()
    active = db.query(Employee).filter(Employee.is_active.isnot(False)).count()
    if absent or (marked and marked < active):
        add("attendance", "info", "Attendance exceptions today",
            f"{absent} absent · {max(0, active - marked)} not marked yet", "/app/super-attendance")
    for t in db.query(Task).filter(Task.status != "completed").all():
        if is_overdue(t, today):
            add("overdue_tasks", "warning", f"Overdue: {t.title}",
                f"{DEPT_LABEL.get(t.department, t.department)} · due {t.deadline.strftime('%d/%m/%Y')}", "/app/super-tasks")
    from app.models import PurchaseRequest

    for r in db.query(PurchaseRequest).filter(PurchaseRequest.status == "pending").order_by(PurchaseRequest.id).all():
        add("purchase_approvals", "warning", f"Purchase request {r.pr_no} needs approval",
            f"{float(r.quantity_kg):,.0f} kg {r.yarn_type} {r.colour}" + (f" · needed by {r.required_date.strftime('%d/%m/%Y')}" if r.required_date else ""),
            "/app/super-inventory")
    rank = {"critical": 0, "warning": 1, "info": 2}
    out.sort(key=lambda a: rank.get(a["severity"], 3))
    return out


# --------------------------------------------------------------------------- #
# Overview (dashboard)
# --------------------------------------------------------------------------- #
def overview(db: Session) -> dict:
    counts = dict(db.query(Order.status, func.count(Order.id)).group_by(Order.status).all())
    start, end = month_window()
    managers = [u for u in dept_managers(db) if u.is_active]
    cards = {
        "department_managers": len(managers),
        "workers": db.query(Employee).filter(Employee.is_active.isnot(False)).count(),
        "pending_orders": counts.get("pending_review", 0) + counts.get("draft", 0) + counts.get("clarification", 0),
        "confirmed_orders": counts.get("confirmed", 0),
        "in_production": counts.get("in_production", 0),
        "qc_pending": db.query(Roll).filter(Roll.status == "pending").count(),
        "dispatch_pending": counts.get("ready_to_ship", 0),
        "present_today": present_today(db),
    }
    recent = db.query(Order).order_by(Order.id.desc()).limit(8).all()
    approvals = (db.query(Order).filter(Order.status.in_(("pending_review", "draft", "clarification")))
                 .order_by(Order.id).all())
    acts = db.query(ActivityLog).order_by(ActivityLog.id.desc()).limit(12).all()
    al = alerts(db)
    return {
        "cards": cards,
        "order_progress": [{"status": s, "count": counts.get(s, 0)} for s in PIPELINE if counts.get(s, 0)],
        "departments": department_performance(db, start, end),
        "recent_orders": [order_row(db, o) for o in recent],
        "pending_approvals": [order_row(db, o) for o in approvals],
        "alerts": [a for a in al if a["severity"] in ("critical", "warning")][:8],
        "alerts_total": len(al),
        "activity": [activity_row(a) for a in acts],
        "month": {"start": start.isoformat(), "end": end.isoformat()},
    }


def activity_row(a: ActivityLog) -> dict:
    return {"id": a.id, "at": a.at.isoformat() if a.at else None, "user": a.user_name or "System",
            "role": a.user_role, "category": a.category, "action": a.action, "details": a.details}


def task_row(db: Session, t: Task) -> dict:
    mgr = db.get(User, t.manager_user_id) if t.manager_user_id else None
    order = db.get(Order, t.order_id) if t.order_id else None
    worker = db.get(Employee, t.worker_employee_id) if t.worker_employee_id else None
    return {
        "id": t.id, "title": t.title, "details": t.details,
        "department": t.department, "department_label": DEPT_LABEL.get(t.department, t.department),
        "manager": user_brief(mgr), "order_no": order.order_no if order else None, "order_id": t.order_id,
        "worker": {"id": worker.id, "name": worker.name} if worker else None,
        "priority": t.priority, "deadline": t.deadline.isoformat() if t.deadline else None,
        "status": t.status, "shown_status": shown_status(t), "auto": bool(t.auto),
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


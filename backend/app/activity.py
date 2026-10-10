"""Automatic, append-only activity log.

Who did it comes from session.info["actor"], set by deps.get_current_user for
every signed-in request. Important changes found in a flush are written as
ActivityLog rows in the same transaction, so a rolled-back change leaves no log.
"""

from __future__ import annotations

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app import models as m


def _hist(obj, attr):
    """(old, new, changed) for an attribute in this flush."""
    h = inspect(obj).attrs[attr].history
    if not h.has_changes():
        return None, getattr(obj, attr), False
    old = h.deleted[0] if h.deleted else None
    new = h.added[0] if h.added else getattr(obj, attr)
    return old, new, True


def _fmt(v):
    if v is None:
        return "—"
    if isinstance(v, float) or hasattr(v, "quantize"):
        return f"{float(v):,.2f}".rstrip("0").rstrip(".")
    return str(v)


def _arrow(old, new):
    return f"{_fmt(old)} → {_fmt(new)}" if old is not None else _fmt(new)


def _st(v):
    """order/dispatch status code -> words (pending_review -> pending review)."""
    return None if v is None else str(v).replace("_", " ")


def _entries(session):  # noqa: C901 - one flat list of cases reads best here
    out = []
    for obj in list(session.new) + list(session.dirty):
        if isinstance(obj, m.ActivityLog):
            continue
        is_new = obj in session.new
        if isinstance(obj, m.Order):
            if is_new:
                out.append(("order", "created", f"{obj.order_no} · {obj.fabric_type} {obj.colour} · {_fmt(obj.quantity_meters)} m · {_st(obj.status)}"))
            else:
                old, new, ch = _hist(obj, "status")
                if ch:
                    note = f" · {obj.review_note}" if new in ("rejected", "clarification") and obj.review_note else ""
                    out.append(("order", f"status_{new}", f"{obj.order_no}: {_arrow(_st(old), _st(new))}{note}"))
        elif isinstance(obj, m.YarnStock):
            old, new, ch = _hist(obj, "quantity_kg")
            if is_new:
                out.append(("stock", "added", f"{obj.yarn_type} {obj.colour}: {_fmt(obj.quantity_kg)} kg"))
            elif ch:
                out.append(("stock", "changed", f"{obj.yarn_type} {obj.colour}: {_arrow(old, new)} kg"))
        elif isinstance(obj, m.QualityInspection) and is_new:
            roll = session.get(m.Roll, obj.roll_id)
            out.append(("qc", obj.result, f"Roll {roll.roll_no if roll else obj.roll_id}: {obj.result}" + (f" · {obj.defect_type}" if obj.defect_type and obj.defect_type != "none" else "")))
        elif isinstance(obj, m.Dispatch):
            if is_new:
                out.append(("dispatch", "created", f"{obj.dispatch_no}: {obj.total_rolls} rolls · {_fmt(obj.total_meters)} m"))
            else:
                old, new, ch = _hist(obj, "status")
                if ch:
                    out.append(("dispatch", f"status_{new}", f"{obj.dispatch_no}: {_arrow(_st(old), _st(new))}"))
        elif isinstance(obj, m.Attendance):
            emp = session.get(m.Employee, obj.employee_id)
            who = emp.name if emp else f"#{obj.employee_id}"
            if is_new:
                out.append(("attendance", "marked", f"{who} · {obj.work_date} · {obj.status}"))
            else:
                old, new, ch = _hist(obj, "status")
                if ch:
                    out.append(("attendance", "corrected", f"{who} · {obj.work_date}: {_arrow(old, new)}"))
        elif isinstance(obj, m.User):
            role = obj.role.name if obj.role else ""
            role = "supermanager" if role == "manager" else role.replace("_", " ")
            if is_new:
                out.append(("team", "user_created", f"New login: {obj.name} ({role})"))
            else:
                for attr, label in (("is_active", "active"), ("department", "department"), ("name", "name"), ("email", "email")):
                    old, new, ch = _hist(obj, attr)
                    if ch:
                        out.append(("team", f"user_{label}", f"{obj.name}: {label} {_arrow(old, new)}"))
                if _hist(obj, "password_hash")[2]:
                    out.append(("team", "password_reset", f"{obj.name}: password reset"))
        elif isinstance(obj, m.Employee):
            if is_new:
                out.append(("worker", "added", f"{obj.name}" + (f" · {obj.department}" if obj.department else "")))
            else:
                for attr in ("department", "manager_user_id", "is_active", "daily_wage", "name"):
                    old, new, ch = _hist(obj, attr)
                    if ch:
                        out.append(("worker", f"{attr}", f"{obj.name}: {attr.replace('_user_id', '').replace('_', ' ')} {_arrow(old, new)}"))
        elif isinstance(obj, m.Task):
            if is_new:
                out.append(("task", "assigned", f"{obj.title} → {obj.department} · {obj.priority}"))
            else:
                old, new, ch = _hist(obj, "status")
                if ch:
                    out.append(("task", f"status_{new}", f"{obj.title}: {_arrow(_st(old), _st(new))}"))
        elif isinstance(obj, m.Payment):
            if is_new:
                out.append(("payment", obj.direction, f"{obj.direction} ₹{_fmt(obj.amount)}"))
            elif _hist(obj, "voided_at")[2]:
                out.append(("payment", "voided", f"₹{_fmt(obj.amount)} voided · {obj.void_reason or ''}"))
    return out


@event.listens_for(Session, "before_flush")
def _log_activity(session, flush_context, instances):  # noqa: ARG001
    entries = _entries(session)
    if not entries:
        return
    actor = session.info.get("actor") or {}
    for cat, action, details in entries:
        session.add(m.ActivityLog(
            user_id=actor.get("id"), user_name=actor.get("name"), user_role=actor.get("role"),
            category=cat, action=action, details=details[:2000],
        ))

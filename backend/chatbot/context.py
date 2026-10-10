"""Role-scoped live-data context for the logged-in chatbot mode (C4).

Public mode (no user) sends NO private data — Dify answers FAQ/how-to only.

Logged-in mode builds a short, read-only "facts" block limited by role and passes
it to Dify as an input variable. A buyer only ever gets their own orders.

Keeping this in backend/chatbot/ (the chatbot owner's folder) and reusing the
shared models/services. No other module's files are modified.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Invoice, Machine, Order, User, YarnStock
from app.services.production import idle_loss_for_machine, order_progress_percent


def build_context(db: Session, user: User | None) -> str:
    """Return a plain-text facts block for Dify, or '' for public mode."""
    if user is None:
        return ""  # public mode: no private data

    role = user.role.name

    if role == "buyer":
        return _buyer_context(db, user)
    if role in ("owner",):
        return _owner_context(db)
    if role in ("store_manager",):
        return _stock_context(db)
    if role in ("floor_supervisor",):
        return _floor_context(db)
    # accountant / quality_inspector: minimal, role-appropriate facts
    if role == "accountant":
        return _finance_context(db)
    return f"Logged in as role '{role}'. No special live data available."


def _buyer_context(db: Session, user: User) -> str:
    # Buyer sees ONLY their own orders / invoices.
    orders = db.query(Order).filter(Order.buyer_id == user.buyer_id).all()
    lines = [f"You are helping buyer '{user.name}'. Only their own data is shown."]
    if not orders:
        lines.append("This buyer has no orders.")
    for o in orders:
        lines.append(
            f"Order {o.order_no}: {o.fabric_type} {o.colour}, "
            f"{float(o.quantity_meters)}m, status={o.status}, "
            f"progress={order_progress_percent(db, o)}%."
        )
    invoices = db.query(Invoice).filter(Invoice.buyer_id == user.buyer_id).all()
    for inv in invoices:
        lines.append(
            f"Invoice {inv.invoice_no}: total Rs {float(inv.total)}, status={inv.status}."
        )
    return "\n".join(lines)


def _owner_context(db: Session) -> str:
    stage_rows = (
        db.query(Order.status, func.count(Order.id)).group_by(Order.status).all()
    )
    stages = ", ".join(f"{s}={c}" for s, c in stage_rows) or "none"
    total_idle = 0.0
    for m in db.query(Machine).all():
        total_idle += idle_loss_for_machine(db, m.id, float(m.hourly_cost or 0))[
            "loss_rupees"
        ]
    return (
        f"Owner view. Orders by stage: {stages}. "
        f"Total idle-machine loss so far: Rs {round(total_idle, 2)}."
    )


def _stock_context(db: Session) -> str:
    lines = ["Store manager view. Yarn stock:"]
    for s in db.query(YarnStock).all():
        lines.append(f"- {s.yarn_type} {s.colour}: {float(s.quantity_kg)} kg")
    return "\n".join(lines)


def _floor_context(db: Session) -> str:
    lines = ["Floor supervisor view. Machines:"]
    for m in db.query(Machine).all():
        lines.append(f"- {m.name} ({m.type}): {m.current_status}")
    return "\n".join(lines)


def _finance_context(db: Session) -> str:
    unpaid = db.query(func.count(Invoice.id)).filter(Invoice.status != "paid").scalar()
    return f"Accountant view. Invoices not fully paid: {unpaid}."

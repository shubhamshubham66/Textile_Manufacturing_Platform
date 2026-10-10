"""Read-only aggregations for the Sales & Dispatch Manager screens.

Everything is computed from the live tables (orders, rolls, dispatches,
invoices, payments, buyers). This service never writes; writes live in the
router and reuse the existing atomic dispatch service.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    ActivityLog,
    Buyer,
    Dispatch,
    DispatchItem,
    Invoice,
    Order,
    Payment,
    Roll,
)
from app.services.production import order_display_progress

# Orders the sales desk cares about (confirmed by the Supermanager onward).
SALES_ORDERS = ("confirmed", "in_production", "in_quality", "ready_to_ship",
                "partially_dispatched", "dispatched", "closed")
# Buyer-facing status label for each internal order status.
STATUS_LABEL = {
    "confirmed": "Confirmed",
    "in_production": "In Production",
    "in_quality": "QC Pending",
    "ready_to_ship": "Ready for Dispatch",
    "partially_dispatched": "Partially Dispatched",
    "dispatched": "Dispatched",
    "closed": "Delivered",
}


def _f(v) -> float:
    return round(float(v or 0), 2)


def _iso(v) -> str | None:
    return v.isoformat() if v else None


# --------------------------------------------------------------------------- #
# Finished-stock helpers (QC-approved = rolls with status 'pass')
# --------------------------------------------------------------------------- #
def approved_rolls_for_order(db: Session, order_id: int) -> list[Roll]:
    """Rolls of an order that passed QC and are NOT yet dispatched."""
    return (
        db.query(Roll)
        .filter(Roll.order_id == order_id, Roll.status == "pass")
        .order_by(Roll.id)
        .all()
    )


def _dispatched_meters(db: Session, order_id: int) -> float:
    return _f(
        db.query(func.coalesce(func.sum(Dispatch.total_meters), 0))
        .filter(Dispatch.order_id == order_id)
        .scalar()
    )


def _approved_available(db: Session, order_id: int) -> tuple[int, float]:
    rows = approved_rolls_for_order(db, order_id)
    return len(rows), round(sum(float(r.length_meters or 0) for r in rows), 2)


def order_row(db: Session, o: Order) -> dict:
    today = date.today()
    rolls_ready, meters_ready = _approved_available(db, o.id)
    dispatched_m = _dispatched_meters(db, o.id)
    late = bool(
        o.deadline
        and o.deadline < today
        and o.status in ("confirmed", "in_production", "in_quality", "ready_to_ship", "partially_dispatched")
    )
    return {
        "id": o.id,
        "order_no": o.order_no,
        "buyer": o.buyer.name if o.buyer else "",
        "buyer_id": o.buyer_id,
        "fabric_type": o.fabric_type,
        "colour": o.colour,
        "quantity_meters": _f(o.quantity_meters),
        "dispatched_meters": dispatched_m,
        "remaining_meters": round(max(0.0, float(o.quantity_meters or 0) - dispatched_m), 2),
        "rolls_ready": rolls_ready,
        "meters_ready": meters_ready,
        "deadline": _iso(o.deadline),
        "status": o.status,
        "status_label": STATUS_LABEL.get(o.status, o.status.replace("_", " ").title()),
        "progress": order_display_progress(db, o),
        "late": late,
        "unit_price": _f(o.unit_price),
    }


# --------------------------------------------------------------------------- #
# Buyer dues (read-only — Accounts owns the money, this is a view only)
# --------------------------------------------------------------------------- #
def _invoice_paid(db: Session, invoice_id: int) -> float:
    return _f(
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(
            Payment.invoice_id == invoice_id,
            Payment.direction == "incoming",
            Payment.voided_at.is_(None),
        )
        .scalar()
    )


def buyer_dues(db: Session) -> dict:
    invoices = db.query(Invoice).order_by(Invoice.id.desc()).all()
    rows = []
    total_outstanding = 0.0
    for inv in invoices:
        paid = _invoice_paid(db, inv.id)
        balance = round(float(inv.total or 0) - paid, 2)
        buyer = db.get(Buyer, inv.buyer_id)
        order = db.get(Order, inv.order_id)
        if balance > 0.01:
            total_outstanding += balance
        rows.append(
            {
                "invoice_no": inv.invoice_no,
                "order_no": order.order_no if order else None,
                "buyer": buyer.name if buyer else "",
                "total": _f(inv.total),
                "paid": paid,
                "balance": balance,
                "status": inv.status,
                "created_at": _iso(inv.created_at),
            }
        )
    return {
        "total_outstanding": round(total_outstanding, 2),
        "unpaid_invoices": sum(1 for r in rows if r["balance"] > 0.01),
        "rows": rows,
    }


# --------------------------------------------------------------------------- #
# Dispatch rows
# --------------------------------------------------------------------------- #
def dispatch_row(db: Session, d: Dispatch) -> dict:
    order = db.get(Order, d.order_id)
    buyer = db.get(Buyer, d.buyer_id)
    invoice = db.query(Invoice).filter(Invoice.dispatch_id == d.id).first()
    items = db.query(DispatchItem).filter(DispatchItem.dispatch_id == d.id).all()
    roll_nos = []
    for it in items:
        r = db.get(Roll, it.roll_id)
        roll_nos.append(r.roll_no if r else f"#{it.roll_id}")
    return {
        "id": d.id,
        "dispatch_no": d.dispatch_no,
        "challan_no": d.challan_no,
        "order_no": order.order_no if order else "",
        "buyer": buyer.name if buyer else "",
        "total_rolls": d.total_rolls,
        "total_meters": _f(d.total_meters),
        "status": d.status,
        "vehicle_no": d.vehicle_no,
        "transporter": d.transporter,
        "driver_phone": d.driver_phone,
        "delivery_address": d.delivery_address,
        "rolls": roll_nos,
        "invoice_no": invoice.invoice_no if invoice else None,
        "invoice_id": invoice.id if invoice else None,
        "dispatched_at": _iso(d.dispatched_at),
        "delivered_at": _iso(d.delivered_at),
    }


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
def dashboard(db: Session) -> dict:
    today = date.today()
    counts = dict(db.query(Order.status, func.count(Order.id)).group_by(Order.status).all())

    sales_orders = (
        db.query(Order)
        .filter(Order.status.in_(SALES_ORDERS))
        .order_by(Order.deadline.is_(None), Order.deadline, Order.id)
        .all()
    )
    order_rows = [order_row(db, o) for o in sales_orders]

    # QC-approved finished stock on the shelf (pass, not dispatched).
    approved = db.query(Roll).filter(Roll.status == "pass").all()
    approved_rolls = len(approved)
    approved_meters = round(sum(float(r.length_meters or 0) for r in approved), 2)

    # Orders ready for dispatch = have at least one approved roll waiting.
    ready = [r for r in order_rows if r["rolls_ready"] > 0]

    dispatches = db.query(Dispatch).order_by(Dispatch.id.desc()).all()
    pending_dispatches = [d for d in dispatches if d.status != "delivered" and d.delivered_at is None]
    dispatched_orders = counts.get("dispatched", 0) + counts.get("partially_dispatched", 0) + counts.get("closed", 0)

    delayed = [r for r in order_rows if r["late"]]
    dues = buyer_dues(db)

    cards = {
        "total_buyer_orders": sum(counts.get(s, 0) for s in SALES_ORDERS),
        "pending_dispatches": len(pending_dispatches),
        "qc_approved_rolls": approved_rolls,
        "qc_approved_meters": approved_meters,
        "orders_ready_for_dispatch": len(ready),
        "dispatched_orders": dispatched_orders,
        "delayed_deliveries": len(delayed),
        "pending_buyer_payments": dues["unpaid_invoices"],
        "pending_buyer_amount": dues["total_outstanding"],
    }

    acts = (
        db.query(ActivityLog)
        .filter(ActivityLog.category.in_(("dispatch", "order", "qc", "payment")))
        .order_by(ActivityLog.id.desc())
        .limit(10)
        .all()
    )

    return {
        "cards": cards,
        "ready_for_dispatch": ready[:8],
        "delayed": delayed,
        "recent_dispatches": [dispatch_row(db, d) for d in dispatches[:6]],
        "pending_payments": dues["rows"][:6],
        "activity": [activity_row(a) for a in acts],
        "pipeline": [
            {"status": s, "label": STATUS_LABEL.get(s, s), "count": counts.get(s, 0)}
            for s in SALES_ORDERS
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

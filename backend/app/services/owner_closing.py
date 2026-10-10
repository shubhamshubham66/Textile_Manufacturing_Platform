"""Owner "closing the books" — read-only aggregations for the owner dashboard.

Everything here is for a selected month (same window helpers as services.reports)
so the order history, order slip, raw-material bills and buyer-payments lists all
line up with the Month summary band. The owner only VIEWS: nothing here writes.

Status groups the owner cares about:
  Awaiting   -> draft
  Confirmed  -> confirmed (production not started)
  Ongoing    -> in_production, in_quality, ready_to_ship
  Completed  -> dispatched, closed
  Cancelled  -> cancelled
(There is no order-level "Rejected" status yet; that is a separate change.)
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Buyer,
    Dispatch,
    Invoice,
    Machine,
    Order,
    Payment,
    PurchaseOrder,
    QualityInspection,
    Roll,
    Supplier,
)
from app.services.production import order_display_progress
from app.services.reports import cost_per_order

STATUS_GROUP = {
    "draft": "awaiting",
    "confirmed": "confirmed",
    "in_production": "ongoing",
    "in_quality": "ongoing",
    "ready_to_ship": "ongoing",
    "dispatched": "completed",
    "closed": "completed",
    "cancelled": "cancelled",
}

GROUP_ORDER = ["awaiting", "confirmed", "ongoing", "completed", "cancelled"]


def _cost_by_order_no(db: Session, start: date | None, end: date | None) -> dict[str, dict]:
    return {r["order_no"]: r for r in cost_per_order(db, start, end)}


def _late(order: Order, progress: float) -> bool:
    if not order.deadline or order.status in ("dispatched", "closed", "cancelled"):
        return False
    return date.today() > order.deadline and progress < 100.0


def order_history(db: Session, start: date | None, end: date | None) -> dict:
    """All orders (not month-filtered — history is a running record), each with
    its month-window cost, progress and late flag, plus per-group counts."""
    costs = _cost_by_order_no(db, start, end)
    orders = db.query(Order).order_by(Order.id.desc()).all()
    rows = []
    counts = {g: 0 for g in GROUP_ORDER}
    counts["all"] = 0
    for o in orders:
        progress = order_display_progress(db, o)
        group = STATUS_GROUP.get(o.status, "ongoing")
        counts[group] = counts.get(group, 0) + 1
        counts["all"] += 1
        buyer = db.query(Buyer).filter(Buyer.id == o.buyer_id).first()
        c = costs.get(o.order_no)
        rows.append(
            {
                "id": o.id,
                "order_no": o.order_no,
                "buyer_name": buyer.name if buyer else "",
                "fabric_type": o.fabric_type,
                "colour": o.colour,
                "quantity_meters": float(o.quantity_meters or 0),
                "unit_price": float(o.unit_price or 0),
                "deadline": o.deadline.isoformat() if o.deadline else None,
                "status": o.status,
                "group": group,
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "progress_percent": progress,
                "late": _late(o, progress),
                "total_cost": c["total_cost"] if c else 0.0,
                "revenue_est": c["revenue_est"] if c else 0.0,
                "margin_est": c["margin_est"] if c else 0.0,
            }
        )
    return {"rows": rows, "counts": counts}


def order_slip(db: Session, order_id: int, start: date | None, end: date | None) -> dict | None:
    """One order's printable slip: details, rolls (with inspection + machine),
    dispatch/invoice reference, and the month-window cost summary."""
    o = db.query(Order).filter(Order.id == order_id).first()
    if o is None:
        return None
    buyer = db.query(Buyer).filter(Buyer.id == o.buyer_id).first()
    progress = order_display_progress(db, o)

    rolls = []
    for r in db.query(Roll).filter(Roll.order_id == o.id).order_by(Roll.id).all():
        insp = (
            db.query(QualityInspection)
            .filter(QualityInspection.roll_id == r.id)
            .first()
        )
        machine = db.query(Machine).filter(Machine.id == r.machine_id).first()
        result = insp.result if insp else ("pass" if r.status == "dispatched" else "pending")
        rolls.append(
            {
                "roll_no": r.roll_no,
                "length_meters": float(r.length_meters or 0),
                "machine": machine.name if machine else "—",
                "result": result,
                "defect_type": insp.defect_type if insp else "none",
            }
        )

    dispatch = db.query(Dispatch).filter(Dispatch.order_id == o.id).first()
    invoice = db.query(Invoice).filter(Invoice.order_id == o.id).first()
    c = _cost_by_order_no(db, start, end).get(o.order_no)

    return {
        "order_no": o.order_no,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "buyer_name": buyer.name if buyer else "",
        "buyer_address": buyer.address if buyer else "",
        "fabric_type": o.fabric_type,
        "colour": o.colour,
        "quantity_meters": float(o.quantity_meters or 0),
        "unit_price": float(o.unit_price or 0),
        "deadline": o.deadline.isoformat() if o.deadline else None,
        "status": o.status,
        "group": STATUS_GROUP.get(o.status, "ongoing"),
        "progress_percent": progress,
        "late": _late(o, progress),
        "rolls": rolls,
        "dispatch_no": dispatch.dispatch_no if dispatch else None,
        "invoice_no": invoice.invoice_no if invoice else None,
        "cost": {
            "yarn": c["yarn_cost"] if c else 0.0,
            "wages": c["wage_cost"] if c else 0.0,
            "machine": c["machine_cost"] if c else 0.0,
            "total": c["total_cost"] if c else 0.0,
            "revenue_est": c["revenue_est"] if c else 0.0,
            "margin_est": c["margin_est"] if c else 0.0,
        },
    }


def raw_material_bills(db: Session, start: date | None, end: date | None) -> dict:
    """Supplier (raw material) side for the month, in one place:
    - bills: purchase orders as the 'bills' (date, supplier, bill no = PO no,
      amount = qty×rate, status raised/received)
    - payments made to suppliers in the month (what actually left the bank)
    - totals: paid (matches the Month band) and still outstanding.
    """
    # Bills = purchase orders (the raw-material liabilities), newest first.
    bills = []
    total_billed = 0.0
    for po in db.query(PurchaseOrder).order_by(PurchaseOrder.id.desc()).all():
        amount = float(po.quantity_kg or 0) * float(po.unit_cost or 0)
        if po.status in ("raised", "received"):
            total_billed += amount
        sup = db.query(Supplier).filter(Supplier.id == po.supplier_id).first()
        bills.append(
            {
                "bill_no": po.po_no,
                "date": po.created_at.date().isoformat() if po.created_at else None,
                "supplier": sup.name if sup else "",
                "yarn_type": po.yarn_type,
                "colour": po.colour,
                "amount": round(amount, 2),
                "status": po.status,
            }
        )

    # Supplier payments actually made in the month (exclude voided).
    paid_q = (
        db.query(Payment)
        .filter(Payment.direction == "outgoing", Payment.voided_at.is_(None))
    )
    if start:
        paid_q = paid_q.filter(func.date(Payment.paid_at) >= start)
    if end:
        paid_q = paid_q.filter(func.date(Payment.paid_at) <= end)
    total_paid = 0.0
    payments = []
    for p in paid_q.order_by(Payment.id.desc()).all():
        sup = db.query(Supplier).filter(Supplier.id == p.supplier_id).first()
        total_paid += float(p.amount or 0)
        payments.append(
            {
                "date": p.paid_at.date().isoformat() if p.paid_at else None,
                "supplier": sup.name if sup else "",
                "amount": float(p.amount or 0),
                "method": p.method,
            }
        )

    return {
        "bills": bills,
        "payments": payments,
        "total_paid": round(total_paid, 2),
        "total_outstanding": round(max(0.0, total_billed - _supplier_paid_all_time(db)), 2),
    }


def _supplier_paid_all_time(db: Session) -> float:
    v = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.direction == "outgoing", Payment.voided_at.is_(None))
        .scalar()
    )
    return float(v or 0)


def buyer_payments_list(db: Session, start: date | None, end: date | None) -> dict:
    """Buyer payments received in the month (what the Month band counts) plus the
    outstanding receivable across all invoices."""
    q = (
        db.query(Payment)
        .filter(Payment.direction == "incoming", Payment.voided_at.is_(None))
    )
    if start:
        q = q.filter(func.date(Payment.paid_at) >= start)
    if end:
        q = q.filter(func.date(Payment.paid_at) <= end)
    total_received = 0.0
    rows = []
    for p in q.order_by(Payment.id.desc()).all():
        buyer = db.query(Buyer).filter(Buyer.id == p.buyer_id).first()
        inv = db.query(Invoice).filter(Invoice.id == p.invoice_id).first()
        total_received += float(p.amount or 0)
        rows.append(
            {
                "date": p.paid_at.date().isoformat() if p.paid_at else None,
                "buyer": buyer.name if buyer else "",
                "invoice_no": inv.invoice_no if inv else None,
                "amount": float(p.amount or 0),
                "method": p.method,
            }
        )

    # Outstanding receivable = Σ(invoice total − non-voided incoming paid).
    outstanding = 0.0
    for inv in db.query(Invoice).all():
        paid = (
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(
                Payment.direction == "incoming",
                Payment.invoice_id == inv.id,
                Payment.voided_at.is_(None),
            )
            .scalar()
            or 0
        )
        bal = float(inv.total or 0) - float(paid)
        if bal > 0.001:
            outstanding += bal

    return {
        "payments": rows,
        "total_received": round(total_received, 2),
        "total_outstanding": round(outstanding, 2),
    }

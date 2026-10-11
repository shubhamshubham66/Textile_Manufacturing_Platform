"""Buyer pays against an ORDER, from confirmation until delivery.

- Once an order is confirmed the buyer can pay (in parts if they like). Each
  payment is a BuyerPaymentRequest until the accounts team confirms it; only a
  confirmed request becomes a real incoming Payment (with `order_id`).
- Invoices are raised later, at dispatch. `allocate_to_invoices` moves the
  order's unattached payments onto its open invoices (splitting a payment when
  it covers more than one invoice), so every existing invoice / dues / report
  total keeps working on `Payment.invoice_id`.
- Delivery is refused until the dispatch's invoice is fully paid.
"""

from __future__ import annotations

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import BuyerPaymentRequest, Invoice, Order, Payment

settings = get_settings()

# Order stages in which the buyer may pay.
PAYABLE_STATUSES = ("confirmed", "in_production", "in_quality", "ready_to_ship", "dispatched")
SPLIT = "advance_split"  # category on the remainder row of a split payment


def order_value(order: Order) -> float:
    sub = float(order.quantity_meters or 0) * float(order.unit_price or 0)
    return round(sub * (1 + settings.invoice_tax_rate), 2)


def _invoices(db: Session, order_id: int) -> list[Invoice]:
    return db.query(Invoice).filter(Invoice.order_id == order_id).order_by(Invoice.id).all()


def paid_for_order(db: Session, order: Order) -> float:
    inv_ids = [i.id for i in _invoices(db, order.id)]
    cond = Payment.order_id == order.id
    if inv_ids:
        cond = or_(cond, Payment.invoice_id.in_(inv_ids))
    total = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.direction == "incoming", Payment.voided_at.is_(None), cond)
        .scalar()
    )
    return round(float(total or 0), 2)


def pending_for_order(db: Session, order_id: int) -> float:
    total = (
        db.query(func.coalesce(func.sum(BuyerPaymentRequest.amount), 0))
        .filter(BuyerPaymentRequest.order_id == order_id, BuyerPaymentRequest.status == "pending")
        .scalar()
    )
    return round(float(total or 0), 2)


def summary(db: Session, order: Order) -> dict:
    """Total / paid / awaiting confirmation / balance for one order."""
    invoiced = round(sum(float(i.total) for i in _invoices(db, order.id)), 2)
    total = max(order_value(order), invoiced)
    paid = paid_for_order(db, order)
    pending = pending_for_order(db, order.id)
    balance = round(max(0.0, total - paid), 2)
    if total > 0 and balance <= 0.5:
        status = "paid"
    elif paid > 0:
        status = "part_paid"
    else:
        status = "unpaid"
    payable = round(max(0.0, balance - pending), 2)
    return {
        "total": total,
        "invoiced": invoiced,
        "paid": paid,
        "pending": pending,
        "balance": balance,
        "payable": payable,
        "status": status,
        "can_pay": order.status in PAYABLE_STATUSES and payable > 0.5,
    }


def _refresh_invoice(db: Session, inv: Invoice) -> None:
    paid = float(
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.direction == "incoming", Payment.invoice_id == inv.id, Payment.voided_at.is_(None))
        .scalar()
        or 0
    )
    total = float(inv.total)
    inv.status = "unpaid" if paid <= 0 else ("part_paid" if paid + 0.001 < total else "paid")


def allocate_to_invoices(db: Session, order_id: int) -> None:
    """Attach the order's unattached payments to its open invoices, oldest first."""
    db.flush()
    loose = (
        db.query(Payment)
        .filter(
            Payment.order_id == order_id,
            Payment.invoice_id.is_(None),
            Payment.direction == "incoming",
            Payment.voided_at.is_(None),
        )
        .order_by(Payment.id)
        .all()
    )
    if not loose:
        return
    for inv in _invoices(db, order_id):
        paid = float(
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.direction == "incoming", Payment.invoice_id == inv.id, Payment.voided_at.is_(None))
            .scalar()
            or 0
        )
        room = round(float(inv.total) - paid, 2)
        while room > 0.001 and loose:
            p = loose[0]
            amt = float(p.amount)
            if amt <= room + 0.001:
                p.invoice_id = inv.id
                room = round(room - amt, 2)
                loose.pop(0)
            else:
                # Split: this invoice takes `room`, the rest waits for the next one.
                rest = Payment(
                    direction="incoming", buyer_id=p.buyer_id, order_id=p.order_id,
                    amount=round(amt - room, 2), method=p.method, paid_at=p.paid_at,
                    reference=p.reference, recorded_by_user_id=p.recorded_by_user_id,
                    category=SPLIT, note=f"Balance of payment #{p.id}",
                )
                p.amount = room
                p.invoice_id = inv.id
                db.add(rest)
                db.flush()
                loose[0] = rest
                room = 0
        _refresh_invoice(db, inv)
        if not loose:
            break
    db.flush()


def dispatch_invoice_unpaid(db: Session, dispatch_id: int) -> tuple[Invoice | None, float]:
    """(invoice, balance) of a dispatch's invoice; balance 0 when settled/none."""
    inv = db.query(Invoice).filter(Invoice.dispatch_id == dispatch_id).first()
    if inv is None:
        return None, 0.0
    allocate_to_invoices(db, inv.order_id)
    paid = float(
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.direction == "incoming", Payment.invoice_id == inv.id, Payment.voided_at.is_(None))
        .scalar()
        or 0
    )
    return inv, round(max(0.0, float(inv.total) - paid), 2)

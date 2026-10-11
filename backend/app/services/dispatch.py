"""Dispatch service — the one-transaction confirm with a hard double-dispatch guard.

confirm_dispatch does ALL of the following atomically, or nothing:
  1. validate every roll belongs to the order/buyer and is 'pass' (not dispatched)
  2. mark each roll 'dispatched'
  3. create the dispatch record + dispatch_items (reduces finished-on-shelf stock)
  4. auto-create the invoice (metres × rate + tax)

Double dispatch is prevented at TWO levels:
  - application check: a roll must currently be 'pass' (dispatched rolls are rejected)
  - database constraint: dispatch_items.roll_id is UNIQUE (a roll can be in only
    one dispatch), so even a concurrent request cannot double-dispatch — the second
    insert raises IntegrityError and the whole transaction rolls back.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Dispatch, DispatchItem, Invoice, Order, Roll

settings = get_settings()


def _next_dispatch_no(db: Session) -> str:
    n = db.query(func.count(Dispatch.id)).scalar() or 0
    return f"DSP-{3001 + n}"


def _next_invoice_no(db: Session) -> str:
    n = db.query(func.count(Invoice.id)).scalar() or 0
    return f"INV-{4001 + n}"


def ensure_order_invoice(db: Session, order: Order) -> Invoice:
    """Return the order's invoice, creating a pre-dispatch one on first call.

    Buyers pay against this invoice BEFORE dispatch, so it is raised at order
    confirmation for the full ordered amount (quantity × unit price + tax). It
    has no dispatch yet (`dispatch_id` is null). If an invoice already exists
    for the order (e.g. created earlier at confirmation) it is returned as-is —
    this is idempotent, so confirming twice never raises a second invoice.

    The caller is responsible for the surrounding transaction/commit.
    """
    existing = (
        db.query(Invoice)
        .filter(Invoice.order_id == order.id)
        .order_by(Invoice.id)
        .first()
    )
    if existing is not None:
        return existing

    subtotal = round(float(order.quantity_meters or 0) * float(order.unit_price or 0), 2)
    tax = round(subtotal * settings.invoice_tax_rate, 2)
    invoice = Invoice(
        order_id=order.id,
        dispatch_id=None,  # pre-dispatch: paid before goods ship
        buyer_id=order.buyer_id,
        invoice_no=_next_invoice_no(db),
        subtotal=subtotal,
        tax=tax,
        total=round(subtotal + tax, 2),
        status="unpaid",
    )
    db.add(invoice)
    db.flush()
    return invoice


def confirm_dispatch(db: Session, order_id: int, roll_ids: list[int]) -> dict:
    if not roll_ids:
        raise HTTPException(status_code=400, detail="Select at least one roll")

    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    # Payment gate: goods ship only AFTER the buyer's invoice is fully paid and
    # confirmed by Accounts. The invoice is raised at order confirmation and
    # marked 'paid' by the accounts team once the buyer's payment clears.
    invoice = (
        db.query(Invoice)
        .filter(Invoice.order_id == order.id)
        .order_by(Invoice.id)
        .first()
    )
    if invoice is None:
        raise HTTPException(
            status_code=409,
            detail="No invoice for this order yet — confirm the order first so the buyer can pay.",
        )
    if invoice.status != "paid":
        raise HTTPException(
            status_code=402,
            detail=(
                f"Payment not complete for {order.order_no}: invoice {invoice.invoice_no} "
                f"is '{invoice.status}'. Dispatch is allowed only after the buyer's payment "
                "is confirmed by Accounts."
            ),
        )

    # Lock-free validation: load the rolls and check each one.
    rolls = db.query(Roll).filter(Roll.id.in_(roll_ids)).all()
    found_ids = {r.id for r in rolls}
    missing = set(roll_ids) - found_ids
    if missing:
        raise HTTPException(status_code=400, detail=f"Unknown roll ids: {sorted(missing)}")

    for r in rolls:
        if r.order_id != order_id:
            raise HTTPException(
                status_code=400,
                detail=f"Roll {r.roll_no} does not belong to this order",
            )
        if r.status == "dispatched":
            raise HTTPException(
                status_code=409,
                detail=f"Roll {r.roll_no} is already dispatched (no double dispatch)",
            )
        if r.status != "pass":
            raise HTTPException(
                status_code=400,
                detail=f"Roll {r.roll_no} is '{r.status}'; only passed rolls can be dispatched",
            )

    now = datetime.now(timezone.utc)
    total_meters = sum(float(r.length_meters) for r in rolls)

    try:
        dispatch = Dispatch(
            order_id=order.id,
            buyer_id=order.buyer_id,
            dispatch_no=_next_dispatch_no(db),
            total_rolls=len(rolls),
            total_meters=total_meters,
            status="shipped",
            dispatched_at=now,
        )
        db.add(dispatch)
        db.flush()  # need dispatch.id

        for r in rolls:
            db.add(
                DispatchItem(
                    dispatch_id=dispatch.id,
                    roll_id=r.id,  # UNIQUE -> hard double-dispatch guard
                    length_meters=r.length_meters,
                )
            )
            r.status = "dispatched"

        # Link the already-paid invoice (raised at confirmation) to this
        # dispatch. We do NOT change the amounts: the buyer has already paid the
        # confirmed invoice, so its total stays as billed/paid.
        invoice.dispatch_id = dispatch.id

        # Order is fully dispatched -> mark ready/closed state.
        order.status = "dispatched"

        db.commit()
    except IntegrityError:
        # Most likely the UNIQUE roll_id guard firing (concurrent dispatch).
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="One or more rolls were already dispatched (double dispatch prevented)",
        )
    except Exception:
        db.rollback()
        raise

    db.refresh(dispatch)
    db.refresh(invoice)
    return {
        "dispatch_id": dispatch.id,
        "dispatch_no": dispatch.dispatch_no,
        "invoice_id": invoice.id,
        "invoice_no": invoice.invoice_no,
        "total_rolls": dispatch.total_rolls,
        "total_meters": float(dispatch.total_meters),
        "subtotal": float(invoice.subtotal),
        "tax": float(invoice.tax),
        "total": float(invoice.total),
    }

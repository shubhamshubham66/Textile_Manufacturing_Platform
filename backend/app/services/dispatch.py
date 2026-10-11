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
from app.services.order_payments import allocate_to_invoices

settings = get_settings()


def _next_dispatch_no(db: Session) -> str:
    n = db.query(func.count(Dispatch.id)).scalar() or 0
    return f"DSP-{3001 + n}"


def _next_invoice_no(db: Session) -> str:
    n = db.query(func.count(Invoice.id)).scalar() or 0
    return f"INV-{4001 + n}"


def confirm_dispatch(db: Session, order_id: int, roll_ids: list[int]) -> dict:
    if not roll_ids:
        raise HTTPException(status_code=400, detail="Select at least one roll")

    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

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
    subtotal = round(total_meters * float(order.unit_price), 2)
    tax = round(subtotal * settings.invoice_tax_rate, 2)
    total = round(subtotal + tax, 2)

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

        invoice = Invoice(
            order_id=order.id,
            dispatch_id=dispatch.id,
            buyer_id=order.buyer_id,
            invoice_no=_next_invoice_no(db),
            subtotal=subtotal,
            tax=tax,
            total=total,
            status="unpaid",
        )
        db.add(invoice)
        # Advance payments the buyer already made on this order settle it now.
        allocate_to_invoices(db, order.id)

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
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
    }

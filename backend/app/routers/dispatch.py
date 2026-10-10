"""Dispatch module — scene 5.

Store manager (resource "dispatch"):
  GET  /api/dispatch/orders                 orders with pickable (passed) rolls
  GET  /api/dispatch/orders/{id}/pickable   ONLY passed, not-yet-dispatched rolls
  POST /api/dispatch/confirm                one-transaction confirm (see service)
  GET  /api/dispatch                        list dispatches
  GET  /api/dispatch/finished-stock         on-shelf (passed) vs dispatched
  GET  /api/dispatch/invoice/{id}           invoice JSON (rolls listed)
  GET  /api/dispatch/invoice/{id}/pdf       invoice as PDF
"""

from __future__ import annotations

import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_resource
from app.models import (
    Buyer,
    Dispatch,
    DispatchItem,
    Invoice,
    Order,
    Roll,
)
from app.services.dispatch import confirm_dispatch

router = APIRouter(prefix="/api/dispatch", tags=["dispatch"])


class ConfirmRequest(BaseModel):
    order_id: int
    roll_ids: list[int]


@router.get("/orders")
def dispatchable_orders(
    _=Depends(require_resource("dispatch")),
    db: Session = Depends(get_db),
):
    """Orders that have at least one passed, not-yet-dispatched roll."""
    rows = (
        db.query(Order.id, Order.order_no, Buyer.name, func.count(Roll.id))
        .join(Buyer, Buyer.id == Order.buyer_id)
        .join(Roll, Roll.order_id == Order.id)
        .filter(Roll.status == "pass")
        .group_by(Order.id, Order.order_no, Buyer.name)
        .all()
    )
    return [
        {"order_id": oid, "order_no": ono, "buyer_name": bn, "passed_rolls": cnt}
        for oid, ono, bn, cnt in rows
    ]


@router.get("/orders/{order_id}/pickable")
def pickable_rolls(
    order_id: int,
    _=Depends(require_resource("dispatch")),
    db: Session = Depends(get_db),
):
    """ONLY passed rolls of this order that are not yet dispatched."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    rolls = (
        db.query(Roll)
        .filter(Roll.order_id == order_id, Roll.status == "pass")
        .order_by(Roll.id)
        .all()
    )
    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "unit_price": float(order.unit_price),
        "rolls": [
            {"id": r.id, "roll_no": r.roll_no, "length_meters": float(r.length_meters)}
            for r in rolls
        ],
    }


@router.post("/confirm")
def confirm(
    body: ConfirmRequest,
    _=Depends(require_resource("dispatch")),
    db: Session = Depends(get_db),
):
    return confirm_dispatch(db, body.order_id, body.roll_ids)


@router.get("")
def list_dispatches(
    _=Depends(require_resource("dispatch")),
    db: Session = Depends(get_db),
):
    rows = db.query(Dispatch).order_by(Dispatch.id.desc()).all()
    out = []
    for d in rows:
        order = db.query(Order).filter(Order.id == d.order_id).first()
        buyer = db.query(Buyer).filter(Buyer.id == d.buyer_id).first()
        invoice = db.query(Invoice).filter(Invoice.dispatch_id == d.id).first()
        out.append(
            {
                "id": d.id,
                "dispatch_no": d.dispatch_no,
                "order_no": order.order_no if order else "",
                "buyer_name": buyer.name if buyer else "",
                "total_rolls": d.total_rolls,
                "total_meters": float(d.total_meters),
                "status": d.status,
                "invoice_no": invoice.invoice_no if invoice else None,
                "invoice_id": invoice.id if invoice else None,
                "dispatched_at": d.dispatched_at,
            }
        )
    return out


@router.get("/finished-stock")
def finished_stock(
    _=Depends(require_resource("dispatch")),
    db: Session = Depends(get_db),
):
    """Finished rolls on the shelf (passed, not dispatched) vs gone out
    (dispatched), grouped by order."""
    rows = (
        db.query(Order.order_no, Roll.status, func.count(Roll.id),
                 func.coalesce(func.sum(Roll.length_meters), 0))
        .join(Roll, Roll.order_id == Order.id)
        .filter(Roll.status.in_(("pass", "dispatched")))
        .group_by(Order.order_no, Roll.status)
        .all()
    )
    by_order: dict[str, dict] = {}
    for order_no, status, count, meters in rows:
        entry = by_order.setdefault(
            order_no,
            {"order_no": order_no, "on_shelf_rolls": 0, "on_shelf_meters": 0.0,
             "dispatched_rolls": 0, "dispatched_meters": 0.0},
        )
        if status == "pass":
            entry["on_shelf_rolls"] = int(count)
            entry["on_shelf_meters"] = float(meters)
        else:
            entry["dispatched_rolls"] = int(count)
            entry["dispatched_meters"] = float(meters)
    return list(by_order.values())


def _invoice_payload(db: Session, invoice_id: int) -> dict:
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    order = db.query(Order).filter(Order.id == invoice.order_id).first()
    buyer = db.query(Buyer).filter(Buyer.id == invoice.buyer_id).first()
    items = (
        db.query(DispatchItem)
        .filter(DispatchItem.dispatch_id == invoice.dispatch_id)
        .all()
    )
    rolls = []
    for it in items:
        roll = db.query(Roll).filter(Roll.id == it.roll_id).first()
        rolls.append(
            {
                "roll_no": roll.roll_no if roll else f"#{it.roll_id}",
                "length_meters": float(it.length_meters),
            }
        )
    return {
        "invoice_no": invoice.invoice_no,
        "order_no": order.order_no if order else "",
        "buyer_name": buyer.name if buyer else "",
        "buyer_address": (buyer.address if buyer else "") or "",
        "unit_price": float(order.unit_price) if order else 0,
        "rolls": rolls,
        "subtotal": float(invoice.subtotal),
        "tax": float(invoice.tax),
        "total": float(invoice.total),
        "status": invoice.status,
        "created_at": invoice.created_at.isoformat(),
    }


@router.get("/invoice/{invoice_id}")
def get_invoice(
    invoice_id: int,
    _=Depends(require_resource("dispatch")),
    db: Session = Depends(get_db),
):
    return _invoice_payload(db, invoice_id)


@router.get("/invoice/{invoice_id}/pdf")
def invoice_pdf(
    invoice_id: int,
    _=Depends(require_resource("dispatch")),
    db: Session = Depends(get_db),
):
    data = _invoice_payload(db, invoice_id)

    # Lazy import so the app still starts if reportlab is missing; the error is
    # then specific to this endpoint.
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="PDF generation requires reportlab (pip install reportlab)",
        )

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - 25 * mm

    c.setFont("Helvetica-Bold", 18)
    c.drawString(20 * mm, y, "Everest Textile Mills")
    c.setFont("Helvetica", 10)
    y -= 7 * mm
    c.drawString(20 * mm, y, "Tax Invoice")

    y -= 12 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20 * mm, y, f"Invoice: {data['invoice_no']}")
    c.drawString(120 * mm, y, f"Order: {data['order_no']}")
    y -= 6 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"Buyer: {data['buyer_name']}")
    y -= 5 * mm
    if data["buyer_address"]:
        c.drawString(20 * mm, y, f"Address: {data['buyer_address']}")
        y -= 5 * mm
    c.drawString(20 * mm, y, f"Date: {data['created_at'][:10]}")

    # Table header
    y -= 12 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, "Roll")
    c.drawString(120 * mm, y, "Length (m)")
    c.line(20 * mm, y - 2 * mm, 190 * mm, y - 2 * mm)

    c.setFont("Helvetica", 10)
    for roll in data["rolls"]:
        y -= 6 * mm
        if y < 40 * mm:
            c.showPage()
            y = height - 25 * mm
            c.setFont("Helvetica", 10)
        c.drawString(20 * mm, y, roll["roll_no"])
        c.drawString(120 * mm, y, f"{roll['length_meters']:.2f}")

    y -= 4 * mm
    c.line(20 * mm, y, 190 * mm, y)
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    c.drawString(120 * mm, y, f"Rate: Rs {data['unit_price']:.2f}/m")
    y -= 6 * mm
    c.drawString(120 * mm, y, f"Subtotal: Rs {data['subtotal']:.2f}")
    y -= 6 * mm
    c.drawString(120 * mm, y, f"Tax: Rs {data['tax']:.2f}")
    y -= 6 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(120 * mm, y, f"Total: Rs {data['total']:.2f}")

    c.showPage()
    c.save()
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename={data['invoice_no']}.pdf"
        },
    )

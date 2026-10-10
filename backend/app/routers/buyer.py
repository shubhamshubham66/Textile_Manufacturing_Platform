"""Buyer portal — scene 4. Buyers check their own order status and invoices.

ALL endpoints use `get_current_buyer` and scope every query to the logged-in
buyer's `buyer_id`. A buyer can never see another buyer's data: single-resource
lookups that don't belong to the buyer return 404 (so existence isn't leaked).

  GET /api/buyer/orders              my orders with stage + progress + ETA
  GET /api/buyer/orders/{id}         track one of MY orders (404 if not mine)
  GET /api/buyer/invoices            my invoices
  GET /api/buyer/invoices/{id}/pdf   my invoice as PDF (404 if not mine)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_buyer
from app.models import Dispatch, Invoice, Order, User
from app.services.production import order_progress_percent

router = APIRouter(prefix="/api/buyer", tags=["buyer"])

# Map internal order status -> buyer-facing stage. Also expose the ordered list of
# stages so the UI can draw a stepper.
STAGE_FLOW = ["Confirmed", "Weaving", "Dyeing", "Checking", "Ready to ship", "Shipped"]

STATUS_TO_STAGE = {
    "draft": "Confirmed",          # buyer sees it as accepted/confirmed
    "confirmed": "Confirmed",
    "in_production": "Weaving",
    "in_quality": "Checking",
    "ready_to_ship": "Ready to ship",
    "dispatched": "Shipped",
    "closed": "Shipped",
}


def _stage_index(stage: str) -> int:
    try:
        return STAGE_FLOW.index(stage)
    except ValueError:
        return 0


@router.get("/orders")
def my_orders(
    buyer: User = Depends(get_current_buyer),
    db: Session = Depends(get_db),
):
    orders = (
        db.query(Order)
        .filter(Order.buyer_id == buyer.buyer_id)  # scoped to this buyer
        .order_by(Order.id.desc())
        .all()
    )
    out = []
    for o in orders:
        stage = STATUS_TO_STAGE.get(o.status, "Confirmed")
        out.append(
            {
                "id": o.id,
                "order_no": o.order_no,
                "fabric_type": o.fabric_type,
                "colour": o.colour,
                "quantity_meters": float(o.quantity_meters),
                "status": o.status,
                "stage": stage,
                "stage_index": _stage_index(stage),
                "progress_percent": order_progress_percent(db, o),
                "expected_delivery": o.deadline.isoformat() if o.deadline else None,
            }
        )
    return out


@router.get("/orders/{order_id}")
def track_order(
    order_id: int,
    buyer: User = Depends(get_current_buyer),
    db: Session = Depends(get_db),
):
    # Scope to the buyer: an order that isn't theirs is reported as 404, so a
    # buyer cannot even probe for another buyer's order ids.
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.buyer_id == buyer.buyer_id)
        .first()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    stage = STATUS_TO_STAGE.get(order.status, "Confirmed")
    return {
        "id": order.id,
        "order_no": order.order_no,
        "fabric_type": order.fabric_type,
        "colour": order.colour,
        "quantity_meters": float(order.quantity_meters),
        "status": order.status,
        "stage": stage,
        "stage_index": _stage_index(stage),
        "stage_flow": STAGE_FLOW,
        "progress_percent": order_progress_percent(db, order),
        "expected_delivery": order.deadline.isoformat() if order.deadline else None,
    }


@router.get("/invoices")
def my_invoices(
    buyer: User = Depends(get_current_buyer),
    db: Session = Depends(get_db),
):
    invoices = (
        db.query(Invoice)
        .filter(Invoice.buyer_id == buyer.buyer_id)  # scoped to this buyer
        .order_by(Invoice.id.desc())
        .all()
    )
    out = []
    for inv in invoices:
        order = db.query(Order).filter(Order.id == inv.order_id).first()
        out.append(
            {
                "id": inv.id,
                "invoice_no": inv.invoice_no,
                "order_no": order.order_no if order else "",
                "subtotal": float(inv.subtotal),
                "tax": float(inv.tax),
                "total": float(inv.total),
                "status": inv.status,
                "created_at": inv.created_at.isoformat(),
            }
        )
    return out


@router.get("/invoices/{invoice_id}/pdf")
def my_invoice_pdf(
    invoice_id: int,
    buyer: User = Depends(get_current_buyer),
    db: Session = Depends(get_db),
):
    # Scoped: only the buyer's own invoice; otherwise 404.
    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.buyer_id == buyer.buyer_id)
        .first()
    )
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Reuse the dispatch invoice payload + PDF builder for a consistent document.
    from app.routers.dispatch import _invoice_payload

    data = _invoice_payload(db, invoice.id)

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="PDF generation requires reportlab (pip install reportlab)",
        )

    import io

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
    y -= 10 * mm
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
    y -= 8 * mm
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
        headers={"Content-Disposition": f"inline; filename={data['invoice_no']}.pdf"},
    )

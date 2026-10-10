"""Buyer portal — scene 4. Buyers check their own order status and invoices.

ALL endpoints use `get_current_buyer` and scope every query to the logged-in
buyer's `buyer_id`. A buyer can never see another buyer's data: single-resource
lookups that don't belong to the buyer return 404 (so existence isn't leaked).

  GET /api/buyer/orders              my orders with stage + progress + ETA
  GET /api/buyer/orders/{id}         track one of MY orders (404 if not mine)
  POST /api/buyer/orders             request a new order (goes to the Supermanager)
  PUT  /api/buyer/orders/{id}        answer a clarification and resubmit
  GET /api/buyer/invoices            my invoices
  GET /api/buyer/invoices/{id}/pdf   my invoice as PDF (404 if not mine)
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_buyer
from app.models import (
    Buyer,
    Dispatch,
    Invoice,
    Notification,
    Order,
    OrderChangeRequest,
    OrderItem,
    Payment,
    Product,
    User,
)
from app.services.production import order_display_progress

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

# Statuses before the mill has accepted the order, shown as a label not a stage.
REVIEW_LABEL = {
    "draft": "Under review",
    "pending_review": "Under review",
    "clarification": "Needs your reply",
    "rejected": "Not accepted",
    "cancelled": "Cancelled",
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
                "progress_percent": order_display_progress(db, o),
                "expected_delivery": o.deadline.isoformat() if o.deadline else None,
                "review_label": REVIEW_LABEL.get(o.status),
                "review_note": o.review_note if o.status in ("clarification", "rejected") else None,
                "buyer_note": o.buyer_note,
            }
        )
    return out


class OrderRequest(BaseModel):
    fabric_type: str = Field(min_length=1, max_length=80)
    colour: str = Field(min_length=1, max_length=60)
    quantity_meters: float = Field(gt=0, le=1_000_000)
    deadline: date
    note: str | None = Field(default=None, max_length=500)
    product_id: int | None = None

    @field_validator("fabric_type", "colour")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v

    @field_validator("deadline")
    @classmethod
    def _future(cls, v: date) -> date:
        if v <= date.today():
            raise ValueError("deadline must be after today")
        return v


@router.post("/orders", status_code=201)
def request_order(
    body: OrderRequest,
    buyer: User = Depends(get_current_buyer),
    db: Session = Depends(get_db),
):
    """A buyer asks for an order. It waits as 'pending_review' until the
    Supermanager sets the rate and confirms, rejects or asks a question.

    Notifies the Supermanager and Sales & Dispatch manager, and blocks an
    obvious duplicate (same fabric/colour/qty submitted in the last minute)."""
    from datetime import timedelta

    from app.routers.orders import _next_order_no, _required_kg

    # If placing against a catalogue product, enforce its minimum order quantity.
    if body.product_id is not None:
        p = db.get(Product, body.product_id)
        if p is None or not p.is_available:
            raise HTTPException(400, "Unknown product")
        if float(p.min_order_meters or 0) > 0 and body.quantity_meters < float(p.min_order_meters):
            raise HTTPException(400, f"Minimum order for {p.name} is {float(p.min_order_meters):,.0f} m")

    recent_cut = _now() - timedelta(minutes=1)
    dup = (
        db.query(Order)
        .filter(Order.buyer_id == buyer.buyer_id,
                func.lower(Order.fabric_type) == body.fabric_type.strip().lower(),
                func.lower(Order.colour) == body.colour.strip().lower(),
                Order.quantity_meters == body.quantity_meters,
                Order.created_at >= recent_cut)
        .first()
    )
    if dup is not None:
        raise HTTPException(409, "This looks like a duplicate of an order you just submitted.")

    order = Order(order_no=_next_order_no(db), buyer_id=buyer.buyer_id,
                  fabric_type=body.fabric_type, colour=body.colour,
                  quantity_meters=body.quantity_meters, unit="meters", unit_price=0,
                  deadline=body.deadline, status="pending_review",
                  buyer_note=(body.note or "").strip() or None)
    db.add(order)
    db.flush()
    db.add(OrderItem(order_id=order.id, yarn_type=f"{body.fabric_type} yarn", colour=body.colour,
                     required_qty_kg=_required_kg(body.quantity_meters), allocated_qty_kg=0))
    # Notify the Supermanager and Sales & Dispatch manager of the new request.
    b = db.get(Buyer, buyer.buyer_id)
    for role in (rbac.ROLE_MANAGER, rbac.ROLE_SALES_MANAGER):
        db.add(Notification(to_role=role, kind="info",
                            title=f"New order request {order.order_no}",
                            body=f"{b.name if b else ''}: {body.fabric_type} {body.colour} · {body.quantity_meters:,.0f} m",
                            from_user_name=b.name if b else "Buyer"))
    db.commit()
    return {"id": order.id, "order_no": order.order_no, "status": order.status}


@router.put("/orders/{order_id}")
def resubmit_order(
    order_id: int,
    body: OrderRequest,
    buyer: User = Depends(get_current_buyer),
    db: Session = Depends(get_db),
):
    """Answer the Supermanager's question: update the request and send it back."""
    from app.routers.orders import _required_kg

    order = db.query(Order).filter(Order.id == order_id, Order.buyer_id == buyer.buyer_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != "clarification":
        raise HTTPException(status_code=409, detail="Only an order that needs your reply can be changed")
    order.fabric_type, order.colour = body.fabric_type, body.colour
    order.quantity_meters, order.deadline = body.quantity_meters, body.deadline
    order.buyer_note = (body.note or "").strip() or None
    order.status = "pending_review"
    item = db.query(OrderItem).filter(OrderItem.order_id == order.id).first()
    if item is not None:
        item.colour = body.colour
        item.required_qty_kg = _required_kg(body.quantity_meters)
    db.commit()
    return {"id": order.id, "order_no": order.order_no, "status": order.status}


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
        "progress_percent": order_display_progress(db, order),
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


# --------------------------------------------------------------------------- #
# Buyer Dashboard (cards + lists) — all scoped to the logged-in buyer
# --------------------------------------------------------------------------- #
from datetime import datetime, timezone  # noqa: E402

from sqlalchemy import func  # noqa: E402

from app import rbac  # noqa: E402


def _now():
    return datetime.now(timezone.utc)


def _f(v) -> float:
    return round(float(v or 0), 2)


@router.get("/dashboard")
def buyer_dashboard(buyer: User = Depends(get_current_buyer), db: Session = Depends(get_db)):
    orders = db.query(Order).filter(Order.buyer_id == buyer.buyer_id).all()
    counts = {}
    for o in orders:
        counts[o.status] = counts.get(o.status, 0) + 1

    def c(*statuses):
        return sum(counts.get(s, 0) for s in statuses)

    cards = {
        "my_orders": len(orders),
        "pending": c("pending_review", "draft", "clarification"),
        "in_production": c("in_production"),
        "qc_status": c("in_quality"),
        "ready_for_dispatch": c("ready_to_ship"),
        "dispatched": c("dispatched", "closed"),
    }
    # Recent orders (buyer-facing stage).
    recent = sorted(orders, key=lambda o: o.id, reverse=True)[:6]
    recent_rows = []
    for o in recent:
        stage = STATUS_TO_STAGE.get(o.status, "Confirmed")
        recent_rows.append({
            "id": o.id, "order_no": o.order_no, "fabric_type": o.fabric_type, "colour": o.colour,
            "quantity_meters": _f(o.quantity_meters), "status": o.status,
            "stage": stage, "review_label": REVIEW_LABEL.get(o.status),
            "progress_percent": order_display_progress(db, o),
            "expected_delivery": o.deadline.isoformat() if o.deadline else None,
        })
    # Outstanding payment total (buyer's own invoices).
    outstanding = 0.0
    for inv in db.query(Invoice).filter(Invoice.buyer_id == buyer.buyer_id).all():
        paid = float(
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.invoice_id == inv.id, Payment.direction == "incoming", Payment.voided_at.is_(None))
            .scalar() or 0
        )
        outstanding += max(0.0, float(inv.total or 0) - paid)
    return {"cards": cards, "recent_orders": recent_rows, "outstanding_payment": round(outstanding, 2)}


# --------------------------------------------------------------------------- #
# Browse Products + Product Specifications
# --------------------------------------------------------------------------- #
def _product_row(p: Product) -> dict:
    return {
        "id": p.id, "name": p.name, "fabric_type": p.fabric_type, "colour": p.colour,
        "gsm": p.gsm, "width_inch": _f(p.width_inch) if p.width_inch is not None else None,
        "composition": p.composition, "finish": p.finish, "description": p.description,
        "price_per_meter": _f(p.price_per_meter), "min_order_meters": _f(p.min_order_meters),
        "lead_time_days": p.lead_time_days, "is_available": bool(p.is_available),
    }


@router.get("/products")
def list_products(buyer: User = Depends(get_current_buyer), db: Session = Depends(get_db)):
    rows = db.query(Product).filter(Product.is_available.is_(True)).order_by(Product.fabric_type, Product.colour).all()
    return {"products": [_product_row(p) for p in rows]}


@router.get("/products/{product_id}")
def product_detail(product_id: int, buyer: User = Depends(get_current_buyer), db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if p is None or not p.is_available:
        raise HTTPException(404, "Product not found")
    return _product_row(p)


# --------------------------------------------------------------------------- #
# Delivery History (buyer's own dispatches)
# --------------------------------------------------------------------------- #
@router.get("/deliveries")
def my_deliveries(buyer: User = Depends(get_current_buyer), db: Session = Depends(get_db)):
    rows = (
        db.query(Dispatch)
        .filter(Dispatch.buyer_id == buyer.buyer_id)
        .order_by(Dispatch.id.desc())
        .all()
    )
    out = []
    for d in rows:
        order = db.get(Order, d.order_id)
        out.append({
            "dispatch_no": d.dispatch_no,
            "order_no": order.order_no if order else "",
            "total_rolls": d.total_rolls,
            "total_meters": _f(d.total_meters),
            "status": "Delivered" if getattr(d, "delivered_at", None) else "In transit",
            "vehicle_no": getattr(d, "vehicle_no", None),
            "transporter": getattr(d, "transporter", None),
            "dispatched_at": d.dispatched_at.isoformat() if d.dispatched_at else None,
            "delivered_at": d.delivered_at.isoformat() if getattr(d, "delivered_at", None) else None,
        })
    return {"deliveries": out}


# --------------------------------------------------------------------------- #
# Cancellation / modification requests (never auto-changes a confirmed order)
# --------------------------------------------------------------------------- #
class ChangeRequestIn(BaseModel):
    kind: str = Field(pattern="^(cancel|modify)$")
    message: str = Field(min_length=3, max_length=1000)


@router.get("/orders/{order_id}/change-requests")
def list_change_requests(order_id: int, buyer: User = Depends(get_current_buyer), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id, Order.buyer_id == buyer.buyer_id).first()
    if order is None:
        raise HTTPException(404, "Order not found")
    rows = (
        db.query(OrderChangeRequest)
        .filter(OrderChangeRequest.order_id == order_id)
        .order_by(OrderChangeRequest.id.desc())
        .all()
    )
    return {"requests": [{"id": r.id, "kind": r.kind, "message": r.message, "status": r.status,
                          "decision_note": r.decision_note,
                          "created_at": r.created_at.isoformat() if r.created_at else None} for r in rows]}


@router.post("/orders/{order_id}/request-change", status_code=201)
def request_change(order_id: int, body: ChangeRequestIn, buyer: User = Depends(get_current_buyer),
                   db: Session = Depends(get_db)):
    """Submit a cancel/modify request. It does NOT change the order — a manager
    reviews it. Duplicate open request of the same kind is rejected."""
    order = db.query(Order).filter(Order.id == order_id, Order.buyer_id == buyer.buyer_id).first()
    if order is None:
        raise HTTPException(404, "Order not found")
    if order.status in ("dispatched", "closed", "cancelled", "rejected"):
        raise HTTPException(409, "This order can no longer be changed")
    dup = (
        db.query(OrderChangeRequest)
        .filter(OrderChangeRequest.order_id == order_id, OrderChangeRequest.kind == body.kind,
                OrderChangeRequest.status == "open")
        .first()
    )
    if dup is not None:
        raise HTTPException(409, f"You already have an open {body.kind} request for this order")
    req = OrderChangeRequest(order_id=order.id, buyer_id=buyer.buyer_id, kind=body.kind,
                             message=body.message.strip(), status="open")
    db.add(req)
    label = "cancel" if body.kind == "cancel" else "modify"
    b = db.get(Buyer, buyer.buyer_id)
    for role in (rbac.ROLE_MANAGER, rbac.ROLE_SALES_MANAGER):
        db.add(Notification(to_role=role, kind="info",
                            title=f"Buyer wants to {label} {order.order_no}",
                            body=f"{b.name if b else ''}: {body.message.strip()}",
                            from_user_name=b.name if b else "Buyer"))
    db.commit()
    return {"ok": True, "order_no": order.order_no, "kind": body.kind, "status": "open"}


# --------------------------------------------------------------------------- #
# Contact Sales & Dispatch (inquiry)
# --------------------------------------------------------------------------- #
class InquiryIn(BaseModel):
    subject: str = Field(min_length=2, max_length=160)
    message: str = Field(min_length=3, max_length=1000)
    order_id: int | None = None


@router.post("/inquiries", status_code=201)
def contact_sales(body: InquiryIn, buyer: User = Depends(get_current_buyer), db: Session = Depends(get_db)):
    b = db.get(Buyer, buyer.buyer_id)
    ref = ""
    if body.order_id is not None:
        order = db.query(Order).filter(Order.id == body.order_id, Order.buyer_id == buyer.buyer_id).first()
        if order is None:
            raise HTTPException(404, "Order not found")
        ref = f" ({order.order_no})"
    db.add(Notification(to_role=rbac.ROLE_SALES_MANAGER, kind="info",
                        title=f"Buyer inquiry: {body.subject}{ref}",
                        body=f"{b.name if b else ''}: {body.message.strip()}",
                        from_user_name=b.name if b else "Buyer"))
    db.commit()
    return {"ok": True, "sent": True}


# --------------------------------------------------------------------------- #
# Notifications (buyer's own)
# --------------------------------------------------------------------------- #
@router.get("/notifications")
def buyer_notifications(buyer: User = Depends(get_current_buyer), db: Session = Depends(get_db)):
    rows = (
        db.query(Notification)
        .filter((Notification.to_user_id == buyer.id) | (Notification.to_role == rbac.ROLE_BUYER))
        .order_by(Notification.id.desc())
        .limit(50)
        .all()
    )
    return {
        "notifications": [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body,
                           "from": n.from_user_name,
                           "created_at": n.created_at.isoformat() if n.created_at else None,
                           "read": n.read_at is not None} for n in rows],
        "unread": sum(1 for n in rows if n.read_at is None),
    }


@router.post("/notifications/{nid}/read")
def buyer_mark_read(nid: int, buyer: User = Depends(get_current_buyer), db: Session = Depends(get_db)):
    n = db.get(Notification, nid)
    if n is None or (n.to_user_id != buyer.id and n.to_role != rbac.ROLE_BUYER):
        raise HTTPException(404, "Notification not found")
    if n.read_at is None:
        n.read_at = datetime.utcnow()
        db.commit()
    return {"ok": True, "id": nid}


# --------------------------------------------------------------------------- #
# My Profile (buyer's own record; read-only here)
# --------------------------------------------------------------------------- #
@router.get("/profile")
def buyer_profile(buyer: User = Depends(get_current_buyer), db: Session = Depends(get_db)):
    b = db.get(Buyer, buyer.buyer_id)
    orders = db.query(Order).filter(Order.buyer_id == buyer.buyer_id).count()
    return {
        "name": b.name if b else buyer.name,
        "contact_person": b.contact_person if b else None,
        "phone": b.phone if b else None,
        "email": (b.email if b else None) or buyer.email,
        "address": b.address if b else None,
        "credit_limit": _f(b.credit_limit) if b else 0,
        "total_orders": orders,
        "login_email": buyer.email,
    }

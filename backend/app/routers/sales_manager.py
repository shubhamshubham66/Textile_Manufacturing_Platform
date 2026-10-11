"""Sales & Dispatch Manager control panel — /api/sales/*.

The Sales & Dispatch Manager (role "sales_manager") receives QC-approved stock,
matches it to confirmed buyer orders, plans dispatches, generates delivery
challans, confirms deliveries and hands off to Accounts for payment follow-up.

  Dashboard            GET  /api/sales/dashboard
  Buyer Orders         GET  /api/sales/orders
  Buyer Management     GET  /api/sales/buyers
  Order Tracking       GET  /api/sales/tracking  (+ /tracking/{id})
  QC-Approved Stock    GET  /api/sales/stock
  Dispatch Planning    GET  /api/sales/planning  (+ /orders/{id}/pickable)
  Create Challan       POST /api/sales/dispatch          (plan + challan in one txn)
  Dispatch History     GET  /api/sales/history
  Invoice Details      GET  /api/sales/invoices (read-only) (+ /invoices/{id})
  Delivery Confirm     GET  /api/sales/deliveries
                       POST /api/sales/dispatch/{id}/deliver
                       POST /api/sales/dispatch/{id}/status  (packed/loaded/shipped)
  Notifications        GET  /api/sales/notifications
                       POST /api/sales/notifications/{id}/read
  Reports              GET  /api/sales/reports
  Activity Logs        GET  /api/sales/activity

PERMISSIONS (backend-enforced):
  - Every endpoint is guarded by require_resource("sd_*"); only this role passes.
  - Dispatch reuses the existing atomic confirm_dispatch, so only QC-approved
    ('pass') rolls can go out, double dispatch is blocked (app check + UNIQUE
    dispatch_items.roll_id), and quantities can never exceed approved stock.
  - This role cannot confirm buyer orders (Supermanager), approve/reject QC
    (QC inspector) or edit payments/financials (accountant) — no such endpoint
    exists here. Buyer payments are read-only.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import rbac
from app.database import get_db
from app.deps import get_current_user, require_resource
from app.models import (
    ActivityLog,
    Buyer,
    Dispatch,
    Invoice,
    Notification,
    Order,
    Roll,
    User,
)
from app.services import sales_manager as sm
from app.services import order_payments as op
from app.services.dispatch import confirm_dispatch

router = APIRouter(prefix="/api/sales", tags=["sales-dispatch-manager"])

DISPATCH_STATUSES = ("packed", "loaded", "shipped")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _log(db: Session, me: User, category: str, action: str, details: str) -> None:
    db.add(
        ActivityLog(
            user_id=me.id, user_name=me.name, user_role=me.role.name,
            category=category, action=action, details=details[:2000],
        )
    )


def _notify(db: Session, to_role: str, title: str, body: str, me: User, kind: str = "info") -> None:
    db.add(
        Notification(
            to_role=to_role, kind=kind, title=title[:200], body=body, from_user_name=me.name
        )
    )


def _get_order(db: Session, order_id: int) -> Order:
    o = db.get(Order, order_id)
    if o is None:
        raise HTTPException(404, "Order not found")
    return o


def _get_dispatch(db: Session, dispatch_id: int) -> Dispatch:
    d = db.get(Dispatch, dispatch_id)
    if d is None:
        raise HTTPException(404, "Dispatch not found")
    return d


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@router.get("/dashboard")
def dashboard(_=Depends(require_resource("sd_dashboard")), db: Session = Depends(get_db)):
    return sm.dashboard(db)


# --------------------------------------------------------------------------- #
# Buyer Orders (confirmed by the Supermanager; read-only here)
# --------------------------------------------------------------------------- #
@router.get("/orders")
def orders(
    status: str | None = None,
    q: str | None = None,
    _=Depends(require_resource("sd_orders")),
    db: Session = Depends(get_db),
):
    query = db.query(Order).filter(Order.status.in_(sm.SALES_ORDERS))
    if status:
        query = query.filter(Order.status == status)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(Order.order_no.ilike(like), Order.fabric_type.ilike(like), Order.colour.ilike(like)))
    rows = query.order_by(Order.deadline.is_(None), Order.deadline, Order.id).all()
    return {
        "orders": [sm.order_row(db, o) for o in rows],
        "statuses": [{"key": k, "label": v} for k, v in sm.STATUS_LABEL.items()],
        "note": "Orders are confirmed by the Supermanager. You plan dispatch and delivery; you cannot confirm or edit an order.",
    }


# --------------------------------------------------------------------------- #
# Buyer Management (view + contact details; read-only on the account itself)
# --------------------------------------------------------------------------- #
@router.get("/buyers")
def buyers(_=Depends(require_resource("sd_buyers")), db: Session = Depends(get_db)):
    rows = []
    for b in db.query(Buyer).order_by(Buyer.name).all():
        orders = db.query(Order).filter(Order.buyer_id == b.id).all()
        active = [o for o in orders if o.status in sm.SALES_ORDERS and o.status != "closed"]
        delivered = [o for o in orders if o.status == "closed"]
        dues = sm._f(
            db.query(func.coalesce(func.sum(Invoice.total), 0)).filter(Invoice.buyer_id == b.id).scalar()
        )
        rows.append(
            {
                "id": b.id,
                "name": b.name,
                "contact_person": b.contact_person,
                "phone": b.phone,
                "email": b.email,
                "address": b.address,
                "total_orders": len(orders),
                "active_orders": len(active),
                "delivered_orders": len(delivered),
                "invoiced_total": dues,
            }
        )
    return {"buyers": rows, "note": "Buyer master records are managed by the owner; shown here for dispatch & delivery contact."}


# --------------------------------------------------------------------------- #
# Order Status Tracking
# --------------------------------------------------------------------------- #
@router.get("/tracking")
def tracking(_=Depends(require_resource("sd_tracking")), db: Session = Depends(get_db)):
    orders = (
        db.query(Order)
        .filter(Order.status.in_(sm.SALES_ORDERS))
        .order_by(Order.id.desc())
        .all()
    )
    stages = ["Confirmed", "In Production", "QC Pending", "Ready for Dispatch",
              "Partially Dispatched", "Dispatched", "Delivered"]
    return {"orders": [sm.order_row(db, o) for o in orders], "stages": stages}


# --------------------------------------------------------------------------- #
# QC-Approved Finished Stock
# --------------------------------------------------------------------------- #
@router.get("/stock")
def stock(_=Depends(require_resource("sd_stock")), db: Session = Depends(get_db)):
    """Rolls that passed QC and are on the shelf (not dispatched), grouped by
    order. Only this stock can ever be dispatched."""
    rows = (
        db.query(Order)
        .join(Roll, Roll.order_id == Order.id)
        .filter(Roll.status == "pass")
        .distinct()
        .all()
    )
    out = []
    for o in rows:
        approved = sm.approved_rolls_for_order(db, o.id)
        out.append(
            {
                "order_no": o.order_no,
                "buyer": o.buyer.name if o.buyer else "",
                "fabric": f"{o.fabric_type} {o.colour}",
                "rolls": len(approved),
                "meters": round(sum(float(r.length_meters or 0) for r in approved), 2),
                "roll_nos": [r.roll_no for r in approved],
            }
        )
    total_rolls = sum(r["rolls"] for r in out)
    total_meters = round(sum(r["meters"] for r in out), 2)
    return {
        "stock": out,
        "total_rolls": total_rolls,
        "total_meters": total_meters,
        "rule": "Only QC-approved (passed) rolls appear here and can be dispatched. Rework/rejected rolls are excluded.",
    }


# --------------------------------------------------------------------------- #
# Dispatch Planning
# --------------------------------------------------------------------------- #
@router.get("/planning")
def planning(_=Depends(require_resource("sd_planning")), db: Session = Depends(get_db)):
    rows = (
        db.query(Order)
        .join(Roll, Roll.order_id == Order.id)
        .filter(Roll.status == "pass")
        .distinct()
        .all()
    )
    orders = []
    for o in rows:
        r = sm.order_row(db, o)
        if r["rolls_ready"] > 0:
            orders.append(r)
    orders.sort(key=lambda r: (r["deadline"] or "9999", r["order_no"]))
    return {"orders": orders, "note": "Pick an order with approved stock, choose rolls and record logistics to create a dispatch + challan."}


@router.get("/orders/{order_id}/pickable")
def pickable(order_id: int, _=Depends(require_resource("sd_planning")), db: Session = Depends(get_db)):
    o = _get_order(db, order_id)
    rolls = sm.approved_rolls_for_order(db, o.id)
    return {
        "order_id": o.id,
        "order_no": o.order_no,
        "buyer": o.buyer.name if o.buyer else "",
        "buyer_address": (o.buyer.address if o.buyer else "") or "",
        "unit_price": sm._f(o.unit_price),
        "quantity_meters": sm._f(o.quantity_meters),
        "dispatched_meters": sm._dispatched_meters(db, o.id),
        "rolls": [{"id": r.id, "roll_no": r.roll_no, "length_meters": sm._f(r.length_meters)} for r in rolls],
    }


# --------------------------------------------------------------------------- #
# Create dispatch + delivery challan (reuses the atomic confirm_dispatch)
# --------------------------------------------------------------------------- #
class DispatchIn(BaseModel):
    order_id: int
    roll_ids: list[int] = Field(min_length=1)
    vehicle_no: str | None = Field(default=None, max_length=40)
    transporter: str | None = Field(default=None, max_length=120)
    driver_phone: str | None = Field(default=None, max_length=30)
    delivery_address: str | None = Field(default=None, max_length=500)
    delivery_note: str | None = Field(default=None, max_length=500)
    partial: bool = False  # acknowledge this is a partial dispatch


@router.post("/dispatch", status_code=201)
def create_dispatch(
    body: DispatchIn,
    me: User = Depends(get_current_user),
    _=Depends(require_resource("sd_challan")),
    db: Session = Depends(get_db),
):
    o = _get_order(db, body.order_id)
    approved_ids = {r.id for r in sm.approved_rolls_for_order(db, o.id)}
    # Guard: every chosen roll must be currently QC-approved & on the shelf.
    bad = [rid for rid in body.roll_ids if rid not in approved_ids]
    if bad:
        raise HTTPException(400, "Some selected rolls are not QC-approved or already dispatched. Refresh and try again.")
    # Partial dispatch is allowed only when explicitly acknowledged.
    is_partial = len(body.roll_ids) < len(approved_ids) or sm._dispatched_meters(db, o.id) > 0
    if is_partial and not body.partial:
        raise HTTPException(
            409,
            "This is a partial dispatch (not all approved stock selected). Tick 'partial dispatch' to proceed.",
        )

    # Atomic: validates 'pass'-only, marks dispatched, creates dispatch+invoice,
    # blocks double dispatch via the UNIQUE roll constraint.
    result = confirm_dispatch(db, body.order_id, body.roll_ids)

    # Attach challan + logistics to the dispatch just created, and set the final
    # order status (partial vs fully dispatched).
    d = db.get(Dispatch, result["dispatch_id"])
    d.challan_no = f"CH-{d.id:04d}"
    d.vehicle_no = (body.vehicle_no or "").strip() or None
    d.transporter = (body.transporter or "").strip() or None
    d.driver_phone = (body.driver_phone or "").strip() or None
    d.delivery_address = (body.delivery_address or "").strip() or (o.buyer.address if o.buyer else None)
    d.delivery_note = (body.delivery_note or "").strip() or None
    d.dispatched_by_user_id = me.id
    d.status = "shipped"

    # Remaining approved stock after this dispatch decides the order status.
    remaining_after = [r for r in sm.approved_rolls_for_order(db, o.id)]
    produced_remaining = max(0.0, float(o.quantity_meters or 0) - sm._dispatched_meters(db, o.id))
    if remaining_after or produced_remaining > 0.5:
        o.status = "partially_dispatched"
    else:
        o.status = "dispatched"

    # Notifications: Supermanager + store/accounts that a dispatch went out.
    _notify(db, rbac.ROLE_MANAGER, f"Dispatch {d.dispatch_no} created for {o.order_no}",
            f"{d.total_rolls} rolls / {sm._f(d.total_meters):,.0f} m to {o.buyer.name if o.buyer else ''}"
            + (f" · vehicle {d.vehicle_no}" if d.vehicle_no else ""), me)
    _notify(db, rbac.ROLE_ACCOUNTANT, f"Invoice {result['invoice_no']} raised ({o.order_no})",
            f"Dispatch {d.dispatch_no} · total ₹{result['total']:,.0f}", me)
    _notify(db, rbac.ROLE_ACCOUNTS_MANAGER, f"Invoice {result['invoice_no']} raised ({o.order_no})",
            f"Dispatch {d.dispatch_no} · total ₹{result['total']:,.0f} · follow up buyer payment", me)
    _log(db, me, "dispatch", "created",
         f"{d.dispatch_no} ({d.challan_no}) for {o.order_no}: {d.total_rolls} rolls / {sm._f(d.total_meters):,.0f} m")
    db.commit()
    return {
        "ok": True,
        "dispatch_no": d.dispatch_no,
        "challan_no": d.challan_no,
        "invoice_no": result["invoice_no"],
        "invoice_id": result["invoice_id"],
        "order_status": o.status,
        "total_rolls": d.total_rolls,
        "total_meters": sm._f(d.total_meters),
    }


# --------------------------------------------------------------------------- #
# Dispatch History
# --------------------------------------------------------------------------- #
@router.get("/history")
def history(_=Depends(require_resource("sd_history")), db: Session = Depends(get_db)):
    rows = db.query(Dispatch).order_by(Dispatch.id.desc()).all()
    return {"dispatches": [sm.dispatch_row(db, d) for d in rows]}


# --------------------------------------------------------------------------- #
# Invoice Details (read-only)
# --------------------------------------------------------------------------- #
@router.get("/invoices")
def invoices(_=Depends(require_resource("sd_invoices")), db: Session = Depends(get_db)):
    rows = db.query(Invoice).order_by(Invoice.id.desc()).all()
    out = []
    for inv in rows:
        order = db.get(Order, inv.order_id)
        buyer = db.get(Buyer, inv.buyer_id)
        paid = sm._invoice_paid(db, inv.id)
        out.append(
            {
                "id": inv.id,
                "invoice_no": inv.invoice_no,
                "order_no": order.order_no if order else "",
                "buyer": buyer.name if buyer else "",
                "subtotal": sm._f(inv.subtotal),
                "tax": sm._f(inv.tax),
                "total": sm._f(inv.total),
                "paid": paid,
                "balance": round(float(inv.total or 0) - paid, 2),
                "status": inv.status,
                "created_at": sm._iso(inv.created_at),
            }
        )
    return {"invoices": out, "note": "Read-only. Payment status is controlled by the accountant."}


@router.get("/invoices/{invoice_id}")
def invoice_detail(invoice_id: int, _=Depends(require_resource("sd_invoices")), db: Session = Depends(get_db)):
    # Reuse the dispatch invoice payload for a consistent document.
    from app.routers.dispatch import _invoice_payload

    return _invoice_payload(db, invoice_id)


# --------------------------------------------------------------------------- #
# Delivery Confirmation
# --------------------------------------------------------------------------- #
class DeliverIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)
    received_by: str | None = Field(default=None, max_length=120)


class DispatchStatusIn(BaseModel):
    status: str

    @classmethod
    def _check(cls, v):  # pragma: no cover - simple guard
        return v


@router.get("/deliveries")
def deliveries(_=Depends(require_resource("sd_delivery")), db: Session = Depends(get_db)):
    rows = db.query(Dispatch).order_by(Dispatch.id.desc()).all()
    pending = [sm.dispatch_row(db, d) for d in rows if d.delivered_at is None]
    done = [sm.dispatch_row(db, d) for d in rows if d.delivered_at is not None]
    return {"pending": pending, "delivered": done}


@router.post("/dispatch/{dispatch_id}/status")
def set_dispatch_status(
    dispatch_id: int,
    body: DispatchStatusIn,
    me: User = Depends(get_current_user),
    _=Depends(require_resource("sd_delivery")),
    db: Session = Depends(get_db),
):
    if body.status not in DISPATCH_STATUSES:
        raise HTTPException(400, f"status must be one of {', '.join(DISPATCH_STATUSES)}")
    d = _get_dispatch(db, dispatch_id)
    if d.delivered_at is not None:
        raise HTTPException(409, "This dispatch is already delivered")
    d.status = body.status
    _log(db, me, "dispatch", "status", f"{d.dispatch_no} → {body.status}")
    db.commit()
    return sm.dispatch_row(db, d)


@router.post("/dispatch/{dispatch_id}/deliver")
def confirm_delivery(
    dispatch_id: int,
    body: DeliverIn,
    me: User = Depends(get_current_user),
    _=Depends(require_resource("sd_delivery")),
    db: Session = Depends(get_db),
):
    d = _get_dispatch(db, dispatch_id)
    if d.delivered_at is not None:
        raise HTTPException(409, "This dispatch is already marked delivered")
    # Payment must be complete before goods are handed over.
    inv, due = op.dispatch_invoice_unpaid(db, d.id)
    if inv is not None and due > 0.5:
        db.commit()  # keep any advance just allocated
        raise HTTPException(
            409,
            f"Payment pending: ₹{due:,.2f} of {inv.invoice_no} is unpaid. "
            "Delivery can be confirmed only after Accounts confirms full payment.",
        )
    d.delivered_at = _now()
    d.status = "shipped"
    if body.note:
        d.delivery_note = (d.delivery_note or "") + (" | " if d.delivery_note else "") + body.note.strip()
    order = db.get(Order, d.order_id)
    # If the whole order has gone out and this is its last pending dispatch,
    # mark the order delivered (closed). Partial deliveries keep the order open.
    if order is not None:
        undelivered = (
            db.query(Dispatch)
            .filter(Dispatch.order_id == order.id, Dispatch.delivered_at.is_(None), Dispatch.id != d.id)
            .count()
        )
        remaining_stock = sm.approved_rolls_for_order(db, order.id)
        produced_remaining = max(0.0, float(order.quantity_meters or 0) - sm._dispatched_meters(db, order.id))
        if undelivered == 0 and not remaining_stock and produced_remaining <= 0.5:
            order.status = "closed"  # buyer sees "Delivered"
    # Notify Supermanager + Accounts for payment follow-up.
    buyer = db.get(Buyer, d.buyer_id)
    _notify(db, rbac.ROLE_MANAGER, f"Delivery confirmed: {d.dispatch_no}",
            f"{order.order_no if order else ''} delivered to {buyer.name if buyer else ''}", me, kind="info")
    for acct_role in (rbac.ROLE_ACCOUNTANT, rbac.ROLE_ACCOUNTS_MANAGER):
        _notify(db, acct_role, f"Delivered: {order.order_no if order else ''}",
                f"{d.dispatch_no} delivered · payment already settled", me, kind="info")
    _log(db, me, "dispatch", "delivered",
         f"{d.dispatch_no} delivered" + (f" (received by {body.received_by.strip()})" if body.received_by else ""))
    db.commit()
    return sm.dispatch_row(db, d)


# --------------------------------------------------------------------------- #
# Notifications
# --------------------------------------------------------------------------- #
@router.get("/notifications")
def notifications(_=Depends(require_resource("sd_notifications")), db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    rows = (
        db.query(Notification)
        .filter(or_(Notification.to_user_id == me.id, Notification.to_role == rbac.ROLE_SALES_MANAGER))
        .order_by(Notification.id.desc())
        .limit(50)
        .all()
    )
    return {
        "notifications": [
            {
                "id": n.id, "kind": n.kind, "title": n.title, "body": n.body,
                "from": n.from_user_name, "created_at": sm._iso(n.created_at),
                "read": n.read_at is not None,
            }
            for n in rows
        ],
        "unread": sum(1 for n in rows if n.read_at is None),
    }


@router.post("/notifications/{nid}/read")
def mark_read(nid: int, _=Depends(require_resource("sd_notifications")), db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    n = db.get(Notification, nid)
    if n is None or (n.to_user_id != me.id and n.to_role != rbac.ROLE_SALES_MANAGER):
        raise HTTPException(404, "Notification not found")
    if n.read_at is None:
        n.read_at = datetime.utcnow()
        db.commit()
    return {"ok": True, "id": nid}


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
@router.get("/reports")
def reports(
    start: date | None = None,
    end: date | None = None,
    _=Depends(require_resource("sd_reports")),
    db: Session = Depends(get_db),
):
    today = date.today()
    s = start or today.replace(day=1)
    e = end or today
    if e < s:
        raise HTTPException(400, "end must be on or after start")
    s_dt = datetime.combine(s, datetime.min.time())
    e_dt = datetime.combine(e, datetime.max.time())
    dispatches = db.query(Dispatch).filter(Dispatch.dispatched_at.between(s_dt, e_dt)).all()
    delivered = [d for d in dispatches if d.delivered_at is not None]
    # Per-buyer dispatch summary.
    by_buyer: dict[int, dict] = {}
    for d in dispatches:
        b = db.get(Buyer, d.buyer_id)
        row = by_buyer.setdefault(d.buyer_id, {"buyer": b.name if b else "", "dispatches": 0, "meters": 0.0})
        row["dispatches"] += 1
        row["meters"] = round(row["meters"] + float(d.total_meters or 0), 2)
    invoiced = db.query(func.coalesce(func.sum(Invoice.total), 0)).filter(
        Invoice.created_at.between(s_dt, e_dt)).scalar()
    return {
        "start": s.isoformat(),
        "end": e.isoformat(),
        "total_dispatches": len(dispatches),
        "total_meters": round(sum(float(d.total_meters or 0) for d in dispatches), 2),
        "delivered": len(delivered),
        "pending_delivery": len(dispatches) - len(delivered),
        "invoiced_total": sm._f(invoiced),
        "by_buyer": sorted(by_buyer.values(), key=lambda x: -x["meters"]),
        "dues": sm.buyer_dues(db),
    }


# --------------------------------------------------------------------------- #
# Activity Logs
# --------------------------------------------------------------------------- #
@router.get("/activity")
def activity(
    category: str | None = None,
    q: str | None = None,
    limit: int = Query(60, ge=1, le=200),
    _=Depends(require_resource("sd_activity")),
    db: Session = Depends(get_db),
):
    cats = ("dispatch", "order", "qc", "payment")
    query = db.query(ActivityLog).filter(ActivityLog.category.in_(cats))
    if category:
        query = query.filter(ActivityLog.category == category)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(ActivityLog.details.ilike(like), ActivityLog.user_name.ilike(like)))
    rows = query.order_by(ActivityLog.id.desc()).limit(limit).all()
    return {"rows": [sm.activity_row(a) for a in rows], "categories": list(cats)}

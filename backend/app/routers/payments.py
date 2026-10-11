"""Payments module — scene 6 (part 1): money in and out.

Owner + accountant (resource "payments"):
  GET  /api/payments                   list payments (in/out)
  POST /api/payments/buyer             record a buyer payment against an invoice
  POST /api/payments/supplier          pay a supplier (yarn bills)
  GET  /api/payments/dues              pending dues: buyers owe us, we owe suppliers
  GET  /api/payments/_meta             invoices + suppliers for the forms
  GET  /api/payments/requests          buyer payments waiting for confirmation
  POST /api/payments/requests/{id}/confirm   -> becomes a real incoming payment
  POST /api/payments/requests/{id}/reject    {reason}
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import order_payments as op
from app.deps import get_current_user, require_resource, require_roles
from app import rbac
from app.models import (
    Buyer,
    BuyerPaymentRequest,
    IdempotencyKey,
    Invoice,
    Notification,
    Order,
    Payment,
    PurchaseOrder,
    Supplier,
    User,
)

router = APIRouter(prefix="/api/payments", tags=["payments"])


def _replayed_payment(db: Session, scope: str, key: str | None):
    """Return the Payment a previous request with this (scope, key) created, or
    None if this is a fresh key. Used to make payment recording idempotent so a
    double-click or retry never creates a duplicate payment."""
    if not key:
        return None
    row = (
        db.query(IdempotencyKey)
        .filter(IdempotencyKey.scope == scope, IdempotencyKey.key == key)
        .first()
    )
    if row is None or row.result_id is None:
        return None
    return db.query(Payment).filter(Payment.id == row.result_id).first()


def _remember_key(db: Session, scope: str, key: str | None, user_id: int | None, result_id: int) -> None:
    """Record that (scope, key) produced `result_id`. Safe under a race: a
    concurrent duplicate hits the UNIQUE(scope, key) constraint and is ignored
    (the other request already recorded the same logical payment)."""
    if not key:
        return
    db.add(IdempotencyKey(scope=scope, key=key, user_id=user_id, result_id=result_id))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()

VALID_METHODS = ("cash", "bank", "upi")


# --------------------------- schemas --------------------------- #
class BuyerPaymentRequest(BaseModel):
    invoice_id: int
    amount: float = Field(gt=0)
    method: str = "bank"

    @field_validator("method")
    @classmethod
    def _m(cls, v: str) -> str:
        if v not in VALID_METHODS:
            raise ValueError(f"method must be one of {VALID_METHODS}")
        return v


class SupplierPaymentRequest(BaseModel):
    supplier_id: int
    amount: float = Field(gt=0)
    method: str = "bank"
    # Set true to deliberately pay MORE than the current outstanding bill
    # (an advance). Without it, overpaying a supplier is rejected.
    is_advance: bool = False

    @field_validator("method")
    @classmethod
    def _m(cls, v: str) -> str:
        if v not in VALID_METHODS:
            raise ValueError(f"method must be one of {VALID_METHODS}")
        return v


class VoidRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=255)

    @field_validator("reason")
    @classmethod
    def _r(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("reason must be at least 3 characters")
        return v


def _inr(v: float) -> str:
    """₹ with Indian digit grouping and 2 decimals: 1234567.5 -> ₹12,34,567.50."""
    neg = v < 0
    whole, frac = f"{abs(v):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{'−' if neg else ''}₹{whole}.{frac}"


def _invoice_paid_total(db: Session, invoice_id: int) -> float:
    total = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(
            Payment.direction == "incoming",
            Payment.invoice_id == invoice_id,
            Payment.voided_at.is_(None),
        )
        .scalar()
    )
    return float(total or 0)


def _supplier_outstanding(db: Session, supplier_id: int) -> float:
    """What we still owe a supplier: Σ(raised/received PO value) − Σ(payments)."""
    billed = (
        db.query(
            func.coalesce(
                func.sum(PurchaseOrder.quantity_kg * PurchaseOrder.unit_cost), 0
            )
        )
        .filter(
            PurchaseOrder.supplier_id == supplier_id,
            PurchaseOrder.status.in_(("raised", "received")),
        )
        .scalar()
        or 0
    )
    paid = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(
            Payment.direction == "outgoing",
            Payment.supplier_id == supplier_id,
            Payment.voided_at.is_(None),
        )
        .scalar()
        or 0
    )
    return round(float(billed) - float(paid), 2)


def _refresh_invoice_status(db: Session, invoice: Invoice) -> None:
    paid = _invoice_paid_total(db, invoice.id)
    total = float(invoice.total)
    if paid <= 0:
        invoice.status = "unpaid"
    elif paid + 0.001 < total:
        invoice.status = "part_paid"
    else:
        invoice.status = "paid"


# --------------------------- endpoints --------------------------- #
@router.get("/_meta")
def meta(
    _=Depends(require_resource("payments")),
    db: Session = Depends(get_db),
):
    invoices = db.query(Invoice).order_by(Invoice.id.desc()).all()
    suppliers = db.query(Supplier).order_by(Supplier.name).all()
    out_inv = []
    for inv in invoices:
        buyer = db.query(Buyer).filter(Buyer.id == inv.buyer_id).first()
        paid = _invoice_paid_total(db, inv.id)
        out_inv.append(
            {
                "id": inv.id,
                "invoice_no": inv.invoice_no,
                "buyer_name": buyer.name if buyer else "",
                "total": float(inv.total),
                "paid": round(paid, 2),
                "balance": round(float(inv.total) - paid, 2),
                "status": inv.status,
            }
        )
    return {
        "invoices": out_inv,
        "suppliers": [{"id": s.id, "name": s.name} for s in suppliers],
    }


@router.get("")
def list_payments(
    _=Depends(require_resource("payments")),
    db: Session = Depends(get_db),
):
    rows = db.query(Payment).order_by(Payment.id.desc()).all()
    out = []
    for p in rows:
        party = ""
        if p.buyer_id:
            b = db.query(Buyer).filter(Buyer.id == p.buyer_id).first()
            party = b.name if b else ""
        elif p.supplier_id:
            s = db.query(Supplier).filter(Supplier.id == p.supplier_id).first()
            party = s.name if s else ""
        voided_by = ""
        if p.voided_by_user_id:
            u = db.query(User).filter(User.id == p.voided_by_user_id).first()
            voided_by = u.name if u else ""
        out.append(
            {
                "id": p.id,
                "direction": p.direction,
                "party": party,
                "amount": float(p.amount),
                "method": p.method,
                "invoice_id": p.invoice_id,
                "paid_at": p.paid_at,
                "voided": p.voided_at is not None,
                "void_reason": p.void_reason,
                "voided_at": p.voided_at,
                "voided_by": voided_by,
            }
        )
    return out


@router.post("/buyer")
def record_buyer_payment(
    body: BuyerPaymentRequest,
    me: User = Depends(get_current_user),
    _=Depends(require_resource("payments")),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    invoice = db.query(Invoice).filter(Invoice.id == body.invoice_id).first()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Idempotency: if this exact request was already processed (double-click /
    # retry), return the original result instead of recording a second payment.
    prior = _replayed_payment(db, "payment:buyer", idempotency_key)
    if prior is not None:
        return {
            "ok": True,
            "invoice_no": invoice.invoice_no,
            "invoice_status": invoice.status,
            "paid_total": round(_invoice_paid_total(db, invoice.id), 2),
            "balance": round(float(invoice.total) - _invoice_paid_total(db, invoice.id), 2),
            "idempotent_replay": True,
        }

    already = _invoice_paid_total(db, invoice.id)
    balance = float(invoice.total) - already
    if balance <= 0:
        raise HTTPException(status_code=409, detail="Invoice is already fully paid")
    if body.amount - 0.001 > balance:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Amount {_inr(body.amount)} exceeds the outstanding balance "
                f"{_inr(balance)} on {invoice.invoice_no}."
            ),
        )

    payment = Payment(
        direction="incoming",
        buyer_id=invoice.buyer_id,
        invoice_id=invoice.id,
        order_id=invoice.order_id,
        amount=body.amount,
        method=body.method,
        paid_at=datetime.now(timezone.utc),
    )
    db.add(payment)
    db.flush()
    _refresh_invoice_status(db, invoice)
    # Record the key in the SAME transaction so the payment and its idempotency
    # marker commit together (or roll back together).
    _remember_key(db, "payment:buyer", idempotency_key, me.id, payment.id)
    db.commit()
    db.refresh(invoice)
    return {
        "ok": True,
        "invoice_no": invoice.invoice_no,
        "invoice_status": invoice.status,
        "paid_total": round(_invoice_paid_total(db, invoice.id), 2),
        "balance": round(float(invoice.total) - _invoice_paid_total(db, invoice.id), 2),
    }


@router.post("/supplier")
def pay_supplier(
    body: SupplierPaymentRequest,
    me: User = Depends(get_current_user),
    _=Depends(require_resource("payments")),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    supplier = db.query(Supplier).filter(Supplier.id == body.supplier_id).first()
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")

    # Idempotency: a replayed request returns the original payment instead of
    # paying the supplier twice.
    prior = _replayed_payment(db, "payment:supplier", idempotency_key)
    if prior is not None:
        outstanding_now = _supplier_outstanding(db, supplier.id)
        return {
            "ok": True,
            "supplier": supplier.name,
            "amount": float(prior.amount),
            "outstanding_after": round(outstanding_now, 2),
            "is_advance": body.is_advance,
            "idempotent_replay": True,
        }

    outstanding = _supplier_outstanding(db, supplier.id)
    if not body.is_advance and body.amount - 0.001 > outstanding:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Amount {_inr(body.amount)} exceeds the outstanding bill "
                f"{_inr(outstanding)} for {supplier.name}. "
                "Tick 'advance payment' to pay more than is owed."
            ),
        )

    payment = Payment(
        direction="outgoing",
        supplier_id=supplier.id,
        amount=body.amount,
        method=body.method,
        paid_at=datetime.now(timezone.utc),
    )
    db.add(payment)
    db.flush()
    _remember_key(db, "payment:supplier", idempotency_key, me.id, payment.id)
    db.commit()
    return {
        "ok": True,
        "supplier": supplier.name,
        "amount": body.amount,
        "outstanding_after": round(outstanding - body.amount, 2),
        "is_advance": body.is_advance,
    }


@router.post("/{payment_id}/void")
def void_payment(
    payment_id: int,
    body: VoidRequest,
    user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    """Void a payment (owner only). Kept for the audit trail but excluded from
    every total. Recomputes the invoice status for a buyer payment."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment.voided_at is not None:
        raise HTTPException(status_code=409, detail="Payment is already voided")

    payment.voided_at = datetime.now(timezone.utc)
    payment.void_reason = body.reason
    payment.voided_by_user_id = user.id
    db.flush()

    invoice_status = None
    if payment.direction == "incoming" and payment.invoice_id:
        invoice = db.query(Invoice).filter(Invoice.id == payment.invoice_id).first()
        if invoice is not None:
            _refresh_invoice_status(db, invoice)
            invoice_status = invoice.status

    db.commit()
    return {
        "ok": True,
        "payment_id": payment.id,
        "voided": True,
        "void_reason": payment.void_reason,
        "invoice_status": invoice_status,
    }


@router.get("/dues")
def pending_dues(
    _=Depends(require_resource("payments")),
    db: Session = Depends(get_db),
):
    from datetime import date

    today = date.today()

    # Buyers owe us: per-invoice balance with age (days since invoice date).
    invoices = db.query(Invoice).all()
    buyers_owe = []
    for inv in invoices:
        paid = _invoice_paid_total(db, inv.id)
        bal = float(inv.total) - paid
        if bal > 0.001:
            b = db.query(Buyer).filter(Buyer.id == inv.buyer_id).first()
            inv_date = inv.created_at.date() if inv.created_at else today
            days = (today - inv_date).days
            buyers_owe.append(
                {
                    "buyer_name": b.name if b else "",
                    "invoice_no": inv.invoice_no,
                    "invoice_date": inv_date.isoformat(),
                    "due": round(bal, 2),
                    "days_overdue": max(0, days),
                    "overdue": days > 30,
                }
            )
    buyers_owe.sort(key=lambda r: -r["days_overdue"])

    # We owe suppliers: Σ(raised/received PO value) − Σ(outgoing payments) per supplier.
    supplier_due = []
    suppliers = db.query(Supplier).all()
    for s in suppliers:
        billed = (
            db.query(
                func.coalesce(
                    func.sum(PurchaseOrder.quantity_kg * PurchaseOrder.unit_cost), 0
                )
            )
            .filter(
                PurchaseOrder.supplier_id == s.id,
                PurchaseOrder.status.in_(("raised", "received")),
            )
            .scalar()
            or 0
        )
        paid = (
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(
                Payment.direction == "outgoing",
                Payment.supplier_id == s.id,
                Payment.voided_at.is_(None),
            )
            .scalar()
            or 0
        )
        owed = float(billed) - float(paid)
        if owed > 0.001:
            # Oldest open PO date as the bill age reference.
            oldest = (
                db.query(func.min(PurchaseOrder.created_at))
                .filter(
                    PurchaseOrder.supplier_id == s.id,
                    PurchaseOrder.status.in_(("raised", "received")),
                )
                .scalar()
            )
            bill_date = oldest.date() if oldest else today
            days = (today - bill_date).days
            supplier_due.append(
                {
                    "supplier_name": s.name,
                    "bill_date": bill_date.isoformat(),
                    "due": round(owed, 2),
                    "days_overdue": max(0, days),
                    "overdue": days > 30,
                }
            )
    supplier_due.sort(key=lambda r: -r["days_overdue"])

    return {
        "buyers_owe_us": buyers_owe,
        "we_owe_suppliers": supplier_due,
        "total_receivable": round(sum(r["due"] for r in buyers_owe), 2),
        "total_payable": round(sum(d["due"] for d in supplier_due), 2),
    }


# ------------------- buyer payments awaiting confirmation ------------------- #
class RejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=255)


def _req_out(db: Session, r: BuyerPaymentRequest) -> dict:
    o = db.get(Order, r.order_id)
    b = db.get(Buyer, r.buyer_id)
    s = op.summary(db, o) if o else {}
    return {
        "id": r.id,
        "order_id": r.order_id,
        "order_no": o.order_no if o else "",
        "order_status": o.status if o else "",
        "buyer_name": b.name if b else "",
        "amount": float(r.amount),
        "method": r.method,
        "reference": r.reference,
        "note": r.note,
        "status": r.status,
        "reject_reason": r.reject_reason,
        "submitted_at": r.submitted_at,
        "reviewed_at": r.reviewed_at,
        "order_total": s.get("total"),
        "order_paid": s.get("paid"),
        "order_balance": s.get("balance"),
    }


def _get_pending(db: Session, request_id: int) -> BuyerPaymentRequest:
    r = db.get(BuyerPaymentRequest, request_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Payment request not found")
    if r.status != "pending":
        raise HTTPException(status_code=409, detail=f"This payment is already {r.status}")
    return r


def _tell_buyer(db: Session, r: BuyerPaymentRequest, title: str, body: str, me: User) -> None:
    if r.submitted_by_user_id:
        db.add(Notification(to_user_id=r.submitted_by_user_id, kind="info", title=title[:200],
                            body=body, from_user_name=me.name))


@router.get("/requests")
def payment_requests(
    status: str = "pending",
    _=Depends(require_resource("payments")),
    db: Session = Depends(get_db),
):
    q = db.query(BuyerPaymentRequest)
    if status != "all":
        q = q.filter(BuyerPaymentRequest.status == status)
    rows = q.order_by(BuyerPaymentRequest.id.desc()).limit(200).all()
    return [_req_out(db, r) for r in rows]


@router.post("/requests/{request_id}/confirm")
def confirm_request(
    request_id: int,
    me: User = Depends(get_current_user),
    _=Depends(require_resource("payments")),
    db: Session = Depends(get_db),
):
    r = _get_pending(db, request_id)
    order = db.get(Order, r.order_id)
    s = op.summary(db, order)
    if float(r.amount) - 0.001 > s["balance"]:
        raise HTTPException(
            status_code=409,
            detail=f"Amount {_inr(float(r.amount))} is more than the {_inr(s['balance'])} still due on {order.order_no}. Reject it instead.",
        )
    now = datetime.now(timezone.utc)
    payment = Payment(
        direction="incoming", buyer_id=r.buyer_id, order_id=r.order_id, amount=r.amount,
        method=r.method, reference=r.reference, note=r.note, paid_at=now,
        recorded_by_user_id=me.id,
    )
    db.add(payment)
    db.flush()
    r.status = "confirmed"
    r.reviewed_by_user_id = me.id
    r.reviewed_at = now
    r.payment_id = payment.id
    op.allocate_to_invoices(db, order.id)
    after = op.summary(db, order)
    done = after["status"] == "paid"
    _tell_buyer(db, r, f"Payment confirmed: {_inr(float(r.amount))} for {order.order_no}",
                "Order fully paid." if done else f"Balance left: {_inr(after['balance'])}.", me)
    for role in (rbac.ROLE_SALES_MANAGER, rbac.ROLE_MANAGER):
        db.add(Notification(
            to_role=role, kind="info",
            title=f"{order.order_no}: {'fully paid' if done else 'payment received'}",
            body=f"{_inr(float(r.amount))} confirmed by accounts · balance {_inr(after['balance'])}",
            from_user_name=me.name,
        ))
    db.commit()
    return {"ok": True, "request": _req_out(db, r), "order_payment": after}


@router.post("/requests/{request_id}/reject")
def reject_request(
    request_id: int,
    body: RejectRequest,
    me: User = Depends(get_current_user),
    _=Depends(require_resource("payments")),
    db: Session = Depends(get_db),
):
    r = _get_pending(db, request_id)
    order = db.get(Order, r.order_id)
    r.status = "rejected"
    r.reject_reason = body.reason.strip()
    r.reviewed_by_user_id = me.id
    r.reviewed_at = datetime.now(timezone.utc)
    _tell_buyer(db, r, f"Payment not confirmed: {_inr(float(r.amount))} for {order.order_no if order else ''}",
                f"Reason: {r.reject_reason}. Please check and pay again.", me)
    db.commit()
    return {"ok": True, "request": _req_out(db, r)}

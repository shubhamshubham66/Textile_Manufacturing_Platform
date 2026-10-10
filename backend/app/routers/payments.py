"""Payments module — scene 6 (part 1): money in and out.

Owner + accountant (resource "payments"):
  GET  /api/payments                   list payments (in/out)
  POST /api/payments/buyer             record a buyer payment against an invoice
  POST /api/payments/supplier          pay a supplier (yarn bills)
  GET  /api/payments/dues              pending dues: buyers owe us, we owe suppliers
  GET  /api/payments/_meta             invoices + suppliers for the forms
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_resource
from app.models import Buyer, Invoice, Payment, PurchaseOrder, Supplier

router = APIRouter(prefix="/api/payments", tags=["payments"])

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

    @field_validator("method")
    @classmethod
    def _m(cls, v: str) -> str:
        if v not in VALID_METHODS:
            raise ValueError(f"method must be one of {VALID_METHODS}")
        return v


def _invoice_paid_total(db: Session, invoice_id: int) -> float:
    total = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.direction == "incoming", Payment.invoice_id == invoice_id)
        .scalar()
    )
    return float(total or 0)


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
        out.append(
            {
                "id": p.id,
                "direction": p.direction,
                "party": party,
                "amount": float(p.amount),
                "method": p.method,
                "invoice_id": p.invoice_id,
                "paid_at": p.paid_at,
            }
        )
    return out


@router.post("/buyer")
def record_buyer_payment(
    body: BuyerPaymentRequest,
    _=Depends(require_resource("payments")),
    db: Session = Depends(get_db),
):
    invoice = db.query(Invoice).filter(Invoice.id == body.invoice_id).first()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")

    already = _invoice_paid_total(db, invoice.id)
    balance = float(invoice.total) - already
    if balance <= 0:
        raise HTTPException(status_code=409, detail="Invoice is already fully paid")
    if body.amount - 0.001 > balance:
        raise HTTPException(
            status_code=400,
            detail=f"Amount {body.amount} exceeds outstanding balance {round(balance, 2)}",
        )

    payment = Payment(
        direction="incoming",
        buyer_id=invoice.buyer_id,
        invoice_id=invoice.id,
        amount=body.amount,
        method=body.method,
        paid_at=datetime.now(timezone.utc),
    )
    db.add(payment)
    db.flush()
    _refresh_invoice_status(db, invoice)
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
    _=Depends(require_resource("payments")),
    db: Session = Depends(get_db),
):
    supplier = db.query(Supplier).filter(Supplier.id == body.supplier_id).first()
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")

    payment = Payment(
        direction="outgoing",
        supplier_id=supplier.id,
        amount=body.amount,
        method=body.method,
        paid_at=datetime.now(timezone.utc),
    )
    db.add(payment)
    db.commit()
    return {"ok": True, "supplier": supplier.name, "amount": body.amount}


@router.get("/dues")
def pending_dues(
    _=Depends(require_resource("payments")),
    db: Session = Depends(get_db),
):
    # Buyers owe us: Σ invoice balances per buyer.
    invoices = db.query(Invoice).all()
    buyer_due: dict[int, dict] = {}
    for inv in invoices:
        paid = _invoice_paid_total(db, inv.id)
        bal = float(inv.total) - paid
        if bal > 0.001:
            b = db.query(Buyer).filter(Buyer.id == inv.buyer_id).first()
            entry = buyer_due.setdefault(
                inv.buyer_id, {"buyer_name": b.name if b else "", "due": 0.0}
            )
            entry["due"] += bal

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
            .filter(Payment.direction == "outgoing", Payment.supplier_id == s.id)
            .scalar()
            or 0
        )
        owed = float(billed) - float(paid)
        if owed > 0.001:
            supplier_due.append(
                {"supplier_name": s.name, "due": round(owed, 2)}
            )

    return {
        "buyers_owe_us": [
            {"buyer_name": v["buyer_name"], "due": round(v["due"], 2)}
            for v in buyer_due.values()
        ],
        "we_owe_suppliers": supplier_due,
        "total_receivable": round(
            sum(v["due"] for v in buyer_due.values()), 2
        ),
        "total_payable": round(sum(d["due"] for d in supplier_due), 2),
    }

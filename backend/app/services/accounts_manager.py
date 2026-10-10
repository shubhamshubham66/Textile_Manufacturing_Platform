"""Read-only aggregations for the Accounts & Finance Manager dashboard.

Builds the six dashboard cards and supporting lists from the live tables,
reusing the owner reporting math (services/reports.py) so figures agree with
the owner's Profit/Loss. No writes here — payments/wages reuse their existing
routers; expenses are recorded in routers/accounts_manager.py.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    ActivityLog,
    Buyer,
    Invoice,
    Payment,
    Supplier,
    Wage,
)
from app.services import reports as rp


def _f(v) -> float:
    return round(float(v or 0), 2)


def _iso(v) -> str | None:
    return v.isoformat() if v else None


def month_window(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    start = today.replace(day=1)
    nxt = (start + timedelta(days=32)).replace(day=1)
    return start, nxt - timedelta(days=1)


def _invoice_paid(db: Session, invoice_id: int) -> float:
    return _f(
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(
            Payment.invoice_id == invoice_id,
            Payment.direction == "incoming",
            Payment.voided_at.is_(None),
        )
        .scalar()
    )


def receivables(db: Session) -> dict:
    """Buyers owe us: per-invoice outstanding balance with ageing."""
    today = date.today()
    rows = []
    total = 0.0
    for inv in db.query(Invoice).order_by(Invoice.id.desc()).all():
        paid = _invoice_paid(db, inv.id)
        bal = round(float(inv.total or 0) - paid, 2)
        if bal <= 0.01:
            continue
        total += bal
        b = db.get(Buyer, inv.buyer_id)
        inv_date = inv.created_at.date() if inv.created_at else today
        days = (today - inv_date).days
        rows.append(
            {
                "invoice_no": inv.invoice_no,
                "buyer": b.name if b else "",
                "total": _f(inv.total),
                "paid": paid,
                "balance": bal,
                "days": max(0, days),
                "overdue": days > 30,
            }
        )
    return {"rows": rows, "total": round(total, 2), "overdue": sum(1 for r in rows if r["overdue"])}


def payables(db: Session) -> dict:
    """We owe suppliers: billed (raised/received POs) − paid, per supplier."""
    from app.models import PurchaseOrder

    today = date.today()
    rows = []
    total = 0.0
    for s in db.query(Supplier).all():
        billed = (
            db.query(func.coalesce(func.sum(PurchaseOrder.quantity_kg * PurchaseOrder.unit_cost), 0))
            .filter(PurchaseOrder.supplier_id == s.id, PurchaseOrder.status.in_(("raised", "received")))
            .scalar()
            or 0
        )
        paid = (
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.direction == "outgoing", Payment.supplier_id == s.id, Payment.voided_at.is_(None))
            .scalar()
            or 0
        )
        owed = round(float(billed) - float(paid), 2)
        if owed <= 0.01:
            continue
        total += owed
        oldest = (
            db.query(func.min(PurchaseOrder.created_at))
            .filter(PurchaseOrder.supplier_id == s.id, PurchaseOrder.status.in_(("raised", "received")))
            .scalar()
        )
        bdate = oldest.date() if oldest else today
        days = (today - bdate).days
        rows.append(
            {"supplier": s.name, "due": owed, "days": max(0, days), "overdue": days > 30}
        )
    return {"rows": rows, "total": round(total, 2), "overdue": sum(1 for r in rows if r["overdue"])}


def dashboard(db: Session) -> dict:
    start, end = month_window()

    # Total sales this month = invoiced total in the month.
    s_dt = datetime.combine(start, datetime.min.time())
    e_dt = datetime.combine(end, datetime.max.time())
    total_sales = _f(
        db.query(func.coalesce(func.sum(Invoice.total), 0))
        .filter(Invoice.created_at.between(s_dt, e_dt))
        .scalar()
    )

    recv = receivables(db)
    pay = payables(db)
    pl = rp.profit_or_loss(db, start, end)
    wages = rp.wages_report(db, start, end)

    # Monthly expenses = supplier payments out + wages paid + other expenses out.
    other_expenses = _f(
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(
            Payment.direction == "outgoing",
            Payment.supplier_id.is_(None),
            Payment.voided_at.is_(None),
            Payment.paid_at.between(s_dt, e_dt),
        )
        .scalar()
    )
    monthly_expenses = round(pl["supplier_payments_out"] + pl["wages"] + other_expenses, 2)

    cards = {
        "total_sales": total_sales,
        "pending_buyer_payments": recv["total"],
        "pending_buyer_count": len(recv["rows"]),
        "supplier_payments_due": pay["total"],
        "supplier_due_count": len(pay["rows"]),
        "monthly_expenses": monthly_expenses,
        "worker_wages": wages["total_wages"],
        "worker_wages_paid": wages["total_paid"],
        "worker_wages_due": wages["total_unpaid"],
        "profit_or_loss": pl["profit_or_loss"],
        "is_profit": pl["is_profit"],
    }

    acts = (
        db.query(ActivityLog)
        .filter(ActivityLog.category.in_(("payment", "dispatch", "order", "attendance", "stock")))
        .order_by(ActivityLog.id.desc())
        .limit(10)
        .all()
    )

    return {
        "month": {"start": start.isoformat(), "end": end.isoformat()},
        "cards": cards,
        "receivables": recv["rows"][:6],
        "payables": pay["rows"][:6],
        "profit": pl,
        "activity": [activity_row(a) for a in acts],
    }


def activity_row(a: ActivityLog) -> dict:
    return {
        "id": a.id,
        "at": _iso(a.at),
        "user": a.user_name or "System",
        "role": a.user_role,
        "category": a.category,
        "action": a.action,
        "details": a.details,
    }

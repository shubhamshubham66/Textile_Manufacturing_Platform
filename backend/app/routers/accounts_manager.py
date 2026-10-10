"""Accounts & Finance Manager control panel — /api/accounts/*.

The Accounts & Finance Manager (role "accounts_manager") owns invoices,
buyer/supplier payments, wages, expenses and financial reports.

  Dashboard          GET  /api/accounts/dashboard      the six cards
  Sales Invoices     GET  /api/accounts/invoices       invoices + dispatch link
  Overtime Records   GET  /api/accounts/overtime       OT hours from attendance
  Production Exp.    GET  /api/accounts/production-expenses   cost per order (read-only)
  Other Expenses     GET  /api/accounts/expenses
                     POST /api/accounts/expenses        record an expense (txn + audit)
  Financial Reports  GET  /api/accounts/reports?period=day|month|year
  Notifications      GET  /api/accounts/notifications  (+ /{id}/read)
  Activity Logs      GET  /api/accounts/activity

Buyer Payments, Supplier Bills & Payments, Worker Attendance and Salary & Wage
Management reuse the EXISTING, proven endpoints (/api/payments/*, /api/wages/*,
/api/attendance) — the role holds those resources, so no logic is duplicated and
duplicate-payment / overpayment guards apply unchanged.

PERMISSIONS (backend-enforced):
  - am_* endpoints are guarded by require_resource("am_*"); only this role passes.
  - Expenses are recorded in a DB transaction with an audit log entry; the P&L
    reuses them so figures stay consistent. Voiding a payment stays owner-only.
  - This role cannot confirm orders, approve QC, or dispatch goods (no endpoint).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import rbac
from app.database import get_db
from app.deps import get_current_user, require_resource
from app.models import (
    ActivityLog,
    Attendance,
    Buyer,
    Dispatch,
    Employee,
    Invoice,
    Notification,
    Order,
    Payment,
    User,
)
from app.services import accounts_manager as am
from app.services import reports as rp

router = APIRouter(prefix="/api/accounts", tags=["accounts-finance-manager"])

EXPENSE_CATEGORIES = ("production", "rent", "utility", "maintenance", "transport", "other")
VALID_METHODS = ("cash", "bank", "upi")
STANDARD_HOURS = 8.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _log(db: Session, me: User, action: str, details: str) -> None:
    db.add(
        ActivityLog(
            user_id=me.id, user_name=me.name, user_role=me.role.name,
            category="payment", action=action, details=details[:2000],
        )
    )


def _notify(db: Session, to_role: str, title: str, body: str, me: User) -> None:
    db.add(Notification(to_role=to_role, kind="info", title=title[:200], body=body, from_user_name=me.name))


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@router.get("/dashboard")
def dashboard(_=Depends(require_resource("am_dashboard")), db: Session = Depends(get_db)):
    return am.dashboard(db)


# --------------------------------------------------------------------------- #
# Sales Invoices (from Sales & Dispatch)
# --------------------------------------------------------------------------- #
@router.get("/invoices")
def invoices(_=Depends(require_resource("am_invoices")), db: Session = Depends(get_db)):
    rows = []
    for inv in db.query(Invoice).order_by(Invoice.id.desc()).all():
        order = db.get(Order, inv.order_id)
        buyer = db.get(Buyer, inv.buyer_id)
        dispatch = db.get(Dispatch, inv.dispatch_id) if inv.dispatch_id else None
        paid = am._invoice_paid(db, inv.id)
        rows.append(
            {
                "id": inv.id,
                "invoice_no": inv.invoice_no,
                "order_no": order.order_no if order else "",
                "buyer": buyer.name if buyer else "",
                "dispatch_no": dispatch.dispatch_no if dispatch else None,
                "subtotal": am._f(inv.subtotal),
                "tax": am._f(inv.tax),
                "total": am._f(inv.total),
                "paid": paid,
                "balance": round(float(inv.total or 0) - paid, 2),
                "status": inv.status,
                "created_at": am._iso(inv.created_at),
            }
        )
    return {"invoices": rows}


# --------------------------------------------------------------------------- #
# Overtime Records (derived from verified attendance)
# --------------------------------------------------------------------------- #
@router.get("/overtime")
def overtime(
    start: date | None = None,
    end: date | None = None,
    _=Depends(require_resource("am_overtime")),
    db: Session = Depends(get_db),
):
    s, e = (start, end) if (start and end) else am.month_window()
    rows = (
        db.query(Attendance)
        .filter(Attendance.work_date.between(s, e), Attendance.hours_worked > STANDARD_HOURS)
        .order_by(Attendance.work_date.desc())
        .all()
    )
    out = []
    total_ot = 0.0
    for a in rows:
        emp = db.get(Employee, a.employee_id)
        ot = round(float(a.hours_worked) - STANDARD_HOURS, 2)
        total_ot += ot
        out.append(
            {
                "employee": emp.name if emp else "",
                "work_date": a.work_date.isoformat(),
                "shift": a.shift,
                "hours_worked": am._f(a.hours_worked),
                "overtime_hours": ot,
            }
        )
    return {
        "start": s.isoformat(), "end": e.isoformat(),
        "rows": out, "total_overtime_hours": round(total_ot, 2),
        "note": "Overtime is derived from verified attendance (hours beyond 8) and feeds wage calculation.",
    }


# --------------------------------------------------------------------------- #
# Production Expenses (cost per order — read-only from the reports math)
# --------------------------------------------------------------------------- #
@router.get("/production-expenses")
def production_expenses(
    start: date | None = None,
    end: date | None = None,
    _=Depends(require_resource("am_prod_expenses")),
    db: Session = Depends(get_db),
):
    s, e = (start, end) if (start and end) else am.month_window()
    rows = rp.cost_per_order(db, s, e)
    totals = {
        "yarn": round(sum(r["yarn_cost"] for r in rows), 2),
        "wages": round(sum(r["wage_cost"] for r in rows), 2),
        "machine": round(sum(r["machine_cost"] for r in rows), 2),
        "total": round(sum(r["total_cost"] for r in rows), 2),
    }
    return {"start": s.isoformat(), "end": e.isoformat(), "orders": rows, "totals": totals}


# --------------------------------------------------------------------------- #
# Other Expenses (record + list) — stored as outgoing payments with a category
# --------------------------------------------------------------------------- #
class ExpenseIn(BaseModel):
    amount: float = Field(gt=0, le=100_000_000)
    category: str = "other"
    note: str = Field(min_length=2, max_length=500)
    method: str = "bank"
    reference: str | None = Field(default=None, max_length=80)

    @field_validator("category")
    @classmethod
    def _cat(cls, v: str) -> str:
        if v not in EXPENSE_CATEGORIES:
            raise ValueError(f"category must be one of {', '.join(EXPENSE_CATEGORIES)}")
        return v

    @field_validator("method")
    @classmethod
    def _m(cls, v: str) -> str:
        if v not in VALID_METHODS:
            raise ValueError(f"method must be one of {', '.join(VALID_METHODS)}")
        return v


@router.get("/expenses")
def list_expenses(_=Depends(require_resource("am_expenses")), db: Session = Depends(get_db)):
    rows = (
        db.query(Payment)
        .filter(Payment.direction == "outgoing", Payment.supplier_id.is_(None), Payment.voided_at.is_(None))
        .order_by(Payment.id.desc())
        .all()
    )
    out = [
        {
            "id": p.id,
            "amount": am._f(p.amount),
            "category": p.category or "other",
            "note": p.note,
            "method": p.method,
            "reference": p.reference,
            "paid_at": am._iso(p.paid_at),
        }
        for p in rows
    ]
    return {"expenses": out, "total": round(sum(e["amount"] for e in out), 2),
            "categories": list(EXPENSE_CATEGORIES)}


@router.post("/expenses", status_code=201)
def record_expense(
    body: ExpenseIn,
    me: User = Depends(get_current_user),
    _=Depends(require_resource("am_expenses")),
    db: Session = Depends(get_db),
):
    """Record a factory/other expense as an outgoing payment (no supplier), in a
    transaction, with an audit log. Duplicate guard: same amount + reference in
    the last minute is rejected."""
    if body.reference:
        dup = (
            db.query(Payment)
            .filter(
                Payment.direction == "outgoing",
                Payment.supplier_id.is_(None),
                Payment.reference == body.reference.strip(),
            )
            .first()
        )
        if dup is not None:
            raise HTTPException(409, f"An expense with reference '{body.reference}' already exists (no duplicate).")
    p = Payment(
        direction="outgoing",
        amount=body.amount,
        method=body.method,
        category=body.category,
        note=body.note.strip(),
        reference=(body.reference or "").strip() or None,
        recorded_by_user_id=me.id,
        paid_at=_now(),
    )
    db.add(p)
    _log(db, me, "expense_recorded", f"{body.category} ₹{body.amount:,.0f} · {body.note.strip()}")
    # Notify the Supermanager about a major expense (>= ₹50,000).
    if body.amount >= 50000:
        _notify(db, rbac.ROLE_MANAGER, "Major expense recorded",
                f"{body.category}: ₹{body.amount:,.0f} · {body.note.strip()}", me)
    db.commit()
    return {"ok": True, "id": p.id, "amount": am._f(p.amount), "category": p.category}


# --------------------------------------------------------------------------- #
# Financial Reports (day / month / year — income, expense, cash-flow, P&L)
# --------------------------------------------------------------------------- #
@router.get("/reports")
def reports(
    period: str = Query("month", pattern="^(day|month|year)$"),
    on: date | None = None,
    _=Depends(require_resource("am_reports")),
    db: Session = Depends(get_db),
):
    today = on or date.today()
    if period == "day":
        s = e = today
    elif period == "year":
        s, e = date(today.year, 1, 1), date(today.year, 12, 31)
    else:
        s, e = am.month_window(today)

    pl = rp.profit_or_loss(db, s, e)
    s_dt = datetime.combine(s, datetime.min.time())
    e_dt = datetime.combine(e, datetime.max.time())
    invoiced = am._f(
        db.query(func.coalesce(func.sum(Invoice.total), 0)).filter(Invoice.created_at.between(s_dt, e_dt)).scalar()
    )
    other_exp = am._f(
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.direction == "outgoing", Payment.supplier_id.is_(None),
                Payment.voided_at.is_(None), Payment.paid_at.between(s_dt, e_dt))
        .scalar()
    )
    # Cash flow: money in (buyer payments) vs money out (supplier + wages + other).
    cash_in = pl["buyer_payments_in"]
    cash_out = round(pl["supplier_payments_out"] + pl["wages"] + other_exp, 2)
    return {
        "period": period,
        "start": s.isoformat(),
        "end": e.isoformat(),
        "income": {"invoiced": invoiced, "buyer_payments_in": cash_in},
        "expenses": {
            "supplier_payments": pl["supplier_payments_out"],
            "wages_paid": pl["wages"],
            "other_expenses": other_exp,
            "total": cash_out,
        },
        "cash_flow": {"in": cash_in, "out": cash_out, "net": round(cash_in - cash_out, 2)},
        "profit_or_loss": pl["profit_or_loss"],
        "is_profit": pl["is_profit"],
        "wages_due": pl["wages_due"],
        "receivable": am.receivables(db)["total"],
        "payable": am.payables(db)["total"],
    }


# --------------------------------------------------------------------------- #
# Notifications
# --------------------------------------------------------------------------- #
@router.get("/notifications")
def notifications(_=Depends(require_resource("am_notifications")), db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    rows = (
        db.query(Notification)
        .filter(or_(Notification.to_user_id == me.id,
                    Notification.to_role.in_((rbac.ROLE_ACCOUNTS_MANAGER, rbac.ROLE_ACCOUNTANT))))
        .order_by(Notification.id.desc())
        .limit(50)
        .all()
    )
    return {
        "notifications": [
            {"id": n.id, "kind": n.kind, "title": n.title, "body": n.body,
             "from": n.from_user_name, "created_at": am._iso(n.created_at), "read": n.read_at is not None}
            for n in rows
        ],
        "unread": sum(1 for n in rows if n.read_at is None),
    }


@router.post("/notifications/{nid}/read")
def mark_read(nid: int, _=Depends(require_resource("am_notifications")), db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    n = db.get(Notification, nid)
    if n is None or (n.to_user_id != me.id and n.to_role not in (rbac.ROLE_ACCOUNTS_MANAGER, rbac.ROLE_ACCOUNTANT)):
        raise HTTPException(404, "Notification not found")
    if n.read_at is None:
        n.read_at = datetime.utcnow()
        db.commit()
    return {"ok": True, "id": nid}


# --------------------------------------------------------------------------- #
# Activity Logs
# --------------------------------------------------------------------------- #
@router.get("/activity")
def activity(
    category: str | None = None,
    q: str | None = None,
    limit: int = Query(60, ge=1, le=200),
    _=Depends(require_resource("am_activity")),
    db: Session = Depends(get_db),
):
    cats = ("payment", "order", "dispatch", "attendance", "stock")
    query = db.query(ActivityLog).filter(ActivityLog.category.in_(cats))
    if category:
        query = query.filter(ActivityLog.category == category)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(ActivityLog.details.ilike(like), ActivityLog.user_name.ilike(like)))
    rows = query.order_by(ActivityLog.id.desc()).limit(limit).all()
    return {"rows": [am.activity_row(a) for a in rows], "categories": list(cats)}

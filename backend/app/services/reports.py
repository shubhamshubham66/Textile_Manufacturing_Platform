"""Owner reporting math — cost per order, machine report, month-end P&L, wages.

ONE set of definitions, used everywhere (Dashboard and Reports agree exactly):

  Order cost = yarn cost + wages cost + machine cost
    - yarn cost    = Σ(receipt.quantity_kg × receipt.unit_cost) for yarn_receipts
                     whose order_id = that order.
    - machine cost = power + overhead only (machine.hourly_cost does NOT include
                     operator wages). Allocated to an order by its output-metre
                     share × Σ(machine.hourly_cost). No wage double-counting.
    - wages cost   = total paid wages allocated by the order's output-metre share.

  Order margin (estimate) = invoiced revenue − order cost. Labelled "estimate".

  Month net (CASH basis) = buyer payments received in month
                           − raw-material (supplier) bills paid in month
                           − wages PAID in month.

All amounts in INR.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Employee,
    Invoice,
    Machine,
    Order,
    Payment,
    ProductionLog,
    Wage,
    YarnReceipt,
)
from app.services.production import idle_loss_for_machine


def _now() -> datetime:
    return datetime.now(timezone.utc)


def month_bounds(month: str | None) -> tuple[date, date]:
    """Return (first_day, last_day) for a 'YYYY-MM' string. Defaults to current."""
    if month:
        y, mo = int(month[:4]), int(month[5:7])
    else:
        n = _now()
        y, mo = n.year, n.month
    last = calendar.monthrange(y, mo)[1]
    return date(y, mo, 1), date(y, mo, last)


# ---- building blocks (optionally month-scoped) ---- #
def _output_q(db: Session, start: date | None, end: date | None):
    q = db.query(ProductionLog)
    if start:
        q = q.filter(ProductionLog.log_date >= start)
    if end:
        q = q.filter(ProductionLog.log_date <= end)
    return q


def total_output_meters(db, start=None, end=None) -> float:
    return float(
        _output_q(db, start, end)
        .with_entities(func.coalesce(func.sum(ProductionLog.output_meters), 0))
        .scalar() or 0
    )


def order_output_meters(db, order_id, start=None, end=None) -> float:
    return float(
        _output_q(db, start, end)
        .filter(ProductionLog.order_id == order_id)
        .with_entities(func.coalesce(func.sum(ProductionLog.output_meters), 0))
        .scalar() or 0
    )


def order_yarn_cost(db: Session, order_id: int) -> float:
    return float(
        db.query(
            func.coalesce(func.sum(YarnReceipt.quantity_kg * YarnReceipt.unit_cost), 0)
        )
        .filter(YarnReceipt.order_id == order_id)
        .scalar() or 0
    )


def wages_paid(db: Session, start: date | None, end: date | None) -> float:
    """Total wages PAID (cash basis) in the window — status paid, paid_at in range."""
    q = db.query(func.coalesce(func.sum(Wage.amount), 0)).filter(Wage.status == "paid")
    if start:
        q = q.filter(func.date(Wage.paid_at) >= start)
    if end:
        q = q.filter(func.date(Wage.paid_at) <= end)
    return float(q.scalar() or 0)


def _machine_cost_basis(db: Session) -> float:
    return float(
        db.query(func.coalesce(func.sum(Machine.hourly_cost), 0)).scalar() or 0
    )


# ---- reports ---- #
def cost_per_order(db: Session, month: str | None = None) -> dict:
    start, end = month_bounds(month)
    orders = db.query(Order).order_by(Order.id).all()
    total_out = total_output_meters(db)  # yarn/machine cost use lifetime output share
    wages_all = wages_paid(db, start, end)
    machine_basis = _machine_cost_basis(db)

    rows, tot = [], {"yarn": 0.0, "wage": 0.0, "machine": 0.0, "cost": 0.0,
                     "rev": 0.0, "margin": 0.0, "out": 0.0}
    for o in orders:
        out_m = order_output_meters(db, o.id)
        share = (out_m / total_out) if total_out > 0 else 0.0
        yarn = order_yarn_cost(db, o.id)
        wage_alloc = round(wages_all * share, 2)
        machine_alloc = round(machine_basis * share, 2)
        cost = round(yarn + wage_alloc + machine_alloc, 2)
        revenue = round(out_m * float(o.unit_price), 2)
        rows.append({
            "order_no": o.order_no, "status": o.status, "output_meters": out_m,
            "yarn_cost": round(yarn, 2), "wage_cost": wage_alloc,
            "machine_cost": machine_alloc, "total_cost": cost,
            "revenue_est": revenue, "margin_est": round(revenue - cost, 2),
        })
        tot["yarn"] += yarn; tot["wage"] += wage_alloc; tot["machine"] += machine_alloc
        tot["cost"] += cost; tot["rev"] += revenue; tot["margin"] += revenue - cost
        tot["out"] += out_m
    totals = {
        "output_meters": round(tot["out"], 2), "yarn_cost": round(tot["yarn"], 2),
        "wage_cost": round(tot["wage"], 2), "machine_cost": round(tot["machine"], 2),
        "total_cost": round(tot["cost"], 2), "revenue_est": round(tot["rev"], 2),
        "margin_est": round(tot["margin"], 2),
    }
    return {"rows": rows, "totals": totals, "month": f"{start:%Y-%m}"}


def machine_report(db: Session, month: str | None = None) -> dict:
    start, end = month_bounds(month)
    now = _now()
    machines = db.query(Machine).order_by(Machine.name).all()
    rows = []
    tot = {"out": 0.0, "idle": 0.0, "break": 0.0, "run": 0.0, "loss": 0.0}
    for mc in machines:
        output = float(
            _output_q(db, start, end)
            .filter(ProductionLog.machine_id == mc.id)
            .with_entities(func.coalesce(func.sum(ProductionLog.output_meters), 0))
            .scalar() or 0
        )
        loss = idle_loss_for_machine(db, mc.id, float(mc.hourly_cost or 0), now=now)
        rows.append({
            "machine": mc.name, "type": mc.type, "current_status": mc.current_status,
            "total_output_meters": output,
            "running_hours": loss.get("running_hours", 0.0),
            "idle_hours": loss["idle_hours"], "breakdown_hours": loss["breakdown_hours"],
            "idle_loss_rupees": loss["loss_rupees"],
            "top_reason": loss.get("top_reason", "—"),
        })
        tot["out"] += output; tot["idle"] += loss["idle_hours"]
        tot["break"] += loss["breakdown_hours"]; tot["loss"] += loss["loss_rupees"]
        tot["run"] += loss.get("running_hours", 0.0)
    totals = {
        "total_output_meters": round(tot["out"], 2),
        "running_hours": round(tot["run"], 2), "idle_hours": round(tot["idle"], 2),
        "breakdown_hours": round(tot["break"], 2),
        "idle_loss_rupees": round(tot["loss"], 2),
    }
    return {"rows": rows, "totals": totals, "month": f"{start:%Y-%m}"}


def profit_or_loss(db: Session, month: str | None = None) -> dict:
    """Month net on a CASH basis. (start/end come from the month string.)"""
    start, end = month_bounds(month)
    pay_q = db.query(Payment).filter(
        func.date(Payment.paid_at) >= start, func.date(Payment.paid_at) <= end
    )
    payments = pay_q.all()
    income = sum(float(p.amount) for p in payments if p.direction == "incoming")
    supplier_out = sum(float(p.amount) for p in payments if p.direction == "outgoing")
    wages = wages_paid(db, start, end)
    profit = round(income - supplier_out - wages, 2)
    return {
        "month": f"{start:%Y-%m}",
        "buyer_payments_in": round(income, 2),
        "raw_material_bills_out": round(supplier_out, 2),
        "wages_paid": round(wages, 2),
        "net": profit,
        "is_profit": profit >= 0,
    }


def wages_report(db: Session, month: str | None = None) -> dict:
    """Owner wages view: total paid, per-employee rows, per-order allocation."""
    start, end = month_bounds(month)
    wage_rows = (
        db.query(Wage).filter(func.date(Wage.paid_at) >= start,
                              func.date(Wage.paid_at) <= end,
                              Wage.status == "paid").all()
    )
    per_emp: dict[int, dict] = {}
    total = 0.0
    for w in wage_rows:
        emp = db.query(Employee).filter(Employee.id == w.employee_id).first()
        e = per_emp.setdefault(w.employee_id, {
            "employee": emp.name if emp else "", "days": 0.0,
            "rate": float(emp.daily_wage) if emp else 0.0, "amount": 0.0,
            "status": "paid"})
        e["days"] += float(w.days_present)
        e["amount"] += float(w.amount)
        total += float(w.amount)

    # Per-order wage allocation (same output-share rule as cost_per_order).
    total_out = total_output_meters(db)
    per_order = []
    for o in db.query(Order).order_by(Order.id).all():
        out_m = order_output_meters(db, o.id)
        share = (out_m / total_out) if total_out > 0 else 0.0
        alloc = round(total * share, 2)
        if alloc > 0:
            per_order.append({"order_no": o.order_no, "wage_cost": alloc})

    return {
        "month": f"{start:%Y-%m}",
        "total_wages_paid": round(total, 2),
        "per_employee": [
            {**v, "days": round(v["days"], 1), "amount": round(v["amount"], 2)}
            for v in per_emp.values()
        ],
        "per_order": per_order,
    }

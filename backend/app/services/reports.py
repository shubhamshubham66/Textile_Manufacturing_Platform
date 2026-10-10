"""Owner reporting math — scene 6: cost per order, machine report, profit/loss.

Costing model (documented so numbers can be checked by hand):

  Cost per order = yarn cost + wage cost + machine cost
    - yarn cost   = Σ over yarn_receipts linked to the order (quantity_kg × unit_cost)
    - machine cost= Σ over production_logs for the order:
                      (output_meters / machine_output_today?) -> simplified:
                      we charge machine time by output share. For a hackathon we
                      use: machine_cost = Σ production_logs.output_meters for the
                      order × PER_METER_MACHINE_COST is NOT used; instead we use a
                      direct approach — see below.
    - wage cost   = total wages in the period allocated to the order in proportion
                    to the order's production output (metres) vs all output.

  To keep it concrete and hand-checkable we define:
    - machine cost per order = Σ (machine.hourly_cost × hours the machine ran for
      this order). We don't track per-order run-hours directly, so we approximate
      machine cost by the order's share of total production output × total machine
      running cost — identical allocation idea as wages. This keeps the model
      simple and consistent.

  Profit / loss (month) = buyer payments received (incoming)
                          − supplier payments (outgoing)
                          − wages (amount of wage records in the window)

All amounts in INR.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
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


def total_output_meters(db: Session) -> float:
    return float(
        db.query(func.coalesce(func.sum(ProductionLog.output_meters), 0)).scalar() or 0
    )


def order_output_meters(db: Session, order_id: int) -> float:
    return float(
        db.query(func.coalesce(func.sum(ProductionLog.output_meters), 0))
        .filter(ProductionLog.order_id == order_id)
        .scalar()
        or 0
    )


def order_yarn_cost(db: Session, order_id: int) -> float:
    return float(
        db.query(
            func.coalesce(
                func.sum(YarnReceipt.quantity_kg * YarnReceipt.unit_cost), 0
            )
        )
        .filter(YarnReceipt.order_id == order_id)
        .scalar()
        or 0
    )


def total_wages(db: Session) -> float:
    return float(
        db.query(func.coalesce(func.sum(Wage.amount), 0)).scalar() or 0
    )


def total_machine_running_cost_basis(db: Session) -> float:
    """A simple basis for allocating machine cost across orders: the sum of all
    machines' hourly_cost (one 'machine-hour' worth). Allocation is by output
    share, so the absolute basis only scales all orders equally."""
    return float(
        db.query(func.coalesce(func.sum(Machine.hourly_cost), 0)).scalar() or 0
    )


def cost_per_order(db: Session) -> list[dict]:
    orders = db.query(Order).order_by(Order.id).all()
    total_out = total_output_meters(db)
    wages_all = total_wages(db)
    machine_basis = total_machine_running_cost_basis(db)

    rows = []
    for o in orders:
        out_m = order_output_meters(db, o.id)
        share = (out_m / total_out) if total_out > 0 else 0.0
        yarn = order_yarn_cost(db, o.id)
        wage_alloc = round(wages_all * share, 2)
        # Machine cost allocated by the same output share against the basis.
        machine_alloc = round(machine_basis * share, 2)
        cost = round(yarn + wage_alloc + machine_alloc, 2)
        revenue = round(out_m * float(o.unit_price), 2)
        rows.append(
            {
                "order_no": o.order_no,
                "status": o.status,
                "output_meters": out_m,
                "yarn_cost": round(yarn, 2),
                "wage_cost": wage_alloc,
                "machine_cost": machine_alloc,
                "total_cost": cost,
                "revenue_est": revenue,
                "margin_est": round(revenue - cost, 2),
            }
        )
    return rows


def machine_report(db: Session) -> list[dict]:
    now = _now()
    machines = db.query(Machine).order_by(Machine.name).all()
    rows = []
    for m in machines:
        output = float(
            db.query(func.coalesce(func.sum(ProductionLog.output_meters), 0))
            .filter(ProductionLog.machine_id == m.id)
            .scalar()
            or 0
        )
        loss = idle_loss_for_machine(db, m.id, float(m.hourly_cost or 0), now=now)
        rows.append(
            {
                "machine": m.name,
                "type": m.type,
                "current_status": m.current_status,
                "total_output_meters": output,
                "idle_hours": loss["idle_hours"],
                "breakdown_hours": loss["breakdown_hours"],
                "idle_loss_rupees": loss["loss_rupees"],
            }
        )
    return rows


def profit_or_loss(db: Session, start: date | None, end: date | None) -> dict:
    """Month (or any window) P&L.

    income  = Σ incoming payments
    yarn/supplier out = Σ outgoing payments
    wages   = Σ wage amounts in window
    profit  = income − supplier_out − wages
    """
    pay_q = db.query(Payment)
    if start:
        pay_q = pay_q.filter(func.date(Payment.paid_at) >= start)
    if end:
        pay_q = pay_q.filter(func.date(Payment.paid_at) <= end)
    payments = pay_q.all()

    income = sum(float(p.amount) for p in payments if p.direction == "incoming")
    supplier_out = sum(float(p.amount) for p in payments if p.direction == "outgoing")

    wage_q = db.query(func.coalesce(func.sum(Wage.amount), 0))
    if start:
        wage_q = wage_q.filter(Wage.period_end >= start)
    if end:
        wage_q = wage_q.filter(Wage.period_start <= end)
    wages = float(wage_q.scalar() or 0)

    profit = round(income - supplier_out - wages, 2)
    return {
        "buyer_payments_in": round(income, 2),
        "supplier_payments_out": round(supplier_out, 2),
        "wages": round(wages, 2),
        "profit_or_loss": profit,
        "is_profit": profit >= 0,
    }

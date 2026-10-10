"""Owner reporting math — scene 6: cost per order, machine report, profit/loss,
wages.

ONE definition set (also written in PROJECT_STATE.md), so every screen agrees:

Order cost = yarn cost + wages cost + machine cost
  - Yarn cost   = yarn consumed by the order × yarn rate.
      Primary: Σ over yarn_receipts linked to the order (quantity_kg × unit_cost).
      Fallback (receipts not linked to the order): the order's required yarn
      (order_items.required_qty_kg) × the AVERAGE purchase rate for that
      yarn_type+colour taken from yarn_receipts. The schema supports both; we
      prefer linked receipts and fall back to the average receipt rate.
  - Wages cost  = total wages PAID/accrued in the month, allocated to the order
      in proportion to the order's production output (metres) vs all output.
  - Machine cost= power + overhead only (machines.power_overhead_cost), allocated
      by the same output share. Operator wages are NOT in here — they come from
      the wages term above — so wages are never double-counted. If a machine has
      no power_overhead_cost set we fall back to MACHINE_POWER_SHARE × hourly_cost.

Order margin (estimate) = order revenue (invoiced amount for the month) − order
  cost. Labelled "estimate" in the UI.

Month net (cash basis — the real "did we make money this month?") =
  buyer payments received in the month
  − raw material (supplier) bills paid in the month
  − wages paid in the month.

Idle machine loss = idle+breakdown hours × FULL machine hourly_cost (an idle
  machine wastes the whole machine-hour, operator included). Unchanged.

All amounts in INR.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Invoice,
    Machine,
    Order,
    OrderItem,
    Payment,
    ProductionLog,
    Wage,
    YarnReceipt,
)
from app.services.production import idle_loss_for_machine, log_duration_hours

# When a machine's power_overhead_cost is not set, treat this share of the full
# hourly_cost as power+overhead (the rest being the operator wage we count via
# the wages module). Documented assumption; see PROJECT_STATE.md.
MACHINE_POWER_SHARE = 0.60


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Date-window helpers (a "month" is just start/end dates passed by the router)
# --------------------------------------------------------------------------- #
def _production_in_window(db: Session, start: date | None, end: date | None):
    q = db.query(ProductionLog)
    if start:
        q = q.filter(ProductionLog.log_date >= start)
    if end:
        q = q.filter(ProductionLog.log_date <= end)
    return q


def total_output_meters(db: Session, start: date | None, end: date | None) -> float:
    q = _production_in_window(db, start, end)
    return float(
        q.with_entities(func.coalesce(func.sum(ProductionLog.output_meters), 0)).scalar()
        or 0
    )


def order_output_meters(
    db: Session, order_id: int, start: date | None, end: date | None
) -> float:
    q = _production_in_window(db, start, end).filter(ProductionLog.order_id == order_id)
    return float(
        q.with_entities(func.coalesce(func.sum(ProductionLog.output_meters), 0)).scalar()
        or 0
    )


def _avg_receipt_rate(db: Session, yarn_type: str, colour: str) -> float:
    """Average purchase rate (₹/kg) for a yarn type+colour from receipts.

    Weighted by quantity so bulk buys dominate, which is the honest average cost.
    """
    row = (
        db.query(
            func.coalesce(func.sum(YarnReceipt.quantity_kg * YarnReceipt.unit_cost), 0),
            func.coalesce(func.sum(YarnReceipt.quantity_kg), 0),
        )
        .filter(YarnReceipt.yarn_type == yarn_type, YarnReceipt.colour == colour)
        .first()
    )
    value, qty = float(row[0] or 0), float(row[1] or 0)
    return (value / qty) if qty > 0 else 0.0


def order_yarn_cost(db: Session, order_id: int) -> float:
    """Yarn cost for an order.

    Prefer receipts explicitly linked to the order; otherwise estimate from the
    order's required yarn × the average purchase rate for that yarn type+colour.
    """
    linked = float(
        db.query(
            func.coalesce(func.sum(YarnReceipt.quantity_kg * YarnReceipt.unit_cost), 0)
        )
        .filter(YarnReceipt.order_id == order_id)
        .scalar()
        or 0
    )
    if linked > 0:
        return round(linked, 2)

    # Fallback: required yarn (from order_items) × average receipt rate.
    items = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
    est = 0.0
    for it in items:
        rate = _avg_receipt_rate(db, it.yarn_type, it.colour)
        est += float(it.required_qty_kg or 0) * rate
    return round(est, 2)


# --------------------------------------------------------------------------- #
# Wages / machine cost bases (month-windowed)
# --------------------------------------------------------------------------- #
def total_wages(db: Session, start: date | None, end: date | None) -> float:
    q = db.query(func.coalesce(func.sum(Wage.amount), 0))
    if start:
        q = q.filter(Wage.period_end >= start)
    if end:
        q = q.filter(Wage.period_start <= end)
    return float(q.scalar() or 0)


def wages_paid(db: Session, start: date | None, end: date | None) -> float:
    """Wages actually PAID in the window (cash basis, for Month net)."""
    q = db.query(func.coalesce(func.sum(Wage.amount), 0)).filter(Wage.status == "paid")
    if start:
        q = q.filter(func.date(Wage.paid_at) >= start)
    if end:
        q = q.filter(func.date(Wage.paid_at) <= end)
    return float(q.scalar() or 0)


def _machine_power_cost(m: Machine) -> float:
    """Power+overhead ₹/hr for a machine, excluding operator wages."""
    po = float(m.power_overhead_cost or 0)
    if po > 0:
        return po
    return round(float(m.hourly_cost or 0) * MACHINE_POWER_SHARE, 2)


def total_machine_power_basis(db: Session) -> float:
    """Sum of per-machine power+overhead ₹/hr — the basis for allocating machine
    cost across orders by output share (operator wages excluded)."""
    return float(sum(_machine_power_cost(m) for m in db.query(Machine).all()))


# --------------------------------------------------------------------------- #
# Order revenue (invoiced) within the window
# --------------------------------------------------------------------------- #
def order_invoiced_revenue(
    db: Session, order_id: int, start: date | None, end: date | None
) -> float:
    q = db.query(func.coalesce(func.sum(Invoice.total), 0)).filter(
        Invoice.order_id == order_id
    )
    if start:
        q = q.filter(func.date(Invoice.created_at) >= start)
    if end:
        q = q.filter(func.date(Invoice.created_at) <= end)
    return float(q.scalar() or 0)


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
def cost_per_order(
    db: Session, start: date | None = None, end: date | None = None
) -> list[dict]:
    orders = db.query(Order).order_by(Order.id).all()
    total_out = total_output_meters(db, start, end)
    wages_all = total_wages(db, start, end)
    machine_basis = total_machine_power_basis(db)

    rows = []
    for o in orders:
        out_m = order_output_meters(db, o.id, start, end)
        share = (out_m / total_out) if total_out > 0 else 0.0
        yarn = order_yarn_cost(db, o.id)
        wage_alloc = round(wages_all * share, 2)
        machine_alloc = round(machine_basis * share, 2)
        cost = round(yarn + wage_alloc + machine_alloc, 2)
        # Revenue: prefer the invoiced amount; fall back to output × rate when the
        # order has not been invoiced yet, clearly an estimate either way.
        invoiced = order_invoiced_revenue(db, o.id, start, end)
        revenue = invoiced if invoiced > 0 else round(out_m * float(o.unit_price), 2)
        rows.append(
            {
                "order_no": o.order_no,
                "status": o.status,
                "output_meters": round(out_m, 2),
                "yarn_cost": round(yarn, 2),
                "wage_cost": wage_alloc,
                "machine_cost": machine_alloc,
                "total_cost": cost,
                "revenue_est": round(revenue, 2),
                "margin_est": round(revenue - cost, 2),
            }
        )
    return rows


def machine_report(
    db: Session, start: date | None = None, end: date | None = None
) -> dict:
    now = _now()
    machines = db.query(Machine).order_by(Machine.name).all()
    rows = []
    top_reason_counts: dict[str, float] = {}
    for m in machines:
        out_q = _production_in_window(db, start, end).filter(
            ProductionLog.machine_id == m.id
        )
        output = float(
            out_q.with_entities(
                func.coalesce(func.sum(ProductionLog.output_meters), 0)
            ).scalar()
            or 0
        )
        loss = idle_loss_for_machine(db, m.id, float(m.hourly_cost or 0), now=now)
        running = _running_hours_for_machine(db, m.id, now)
        reason = _top_idle_reason_for_machine(db, m.id)
        if reason:
            top_reason_counts[reason] = top_reason_counts.get(reason, 0.0) + loss[
                "lost_hours"
            ]
        rows.append(
            {
                "machine": m.name,
                "type": m.type,
                "current_status": m.current_status,
                "total_output_meters": round(output, 2),
                "running_hours": round(running, 2),
                "idle_hours": loss["idle_hours"],
                "breakdown_hours": loss["breakdown_hours"],
                "idle_loss_rupees": loss["loss_rupees"],
                "top_idle_reason": reason or "—",
            }
        )
    totals = {
        "total_output_meters": round(sum(r["total_output_meters"] for r in rows), 2),
        "running_hours": round(sum(r["running_hours"] for r in rows), 2),
        "idle_hours": round(sum(r["idle_hours"] for r in rows), 2),
        "breakdown_hours": round(sum(r["breakdown_hours"] for r in rows), 2),
        "idle_loss_rupees": round(sum(r["idle_loss_rupees"] for r in rows), 2),
    }
    return {"machines": rows, "totals": totals}


def _running_hours_for_machine(db: Session, machine_id: int, now: datetime) -> float:
    from app.models import MachineStatusLog

    logs = (
        db.query(MachineStatusLog)
        .filter(
            MachineStatusLog.machine_id == machine_id,
            MachineStatusLog.status == "running",
        )
        .all()
    )
    return round(sum(log_duration_hours(log, until=now) for log in logs), 2)


def _top_idle_reason_for_machine(db: Session, machine_id: int) -> str | None:
    from app.models import MachineStatusLog

    logs = (
        db.query(MachineStatusLog)
        .filter(
            MachineStatusLog.machine_id == machine_id,
            MachineStatusLog.status.in_(("idle", "breakdown")),
        )
        .all()
    )
    by_reason: dict[str, float] = {}
    for log in logs:
        r = (log.reason or "Unspecified").strip() or "Unspecified"
        by_reason[r] = by_reason.get(r, 0.0) + log_duration_hours(log)
    if not by_reason:
        return None
    return max(by_reason.items(), key=lambda kv: kv[1])[0]


def idle_loss_by_reason(
    db: Session, start: date | None = None, end: date | None = None
) -> list[dict]:
    """Rupee idle loss grouped by reason, for the whole mill (dashboard chart)."""
    from app.models import MachineStatusLog

    machines = {m.id: m for m in db.query(Machine).all()}
    logs = (
        db.query(MachineStatusLog)
        .filter(MachineStatusLog.status.in_(("idle", "breakdown")))
        .all()
    )
    by_reason: dict[str, float] = {}
    now = _now()
    for log in logs:
        m = machines.get(log.machine_id)
        if not m:
            continue
        r = (log.reason or "Unspecified").strip() or "Unspecified"
        hrs = log_duration_hours(log, until=now)
        by_reason[r] = by_reason.get(r, 0.0) + hrs * float(m.hourly_cost or 0)
    rows = [
        {"reason": k, "loss_rupees": round(v, 2)}
        for k, v in sorted(by_reason.items(), key=lambda kv: -kv[1])
    ]
    return rows


def wages_report(
    db: Session, start: date | None = None, end: date | None = None
) -> dict:
    """Owner wages view for the month: total paid, per employee, per order.

    Per employee: days worked, daily rate, amount, paid/unpaid.
    Per order: wages allocated by production-output share (same basis as cost
    per order), so it ties out with the cost-per-order wage column.
    """
    from app.models import Employee

    wage_q = db.query(Wage)
    if start:
        wage_q = wage_q.filter(Wage.period_end >= start)
    if end:
        wage_q = wage_q.filter(Wage.period_start <= end)
    wages = wage_q.all()

    emps = {e.id: e for e in db.query(Employee).all()}
    per_employee = []
    total = 0.0
    total_paid = 0.0
    for w in wages:
        e = emps.get(w.employee_id)
        amt = float(w.amount or 0)
        total += amt
        if w.status == "paid":
            total_paid += amt
        per_employee.append(
            {
                "employee": e.name if e else "",
                "role_on_floor": (e.role_on_floor if e else "") or "",
                "days_present": float(w.days_present or 0),
                "daily_wage": float(e.daily_wage) if e else 0.0,
                "amount": round(amt, 2),
                "status": w.status,
                "period_start": w.period_start.isoformat(),
                "period_end": w.period_end.isoformat(),
            }
        )

    # Per order allocation (output share within the window).
    total_out = total_output_meters(db, start, end)
    per_order = []
    for o in db.query(Order).order_by(Order.id).all():
        out_m = order_output_meters(db, o.id, start, end)
        share = (out_m / total_out) if total_out > 0 else 0.0
        alloc = round(total * share, 2)
        if alloc > 0:
            per_order.append(
                {"order_no": o.order_no, "output_meters": round(out_m, 2),
                 "wages_allocated": alloc}
            )

    return {
        "total_wages": round(total, 2),
        "total_paid": round(total_paid, 2),
        "total_unpaid": round(total - total_paid, 2),
        "per_employee": per_employee,
        "per_order": per_order,
    }


def profit_or_loss(db: Session, start: date | None, end: date | None) -> dict:
    """Month (or any window) cash-basis net.

    income       = Σ incoming payments received in the window
    supplier_out = Σ outgoing payments made in the window (raw-material bills)
    wages        = Σ wage amounts in the window
    net          = income − supplier_out − wages
    """
    pay_q = db.query(Payment)
    if start:
        pay_q = pay_q.filter(func.date(Payment.paid_at) >= start)
    if end:
        pay_q = pay_q.filter(func.date(Payment.paid_at) <= end)
    payments = pay_q.all()

    income = sum(float(p.amount) for p in payments if p.direction == "incoming")
    supplier_out = sum(float(p.amount) for p in payments if p.direction == "outgoing")
    wages = total_wages(db, start, end)

    profit = round(income - supplier_out - wages, 2)
    return {
        "buyer_payments_in": round(income, 2),
        "supplier_payments_out": round(supplier_out, 2),
        "wages": round(wages, 2),
        "profit_or_loss": profit,
        "is_profit": profit >= 0,
    }

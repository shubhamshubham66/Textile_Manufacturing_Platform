"""Owner reporting math — scene 6: cost per order, machine report, profit/loss,
wages.

ONE definition set (also written in PROJECT_STATE.md), so every screen agrees.
Every figure is for the selected window (a calendar month by default): only
production, receipts, invoices, payments, wages and machine hours that fall
inside the window count, so an empty month shows zeros.

Order cost (for the month) = yarn cost + wages cost + machine cost
  - Yarn cost = yarn consumed by the order × yarn rate.
      a) Receipts linked to the order (yarn_receipts.order_id) received in the
         month: Σ quantity_kg × unit_cost.
      b) Orders with no linked receipts at all: estimate from what was produced
         in the month: the order's required yarn (order_items) × the share of
         the order made this month × the AVERAGE purchase rate for that yarn
         (quantity-weighted, from yarn_receipts). With no order_items, use
         metres made × YARN_KG_PER_METER × the average rate for the order's
         colour (or all yarn). Always an estimate, never ₹0 when yarn was used.
  - Wages cost = wages accrued in the month, allocated to orders by their share
      of the month's production output (metres).
  - Machine cost = power + overhead only: for each machine, running hours in
      the month × machines.power_overhead_cost (₹/hr), split across orders by
      that machine's output per order in the month. Operator wages are NOT in
      here (they are the wages term), so wages are never double-counted. If a
      machine has no power_overhead_cost we use MACHINE_POWER_SHARE × hourly_cost.

Order margin (estimate) = revenue − order cost, where revenue = amount invoiced
  in the month, else metres made × unit price. Labelled "estimate" in the UI.

Month net (cash basis — "did the mill make money this month?") =
  buyer payments received in the month
  − raw material (supplier) bills paid in the month
  − wages PAID in the month.
  Wages accrued but not yet paid are shown separately as "wages due".

Idle machine loss = idle+breakdown hours in the month × FULL machine
  hourly_cost (an idle machine wastes the whole machine-hour, operator
  included).

All amounts in INR.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Invoice,
    Machine,
    MachineStatusLog,
    Order,
    OrderItem,
    Payment,
    ProductionLog,
    Wage,
    YarnReceipt,
)
from app.services.production import idle_loss_for_machine, log_hours_in_window

# When a machine's power_overhead_cost is not set, treat this share of the full
# hourly_cost as power+overhead (the rest being the operator wage we count via
# the wages module). Documented assumption; see PROJECT_STATE.md.
MACHINE_POWER_SHARE = 0.60


def _now() -> datetime:
    return datetime.now(timezone.utc)


def window_bounds(start: date | None, end: date | None) -> tuple[datetime, datetime] | None:
    """[start 00:00, end+1 00:00) in UTC, or None for "all time"."""
    if start is None and end is None:
        return None
    lo = datetime.combine(start or date(1970, 1, 1), time.min, tzinfo=timezone.utc)
    hi = datetime.combine((end or date(2999, 12, 31)) + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return lo, hi


def _in_dates(q, column, start: date | None, end: date | None):
    if start:
        q = q.filter(func.date(column) >= start)
    if end:
        q = q.filter(func.date(column) <= end)
    return q


# --------------------------------------------------------------------------- #
# Production output
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


# --------------------------------------------------------------------------- #
# Yarn cost
# --------------------------------------------------------------------------- #
def _avg_receipt_rate(db: Session, yarn_type: str | None = None, colour: str | None = None) -> float:
    """Quantity-weighted average purchase rate (₹/kg) from receipts."""
    q = db.query(
        func.coalesce(func.sum(YarnReceipt.quantity_kg * YarnReceipt.unit_cost), 0),
        func.coalesce(func.sum(YarnReceipt.quantity_kg), 0),
    )
    if yarn_type:
        q = q.filter(YarnReceipt.yarn_type == yarn_type)
    if colour:
        q = q.filter(YarnReceipt.colour == colour)
    value, kg = q.first()
    value, kg = float(value or 0), float(kg or 0)
    return (value / kg) if kg > 0 else 0.0


def order_yarn_cost(
    db: Session, order: Order, start: date | None = None, end: date | None = None,
    made_m: float | None = None,
) -> tuple[float, str]:
    """(yarn cost for the window, basis) where basis is "linked" or "estimate"."""
    has_linked = (
        db.query(YarnReceipt.id).filter(YarnReceipt.order_id == order.id).first() is not None
    )
    if has_linked:
        q = db.query(func.coalesce(func.sum(YarnReceipt.quantity_kg * YarnReceipt.unit_cost), 0)).filter(
            YarnReceipt.order_id == order.id
        )
        q = _in_dates(q, YarnReceipt.received_at, start, end)
        return round(float(q.scalar() or 0), 2), "linked"

    made = order_output_meters(db, order.id, start, end) if made_m is None else made_m
    if made <= 0:
        return 0.0, "estimate"
    items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    if items:
        ordered = float(order.quantity_meters or 0)
        share = min(1.0, made / ordered) if ordered > 0 else 1.0
        est = 0.0
        for it in items:
            rate = _avg_receipt_rate(db, it.yarn_type, it.colour) or _avg_receipt_rate(db, colour=it.colour) or _avg_receipt_rate(db)
            est += float(it.required_qty_kg or 0) * share * rate
        return round(est, 2), "estimate"
    kg = made * float(get_settings().yarn_kg_per_meter)
    rate = _avg_receipt_rate(db, colour=order.colour) or _avg_receipt_rate(db)
    return round(kg * rate, 2), "estimate"


# --------------------------------------------------------------------------- #
# Wages
# --------------------------------------------------------------------------- #
def total_wages(db: Session, start: date | None, end: date | None) -> float:
    """Wages ACCRUED for work in the window (paid or not)."""
    q = db.query(func.coalesce(func.sum(Wage.amount), 0))
    if start:
        q = q.filter(Wage.period_end >= start)
    if end:
        q = q.filter(Wage.period_start <= end)
    return float(q.scalar() or 0)


def wages_paid(db: Session, start: date | None, end: date | None) -> float:
    """Wages actually PAID in the window (cash basis, for Month net)."""
    q = db.query(func.coalesce(func.sum(Wage.amount), 0)).filter(Wage.status == "paid")
    q = _in_dates(q, Wage.paid_at, start, end)
    return float(q.scalar() or 0)


# --------------------------------------------------------------------------- #
# Machine hours and machine (power + overhead) cost
# --------------------------------------------------------------------------- #
def _machine_power_cost(m: Machine) -> float:
    """Power+overhead ₹/hr for a machine, excluding operator wages."""
    po = float(m.power_overhead_cost or 0)
    if po > 0:
        return po
    return round(float(m.hourly_cost or 0) * MACHINE_POWER_SHARE, 2)


def _status_hours(db: Session, machine_id: int, statuses, window, now) -> float:
    logs = (
        db.query(MachineStatusLog)
        .filter(MachineStatusLog.machine_id == machine_id, MachineStatusLog.status.in_(statuses))
        .all()
    )
    return sum(log_hours_in_window(lg, window, until=now) for lg in logs)


def machine_cost_by_order(db: Session, start: date | None, end: date | None) -> dict[int, float]:
    """order_id -> machine cost (₹) in the window.

    Each machine's cost = running hours in the window × power+overhead ₹/hr,
    shared across the orders it produced for in the window by metres.
    """
    window = window_bounds(start, end)
    now = _now()
    out: dict[int, float] = {}
    for m in db.query(Machine).all():
        cost = _status_hours(db, m.id, ("running",), window, now) * _machine_power_cost(m)
        if cost <= 0:
            continue
        rows = (
            _production_in_window(db, start, end)
            .filter(ProductionLog.machine_id == m.id)
            .with_entities(ProductionLog.order_id, func.sum(ProductionLog.output_meters))
            .group_by(ProductionLog.order_id)
            .all()
        )
        made = sum(float(r[1] or 0) for r in rows)
        if made <= 0:
            continue  # ran but made nothing for an order: shows as machine time only
        for order_id, metres in rows:
            out[order_id] = out.get(order_id, 0.0) + cost * float(metres or 0) / made
    return out


# --------------------------------------------------------------------------- #
# Order revenue (invoiced) within the window
# --------------------------------------------------------------------------- #
def order_invoiced_revenue(
    db: Session, order_id: int, start: date | None, end: date | None
) -> float:
    q = db.query(func.coalesce(func.sum(Invoice.total), 0)).filter(Invoice.order_id == order_id)
    q = _in_dates(q, Invoice.created_at, start, end)
    return float(q.scalar() or 0)


def allocate(total: float, weights: dict) -> dict:
    """Split `total` by `weights`, rounded to paise, so the parts add up to the
    total exactly (the rounding remainder goes to the largest part)."""
    wsum = sum(w for w in weights.values() if w > 0)
    if total == 0 or wsum <= 0:
        return {k: 0.0 for k in weights}
    parts = {k: round(total * w / wsum, 2) if w > 0 else 0.0 for k, w in weights.items()}
    diff = round(round(total, 2) - sum(parts.values()), 2)
    if diff:
        big = max(parts, key=lambda k: parts[k])
        parts[big] = round(parts[big] + diff, 2)
    return parts


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
def cost_per_order(
    db: Session, start: date | None = None, end: date | None = None
) -> list[dict]:
    """One row per order with any activity in the window (production, linked
    yarn received, or an invoice). Orders with nothing in the window are left
    out, so an empty month returns no rows."""
    wages_all = total_wages(db, start, end)
    machine_cost = machine_cost_by_order(db, start, end)
    orders = db.query(Order).order_by(Order.id).all()
    made = {o.id: order_output_meters(db, o.id, start, end) for o in orders}
    wage_parts = allocate(wages_all, made)

    rows = []
    for o in orders:
        out_m = made[o.id]
        yarn, yarn_basis = order_yarn_cost(db, o, start, end, made_m=out_m)
        invoiced = order_invoiced_revenue(db, o.id, start, end)
        if out_m <= 0 and yarn <= 0 and invoiced <= 0:
            continue
        wage_alloc = wage_parts.get(o.id, 0.0)
        machine_alloc = round(machine_cost.get(o.id, 0.0), 2)
        cost = round(yarn + wage_alloc + machine_alloc, 2)
        # Revenue: prefer the amount invoiced in the month; otherwise metres made
        # × unit price. An estimate either way.
        revenue = invoiced if invoiced > 0 else round(out_m * float(o.unit_price or 0), 2)
        rows.append(
            {
                "order_no": o.order_no,
                "status": o.status,
                "output_meters": round(out_m, 2),
                "yarn_cost": round(yarn, 2),
                "yarn_basis": yarn_basis,
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
    window = window_bounds(start, end)
    rows = []
    for m in db.query(Machine).order_by(Machine.name).all():
        output = float(
            _production_in_window(db, start, end)
            .filter(ProductionLog.machine_id == m.id)
            .with_entities(func.coalesce(func.sum(ProductionLog.output_meters), 0))
            .scalar()
            or 0
        )
        loss = idle_loss_for_machine(db, m.id, float(m.hourly_cost or 0), now=now, window=window)
        running = _status_hours(db, m.id, ("running",), window, now)
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
                "top_idle_reason": _top_idle_reason_for_machine(db, m.id, window, now) or "—",
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


def _top_idle_reason_for_machine(db: Session, machine_id: int, window, now) -> str | None:
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
        h = log_hours_in_window(log, window, until=now)
        if h <= 0:
            continue
        r = (log.reason or "Unspecified").strip() or "Unspecified"
        by_reason[r] = by_reason.get(r, 0.0) + h
    if not by_reason:
        return None
    return max(by_reason.items(), key=lambda kv: kv[1])[0]


def idle_loss_total(db: Session, start: date | None = None, end: date | None = None) -> float:
    """Whole-mill idle+breakdown loss (₹) in the window."""
    window = window_bounds(start, end)
    now = _now()
    return round(
        sum(
            idle_loss_for_machine(db, m.id, float(m.hourly_cost or 0), now=now, window=window)["loss_rupees"]
            for m in db.query(Machine).all()
        ),
        2,
    )


def idle_loss_by_reason(
    db: Session, start: date | None = None, end: date | None = None
) -> list[dict]:
    """Rupee idle loss grouped by reason, for the whole mill, in the window."""
    window = window_bounds(start, end)
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
        hrs = log_hours_in_window(log, window, until=now)
        if hrs <= 0:
            continue
        r = (log.reason or "Unspecified").strip() or "Unspecified"
        by_reason[r] = by_reason.get(r, 0.0) + hrs * float(m.hourly_cost or 0)
    return [
        {"reason": k, "loss_rupees": round(v, 2)}
        for k, v in sorted(by_reason.items(), key=lambda kv: -kv[1])
    ]


def wages_report(
    db: Session, start: date | None = None, end: date | None = None
) -> dict:
    """Owner wages view for the month: total, paid, per employee, per order.

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

    orders = db.query(Order).order_by(Order.id).all()
    made = {o.id: order_output_meters(db, o.id, start, end) for o in orders}
    parts = allocate(round(total, 2), made)
    per_order = []
    for o in orders:
        out_m = made[o.id]
        alloc = parts.get(o.id, 0.0)
        if alloc > 0:
            per_order.append(
                {"order_no": o.order_no, "output_meters": round(out_m, 2),
                 "wages_allocated": alloc}
            )

    return {
        "total_wages": round(total, 2),
        "total_paid": round(total_paid, 2),
        "total_unpaid": round(total - total_paid, 2),
        "paid_in_month": round(wages_paid(db, start, end), 2),
        "per_employee": per_employee,
        "per_order": per_order,
    }


def profit_or_loss(db: Session, start: date | None, end: date | None) -> dict:
    """Month (or any window) cash-basis net — the one definition used by both
    the Dashboard card and Reports › Profit / loss.

    income       = Σ buyer payments received in the window
    supplier_out = Σ supplier (raw material) payments made in the window
    wages        = Σ wages PAID in the window
    net          = income − supplier_out − wages
    wages_due    = wages accrued for the window but not yet paid (context only)
    """
    pay_q = _in_dates(db.query(Payment), Payment.paid_at, start, end)
    payments = pay_q.all()

    income = sum(float(p.amount) for p in payments if p.direction == "incoming")
    supplier_out = sum(float(p.amount) for p in payments if p.direction == "outgoing")
    paid_wages = wages_paid(db, start, end)
    accrued = total_wages(db, start, end)
    unpaid_in_window = float(
        db.query(func.coalesce(func.sum(Wage.amount), 0))
        .filter(Wage.status != "paid")
        .filter(*( [Wage.period_end >= start] if start else []))
        .filter(*( [Wage.period_start <= end] if end else []))
        .scalar() or 0
    )

    profit = round(income - supplier_out - paid_wages, 2)
    return {
        "buyer_payments_in": round(income, 2),
        "supplier_payments_out": round(supplier_out, 2),
        "wages": round(paid_wages, 2),
        "wages_accrued": round(accrued, 2),
        "wages_due": round(unpaid_in_window, 2),
        "profit_or_loss": profit,
        "is_profit": profit >= 0,
    }

"""Owner reports + dashboard — scene 6.

Owner (resources "reports" / "dashboard"); every endpoint 403s for other roles.
All reports accept an optional month window via ?start=YYYY-MM-DD&end=YYYY-MM-DD.
When omitted they default to the CURRENT calendar month so a fresh page already
shows "this month".

  GET /api/reports/cost-per-order   yarn + wages + machine cost per order
  GET /api/reports/machines         output, running/idle/breakdown h, idle loss
  GET /api/reports/profit-loss      month cash-basis net (in − bills − wages paid)
  GET /api/reports/wages            owner wages view (total, per employee, order)
  GET /api/reports/dashboard        cards + orders-by-stage + idle loss by reason
"""

from __future__ import annotations

import calendar
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import require_resource
from app.models import Machine, Order, YarnStock
from app.services.reports import (
    cost_per_order,
    idle_loss_by_reason,
    idle_loss_total,
    machine_report,
    profit_or_loss,
    wages_report,
)

settings = get_settings()
router = APIRouter(prefix="/api/reports", tags=["reports"])


def _month_window(start: date | None, end: date | None) -> tuple[date, date]:
    """Resolve the reporting window. Default = the current calendar month.

    If only one bound is given we keep it and fill the other from the current
    month, so partial queries never explode.
    """
    today = date.today()
    if start is None and end is None:
        first = today.replace(day=1)
        last = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        return first, last
    if start is None:
        start = end.replace(day=1)
    if end is None:
        end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
    return start, end


@router.get("/cost-per-order")
def cost_per_order_report(
    start: date | None = Query(None),
    end: date | None = Query(None),
    _=Depends(require_resource("reports")),
    db: Session = Depends(get_db),
):
    s, e = _month_window(start, end)
    return {"start": s.isoformat(), "end": e.isoformat(), "rows": cost_per_order(db, s, e)}


@router.get("/machines")
def machines_report(
    start: date | None = Query(None),
    end: date | None = Query(None),
    _=Depends(require_resource("reports")),
    db: Session = Depends(get_db),
):
    s, e = _month_window(start, end)
    report = machine_report(db, s, e)
    return {"start": s.isoformat(), "end": e.isoformat(), **report}


@router.get("/profit-loss")
def profit_loss_report(
    start: date | None = Query(None),
    end: date | None = Query(None),
    _=Depends(require_resource("reports")),
    db: Session = Depends(get_db),
):
    s, e = _month_window(start, end)
    pl = profit_or_loss(db, s, e)
    return {"start": s.isoformat(), "end": e.isoformat(), **pl}


@router.get("/wages")
def wages_report_endpoint(
    start: date | None = Query(None),
    end: date | None = Query(None),
    _=Depends(require_resource("reports")),
    db: Session = Depends(get_db),
):
    s, e = _month_window(start, end)
    report = wages_report(db, s, e)
    return {"start": s.isoformat(), "end": e.isoformat(), **report}


@router.get("/dashboard")
def dashboard(
    start: date | None = Query(None),
    end: date | None = Query(None),
    _=Depends(require_resource("dashboard")),
    db: Session = Depends(get_db),
):
    s, e = _month_window(start, end)

    # Orders by stage (not date-filtered: it is the current pipeline snapshot).
    stage_rows = (
        db.query(Order.status, func.count(Order.id)).group_by(Order.status).all()
    )
    orders_by_stage = {status: int(c) for status, c in stage_rows}

    # Low stock (current snapshot).
    low = []
    for st in db.query(YarnStock).all():
        threshold = (
            float(st.reorder_level_kg)
            if st.reorder_level_kg and float(st.reorder_level_kg) > 0
            else settings.default_reorder_level_kg
        )
        if float(st.quantity_kg) <= threshold:
            low.append(
                {"yarn_type": st.yarn_type, "colour": st.colour,
                 "quantity_kg": float(st.quantity_kg)}
            )

    # Idle loss inside the selected month (same numbers as the Machine report).
    machines = db.query(Machine).all()
    total_idle_loss = idle_loss_total(db, s, e)

    # Month cash-basis net (matches Reports > Profit / loss exactly).
    pl = profit_or_loss(db, s, e)

    return {
        "start": s.isoformat(),
        "end": e.isoformat(),
        "machine_count": len(machines),
        "orders_by_stage": orders_by_stage,
        "low_stock_count": len(low),
        "low_stock": low,
        "idle_loss_rupees": round(total_idle_loss, 2),
        "idle_loss_by_reason": idle_loss_by_reason(db, s, e),
        "profit_loss": pl,
    }

"""Owner reports + dashboard — scene 6.

Owner (resources "reports" / "dashboard"):
  GET /api/reports/cost-per-order   yarn + wages + machine cost per order
  GET /api/reports/machines         output and idle loss per machine
  GET /api/reports/profit-loss      month P&L (payments in, bills + wages out)
  GET /api/reports/dashboard        key cards: orders by stage, low stock,
                                    idle loss, profit/loss
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import require_resource
from app.models import Machine, Order, YarnStock
from app.services.production import idle_loss_for_machine
from app.services.reports import (
    cost_per_order,
    machine_report,
    profit_or_loss,
)

settings = get_settings()
router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/cost-per-order")
def cost_per_order_report(
    _=Depends(require_resource("reports")),
    db: Session = Depends(get_db),
):
    return cost_per_order(db)


@router.get("/machines")
def machines_report(
    _=Depends(require_resource("reports")),
    db: Session = Depends(get_db),
):
    return machine_report(db)


@router.get("/profit-loss")
def profit_loss_report(
    start: date | None = Query(None),
    end: date | None = Query(None),
    _=Depends(require_resource("reports")),
    db: Session = Depends(get_db),
):
    return profit_or_loss(db, start, end)


@router.get("/dashboard")
def dashboard(
    _=Depends(require_resource("dashboard")),
    db: Session = Depends(get_db),
):
    # Orders by stage
    stage_rows = (
        db.query(Order.status, func.count(Order.id)).group_by(Order.status).all()
    )
    orders_by_stage = {s: int(c) for s, c in stage_rows}

    # Low stock
    low = []
    for s in db.query(YarnStock).all():
        threshold = (
            float(s.reorder_level_kg)
            if s.reorder_level_kg and float(s.reorder_level_kg) > 0
            else settings.default_reorder_level_kg
        )
        if float(s.quantity_kg) <= threshold:
            low.append(
                {"yarn_type": s.yarn_type, "colour": s.colour,
                 "quantity_kg": float(s.quantity_kg)}
            )

    # Idle loss (reuse production service)
    machines = db.query(Machine).all()
    total_idle_loss = 0.0
    for m in machines:
        total_idle_loss += idle_loss_for_machine(
            db, m.id, float(m.hourly_cost or 0)
        )["loss_rupees"]

    # Profit/loss (all time by default)
    pl = profit_or_loss(db, None, None)

    return {
        "orders_by_stage": orders_by_stage,
        "low_stock_count": len(low),
        "low_stock": low,
        "idle_loss_rupees": round(total_idle_loss, 2),
        "profit_loss": pl,
    }

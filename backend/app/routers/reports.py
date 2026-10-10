"""Owner reports + dashboard.

Owner (resources "reports" / "dashboard"):
  GET /api/reports/cost-per-order?month=YYYY-MM   yarn + wages + machine per order
  GET /api/reports/machines?month=YYYY-MM         output + hours + idle loss
  GET /api/reports/profit-loss?month=YYYY-MM      month net (cash basis)
  GET /api/reports/wages?month=YYYY-MM            wages paid: total / emp / order
  GET /api/reports/dashboard?month=YYYY-MM        cards + charts data
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import require_resource
from app.models import Machine, Order, YarnStock
from app.services.production import (
    idle_loss_by_reason,
    idle_loss_for_machine,
    order_display_progress,
)
from app.services.reports import (
    cost_per_order,
    machine_report,
    month_bounds,
    profit_or_loss,
    wages_report,
)

settings = get_settings()
router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/cost-per-order")
def cost_per_order_report(
    month: str | None = Query(None),
    _=Depends(require_resource("reports")),
    db: Session = Depends(get_db),
):
    return cost_per_order(db, month)


@router.get("/machines")
def machines_report(
    month: str | None = Query(None),
    _=Depends(require_resource("reports")),
    db: Session = Depends(get_db),
):
    return machine_report(db, month)


@router.get("/profit-loss")
def profit_loss_report(
    month: str | None = Query(None),
    _=Depends(require_resource("reports")),
    db: Session = Depends(get_db),
):
    return profit_or_loss(db, month)


@router.get("/wages")
def wages_report_endpoint(
    month: str | None = Query(None),
    _=Depends(require_resource("reports")),
    db: Session = Depends(get_db),
):
    return wages_report(db, month)


@router.get("/dashboard")
def dashboard(
    month: str | None = Query(None),
    _=Depends(require_resource("dashboard")),
    db: Session = Depends(get_db),
):
    start, _end = month_bounds(month)

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
            low.append({"yarn_type": s.yarn_type, "colour": s.colour,
                        "quantity_kg": float(s.quantity_kg)})

    # Idle loss total + by reason (month-independent snapshot of current logs)
    machines = db.query(Machine).order_by(Machine.name).all()
    total_idle_loss = 0.0
    machine_strip = []
    for mc in machines:
        detail = idle_loss_for_machine(db, mc.id, float(mc.hourly_cost or 0))
        total_idle_loss += detail["loss_rupees"]
        order_no = None
        today_m = 0.0
        if mc.current_order_id:
            o = db.query(Order).filter(Order.id == mc.current_order_id).first()
            order_no = o.order_no if o else None
        machine_strip.append({
            "name": mc.name, "type": mc.type, "status": mc.current_status,
            "order_no": order_no,
            "reason": detail["top_reason"] if mc.current_status in ("idle", "breakdown") else None,
        })

    pl = profit_or_loss(db, month)

    return {
        "month": f"{start:%Y-%m}",
        "orders_by_stage": orders_by_stage,
        "low_stock_count": len(low),
        "low_stock": low,
        "machine_count": len(machines),
        "idle_loss_rupees": round(total_idle_loss, 2),
        "idle_loss_by_reason": idle_loss_by_reason(db),
        "machine_strip": machine_strip,
        "profit_loss": pl,
    }

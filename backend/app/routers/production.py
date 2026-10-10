"""Production module — scene 2 + idle-machine loss (our unique feature).

Floor supervisor (resources "machines" / "production"):
  GET  /api/production/machines              list machines (status, order, progress)
  POST /api/production/machines/{id}/assign  link an order + stage to a machine
  POST /api/production/machines/{id}/status  change status; writes a log, closes prev
  POST /api/production/output                log metres produced per machine/shift
  GET  /api/production/output/today          today's output per machine
  PATCH /api/production/machines/{id}/hourly-cost  admin: set hourly cost
  GET  /api/production/idle-loss             idle hours × hourly cost per machine + total
  GET  /api/production/orders                confirmed+ orders (for the assign form)
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_resource
from app.models import Machine, MachineStatusLog, Order, ProductionLog
from app.services.production import (
    LOSS_STATUSES,
    idle_loss_for_machine,
    order_progress_percent,
)

router = APIRouter(prefix="/api/production", tags=["production"])

VALID_STATUSES = ("running", "idle", "breakdown")
VALID_STAGES = ("spinning", "weaving", "dyeing")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------- schemas --------------------------- #
class MachineOut(BaseModel):
    id: int
    name: str
    type: str
    current_status: str
    hourly_cost: float
    status_since: datetime
    current_order_id: int | None
    current_order_no: str | None
    current_stage: str | None
    progress_percent: float


class AssignRequest(BaseModel):
    order_id: int
    stage: str

    @field_validator("stage")
    @classmethod
    def _stage_ok(cls, v: str) -> str:
        if v not in VALID_STAGES:
            raise ValueError(f"stage must be one of {VALID_STAGES}")
        return v


class StatusRequest(BaseModel):
    status: str
    reason: str | None = None

    @field_validator("status")
    @classmethod
    def _status_ok(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")
        return v


class OutputRequest(BaseModel):
    machine_id: int
    order_id: int
    output_meters: float = Field(gt=0)
    stage: str | None = None
    shift: str | None = None  # informational; stored in reason-free output log


class HourlyCostRequest(BaseModel):
    hourly_cost: float = Field(ge=0)


# --------------------------- helpers --------------------------- #
def _machine_out(db: Session, m: Machine) -> MachineOut:
    order = None
    progress = 0.0
    if m.current_order_id:
        order = db.query(Order).filter(Order.id == m.current_order_id).first()
        if order:
            progress = order_progress_percent(db, order)
    return MachineOut(
        id=m.id,
        name=m.name,
        type=m.type,
        current_status=m.current_status,
        hourly_cost=float(m.hourly_cost or 0),
        status_since=m.status_since,
        current_order_id=m.current_order_id,
        current_order_no=order.order_no if order else None,
        current_stage=m.current_stage,
        progress_percent=progress,
    )


def _get_machine(db: Session, machine_id: int) -> Machine:
    m = db.query(Machine).filter(Machine.id == machine_id).first()
    if m is None:
        raise HTTPException(status_code=404, detail="Machine not found")
    return m


def _close_open_logs(db: Session, machine_id: int, when: datetime) -> None:
    """Close any open status-log windows for a machine."""
    open_logs = (
        db.query(MachineStatusLog)
        .filter(
            MachineStatusLog.machine_id == machine_id,
            MachineStatusLog.end_time.is_(None),
        )
        .all()
    )
    for log in open_logs:
        log.end_time = when


# --------------------------- endpoints --------------------------- #
@router.get("/machines", response_model=list[MachineOut])
def list_machines(
    _=Depends(require_resource("machines")),
    db: Session = Depends(get_db),
):
    rows = db.query(Machine).order_by(Machine.type, Machine.name).all()
    return [_machine_out(db, m) for m in rows]


@router.get("/orders")
def assignable_orders(
    _=Depends(require_resource("production")),
    db: Session = Depends(get_db),
):
    """Orders available to assign to a machine (confirmed and in-progress)."""
    rows = (
        db.query(Order)
        .filter(Order.status.in_(("confirmed", "in_production", "in_quality")))
        .order_by(Order.id.desc())
        .all()
    )
    return [
        {"id": o.id, "order_no": o.order_no, "fabric_type": o.fabric_type,
         "colour": o.colour, "status": o.status}
        for o in rows
    ]


@router.post("/machines/{machine_id}/assign", response_model=MachineOut)
def assign_machine(
    machine_id: int,
    body: AssignRequest,
    _=Depends(require_resource("production")),
    db: Session = Depends(get_db),
):
    m = _get_machine(db, machine_id)
    order = db.query(Order).filter(Order.id == body.order_id).first()
    if order is None:
        raise HTTPException(status_code=400, detail="Unknown order")

    m.current_order_id = order.id
    m.current_stage = body.stage
    # Assigning work moves the order into production.
    if order.status == "confirmed":
        order.status = "in_production"
    db.commit()
    db.refresh(m)
    return _machine_out(db, m)


@router.post("/machines/{machine_id}/status", response_model=MachineOut)
def update_status(
    machine_id: int,
    body: StatusRequest,
    _=Depends(require_resource("machines")),
    db: Session = Depends(get_db),
):
    m = _get_machine(db, machine_id)

    # Reason is required for Idle and Breakdown.
    if body.status in LOSS_STATUSES and not (body.reason and body.reason.strip()):
        raise HTTPException(
            status_code=400,
            detail=f"A reason is required when setting status to '{body.status}'",
        )

    now = _now()
    # Close the previous open window, then open a new one.
    _close_open_logs(db, m.id, now)
    db.add(
        MachineStatusLog(
            machine_id=m.id,
            status=body.status,
            start_time=now,
            end_time=None,
            reason=(body.reason.strip() if body.reason else None),
        )
    )
    m.current_status = body.status
    m.status_since = now
    db.commit()
    db.refresh(m)
    return _machine_out(db, m)


@router.post("/output")
def log_output(
    body: OutputRequest,
    _=Depends(require_resource("production")),
    db: Session = Depends(get_db),
):
    m = _get_machine(db, body.machine_id)
    order = db.query(Order).filter(Order.id == body.order_id).first()
    if order is None:
        raise HTTPException(status_code=400, detail="Unknown order")

    stage = body.stage or m.current_stage or m.type
    db.add(
        ProductionLog(
            machine_id=m.id,
            order_id=order.id,
            stage=stage,
            output_meters=body.output_meters,
            log_date=date.today(),
        )
    )
    db.flush()
    progress = order_progress_percent(db, order)
    # Keep order status moving as output accrues.
    if order.status == "confirmed":
        order.status = "in_production"
    db.commit()
    return {
        "ok": True,
        "machine_id": m.id,
        "order_id": order.id,
        "order_no": order.order_no,
        "logged_meters": body.output_meters,
        "order_progress_percent": progress,
    }


@router.get("/output/today")
def output_today(
    _=Depends(require_resource("production")),
    db: Session = Depends(get_db),
):
    today = date.today()
    rows = (
        db.query(
            ProductionLog.machine_id,
            func.coalesce(func.sum(ProductionLog.output_meters), 0),
        )
        .filter(ProductionLog.log_date == today)
        .group_by(ProductionLog.machine_id)
        .all()
    )
    totals = {mid: float(total) for mid, total in rows}
    machines = db.query(Machine).order_by(Machine.type, Machine.name).all()
    return [
        {"machine_id": m.id, "machine_name": m.name,
         "output_meters_today": totals.get(m.id, 0.0)}
        for m in machines
    ]


@router.patch("/machines/{machine_id}/hourly-cost", response_model=MachineOut)
def set_hourly_cost(
    machine_id: int,
    body: HourlyCostRequest,
    _=Depends(require_resource("machines")),
    db: Session = Depends(get_db),
):
    m = _get_machine(db, machine_id)
    m.hourly_cost = body.hourly_cost
    db.commit()
    db.refresh(m)
    return _machine_out(db, m)


@router.get("/idle-loss")
def idle_loss(
    _=Depends(require_resource("machines")),
    db: Session = Depends(get_db),
):
    """Idle+breakdown hours and rupee loss per machine, a grand total, and the
    top reasons by lost hours. This is the dashboard card for our USP."""
    now = _now()
    machines = db.query(Machine).order_by(Machine.name).all()

    per_machine = []
    total_loss = 0.0
    total_hours = 0.0
    for m in machines:
        detail = idle_loss_for_machine(db, m.id, float(m.hourly_cost or 0), now=now)
        total_loss += detail["loss_rupees"]
        total_hours += detail["lost_hours"]
        if detail["lost_hours"] > 0:
            per_machine.append(
                {
                    "machine_id": m.id,
                    "machine_name": m.name,
                    "current_status": m.current_status,
                    "hourly_cost": float(m.hourly_cost or 0),
                    **detail,
                }
            )

    # Top reasons by total lost hours across idle/breakdown logs.
    reason_rows = (
        db.query(MachineStatusLog)
        .filter(MachineStatusLog.status.in_(LOSS_STATUSES))
        .all()
    )
    from app.services.production import log_duration_hours

    reason_hours: dict[str, float] = {}
    for log in reason_rows:
        label = log.reason or "(no reason)"
        reason_hours[label] = reason_hours.get(label, 0.0) + log_duration_hours(
            log, until=now
        )
    top_reasons = sorted(
        ({"reason": r, "hours": round(h, 2)} for r, h in reason_hours.items()),
        key=lambda x: x["hours"],
        reverse=True,
    )[:5]

    return {
        "total_loss_rupees": round(total_loss, 2),
        "total_lost_hours": round(total_hours, 2),
        "per_machine": sorted(
            per_machine, key=lambda x: x["loss_rupees"], reverse=True
        ),
        "top_reasons": top_reasons,
    }

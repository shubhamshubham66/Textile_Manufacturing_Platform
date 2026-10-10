"""Quality module — scene 3.

Quality inspector (resources "quality" / "rolls"):
  POST /api/quality/rolls              create a roll (Pending), unique roll no
  GET  /api/quality/rolls              list rolls, optional ?status filter
  POST /api/quality/rolls/{id}/inspect pass | rework | reject (+ defect + notes)
  GET  /api/quality/defect-report      counts by defect, machine and order
  GET  /api/quality/_meta              orders + machines for the new-roll form
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_resource
from app.models import Machine, Order, QualityInspection, Roll, User

router = APIRouter(prefix="/api/quality", tags=["quality"])

VALID_RESULTS = ("pass", "rework", "reject")
VALID_DEFECTS = ("none", "hole", "colour_mismatch", "uneven_weaving", "other")


# --------------------------- schemas --------------------------- #
class RollCreate(BaseModel):
    order_id: int
    machine_id: int
    length_meters: float = Field(gt=0)


class RollOut(BaseModel):
    id: int
    roll_no: str
    order_id: int
    order_no: str
    machine_id: int
    machine_name: str
    length_meters: float
    status: str
    defect_type: str | None = None
    created_at: datetime


class InspectRequest(BaseModel):
    result: str
    defect_type: str = "none"
    notes: str | None = None

    @field_validator("result")
    @classmethod
    def _result_ok(cls, v: str) -> str:
        if v not in VALID_RESULTS:
            raise ValueError(f"result must be one of {VALID_RESULTS}")
        return v

    @field_validator("defect_type")
    @classmethod
    def _defect_ok(cls, v: str) -> str:
        if v not in VALID_DEFECTS:
            raise ValueError(f"defect_type must be one of {VALID_DEFECTS}")
        return v


def _roll_out(db: Session, r: Roll) -> RollOut:
    order = db.query(Order).filter(Order.id == r.order_id).first()
    machine = db.query(Machine).filter(Machine.id == r.machine_id).first()
    insp = (
        db.query(QualityInspection)
        .filter(QualityInspection.roll_id == r.id)
        .order_by(QualityInspection.id.desc())
        .first()
    )
    return RollOut(
        id=r.id,
        roll_no=r.roll_no,
        order_id=r.order_id,
        order_no=order.order_no if order else "",
        machine_id=r.machine_id,
        machine_name=machine.name if machine else "",
        length_meters=float(r.length_meters),
        status=r.status,
        defect_type=insp.defect_type if insp else None,
        created_at=r.created_at,
    )


def _next_roll_no(db: Session) -> str:
    n = db.query(func.count(Roll.id)).scalar() or 0
    return f"R-{n + 1:04d}"


# --------------------------- endpoints --------------------------- #
@router.get("/_meta")
def meta(
    _=Depends(require_resource("rolls")),
    db: Session = Depends(get_db),
):
    orders = db.query(Order).order_by(Order.id.desc()).all()
    machines = db.query(Machine).order_by(Machine.name).all()
    return {
        "orders": [
            {"id": o.id, "order_no": o.order_no, "fabric_type": o.fabric_type}
            for o in orders
        ],
        "machines": [{"id": m.id, "name": m.name} for m in machines],
        "defect_types": list(VALID_DEFECTS),
    }


@router.post("/rolls", response_model=RollOut, status_code=201)
def create_roll(
    body: RollCreate,
    _=Depends(require_resource("rolls")),
    db: Session = Depends(get_db),
):
    if db.query(Order).filter(Order.id == body.order_id).first() is None:
        raise HTTPException(status_code=400, detail="Unknown order")
    if db.query(Machine).filter(Machine.id == body.machine_id).first() is None:
        raise HTTPException(status_code=400, detail="Unknown machine")

    roll = Roll(
        roll_no=_next_roll_no(db),
        order_id=body.order_id,
        machine_id=body.machine_id,
        length_meters=body.length_meters,
        status="pending",
    )
    db.add(roll)
    db.commit()
    db.refresh(roll)
    return _roll_out(db, roll)


@router.get("/rolls", response_model=list[RollOut])
def list_rolls(
    status: str | None = Query(None, description="pending|pass|rework|reject|dispatched"),
    order_id: int | None = Query(None),
    _=Depends(require_resource("rolls")),
    db: Session = Depends(get_db),
):
    q = db.query(Roll)
    if status:
        q = q.filter(Roll.status == status)
    if order_id:
        q = q.filter(Roll.order_id == order_id)
    rolls = q.order_by(Roll.id.desc()).all()
    return [_roll_out(db, r) for r in rolls]


@router.post("/rolls/{roll_id}/inspect", response_model=RollOut)
def inspect_roll(
    roll_id: int,
    body: InspectRequest,
    user: User = Depends(require_resource("quality")),
    db: Session = Depends(get_db),
):
    roll = db.query(Roll).filter(Roll.id == roll_id).first()
    if roll is None:
        raise HTTPException(status_code=404, detail="Roll not found")
    if roll.status == "dispatched":
        raise HTTPException(
            status_code=409, detail="Roll is already dispatched and cannot be re-inspected"
        )

    # A pass with a defect, or a fail without one, is inconsistent.
    if body.result == "pass" and body.defect_type != "none":
        raise HTTPException(
            status_code=400, detail="A passed roll must not have a defect type"
        )
    if body.result in ("rework", "reject") and body.defect_type == "none":
        raise HTTPException(
            status_code=400,
            detail="A reworked or rejected roll must have a defect type",
        )

    db.add(
        QualityInspection(
            roll_id=roll.id,
            inspector_user_id=user.id,
            result=body.result,
            defect_type=body.defect_type,
            notes=body.notes,
        )
    )
    roll.status = body.result  # pass|rework|reject
    db.commit()
    db.refresh(roll)
    return _roll_out(db, roll)


@router.get("/defect-report")
def defect_report(
    _=Depends(require_resource("quality")),
    db: Session = Depends(get_db),
):
    # Counts by defect type (rework+reject only).
    by_defect = (
        db.query(QualityInspection.defect_type, func.count(QualityInspection.id))
        .filter(QualityInspection.result.in_(("rework", "reject")))
        .group_by(QualityInspection.defect_type)
        .all()
    )
    # Counts by machine (join via roll).
    by_machine = (
        db.query(Machine.name, func.count(QualityInspection.id))
        .join(Roll, Roll.machine_id == Machine.id)
        .join(QualityInspection, QualityInspection.roll_id == Roll.id)
        .filter(QualityInspection.result.in_(("rework", "reject")))
        .group_by(Machine.name)
        .all()
    )
    # Counts by order.
    by_order = (
        db.query(Order.order_no, func.count(QualityInspection.id))
        .join(Roll, Roll.order_id == Order.id)
        .join(QualityInspection, QualityInspection.roll_id == Roll.id)
        .filter(QualityInspection.result.in_(("rework", "reject")))
        .group_by(Order.order_no)
        .all()
    )
    # Roll status tallies.
    status_counts = dict(
        db.query(Roll.status, func.count(Roll.id)).group_by(Roll.status).all()
    )

    return {
        "by_defect": [{"defect_type": d or "none", "count": c} for d, c in by_defect],
        "by_machine": [{"machine": n, "count": c} for n, c in by_machine],
        "by_order": [{"order_no": o, "count": c} for o, c in by_order],
        "roll_status_counts": {k: int(v) for k, v in status_counts.items()},
    }

"""Attendance & wages — scene 6 (part 2).

Accountant (resources "attendance" / "wages"):
  GET  /api/wages/employees           employees + today's attendance status
  POST /api/attendance                mark attendance (present/absent/half_day, shift)
  GET  /api/attendance                attendance rows (optional ?date)
  POST /api/wages/calculate           compute wages for a period (days×rate + overtime)
  GET  /api/wages                     list wage records
  POST /api/wages/{id}/pay            mark a wage paid

Wage cost is allocated to orders in the reports module, proportional to each
order's production output. See services/reports.py.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_resource
from app.models import Attendance, Employee, Wage

router = APIRouter(tags=["wages"])

VALID_STATUS = ("present", "absent", "half_day")
VALID_SHIFT = ("morning", "evening", "night")
OVERTIME_RATE_PER_HOUR = 80.0  # ₹/hr beyond 8h, demo value
STANDARD_HOURS = 8.0


# --------------------------- schemas --------------------------- #
class AttendanceRequest(BaseModel):
    employee_id: int
    work_date: date | None = None
    shift: str = "morning"
    status: str = "present"
    hours_worked: float = Field(default=8, ge=0)

    @field_validator("status")
    @classmethod
    def _s(cls, v: str) -> str:
        if v not in VALID_STATUS:
            raise ValueError(f"status must be one of {VALID_STATUS}")
        return v

    @field_validator("shift")
    @classmethod
    def _sh(cls, v: str) -> str:
        if v not in VALID_SHIFT:
            raise ValueError(f"shift must be one of {VALID_SHIFT}")
        return v


class CalculateRequest(BaseModel):
    period_start: date
    period_end: date


# --------------------------- attendance --------------------------- #
@router.get("/api/wages/employees")
def employees_today(
    _=Depends(require_resource("attendance")),
    db: Session = Depends(get_db),
):
    today = date.today()
    emps = db.query(Employee).order_by(Employee.name).all()
    out = []
    for e in emps:
        att = (
            db.query(Attendance)
            .filter(Attendance.employee_id == e.id, Attendance.work_date == today)
            .first()
        )
        out.append(
            {
                "id": e.id,
                "name": e.name,
                "role_on_floor": e.role_on_floor,
                "daily_wage": float(e.daily_wage),
                "today_status": att.status if att else None,
            }
        )
    return out


@router.post("/api/attendance")
def mark_attendance(
    body: AttendanceRequest,
    _=Depends(require_resource("attendance")),
    db: Session = Depends(get_db),
):
    emp = db.query(Employee).filter(Employee.id == body.employee_id).first()
    if emp is None:
        raise HTTPException(status_code=400, detail="Unknown employee")

    wd = body.work_date or date.today()
    # Upsert: one row per employee+date.
    row = (
        db.query(Attendance)
        .filter(Attendance.employee_id == emp.id, Attendance.work_date == wd)
        .first()
    )
    if row is None:
        row = Attendance(employee_id=emp.id, work_date=wd)
        db.add(row)
    row.shift = body.shift
    row.status = body.status
    row.hours_worked = body.hours_worked if body.status != "absent" else 0
    db.commit()
    db.refresh(row)
    return {
        "ok": True,
        "employee": emp.name,
        "work_date": wd.isoformat(),
        "status": row.status,
        "shift": row.shift,
        "hours_worked": float(row.hours_worked),
    }


@router.get("/api/attendance")
def list_attendance(
    date_filter: date | None = Query(None, alias="date"),
    _=Depends(require_resource("attendance")),
    db: Session = Depends(get_db),
):
    q = db.query(Attendance)
    if date_filter:
        q = q.filter(Attendance.work_date == date_filter)
    rows = q.order_by(Attendance.work_date.desc(), Attendance.employee_id).all()
    out = []
    for a in rows:
        emp = db.query(Employee).filter(Employee.id == a.employee_id).first()
        out.append(
            {
                "id": a.id,
                "employee": emp.name if emp else "",
                "work_date": a.work_date.isoformat(),
                "shift": a.shift,
                "status": a.status,
                "hours_worked": float(a.hours_worked),
            }
        )
    return out


# --------------------------- wages --------------------------- #
@router.post("/api/wages/calculate")
def calculate_wages(
    body: CalculateRequest,
    _=Depends(require_resource("wages")),
    db: Session = Depends(get_db),
):
    """Compute a wage record per employee for the period:
    amount = (present=1, half_day=0.5) × daily_wage + overtime(hours>8 × rate).
    Idempotent per (employee, period): replaces an existing pending record."""
    if body.period_end < body.period_start:
        raise HTTPException(status_code=400, detail="period_end before period_start")

    emps = db.query(Employee).all()
    results = []
    for e in emps:
        atts = (
            db.query(Attendance)
            .filter(
                Attendance.employee_id == e.id,
                Attendance.work_date >= body.period_start,
                Attendance.work_date <= body.period_end,
            )
            .all()
        )
        days = 0.0
        overtime = 0.0
        for a in atts:
            if a.status == "present":
                days += 1.0
            elif a.status == "half_day":
                days += 0.5
            extra = float(a.hours_worked) - STANDARD_HOURS
            if extra > 0:
                overtime += extra * OVERTIME_RATE_PER_HOUR
        amount = round(days * float(e.daily_wage) + overtime, 2)

        existing = (
            db.query(Wage)
            .filter(
                Wage.employee_id == e.id,
                Wage.period_start == body.period_start,
                Wage.period_end == body.period_end,
            )
            .first()
        )
        if existing and existing.status == "pending":
            existing.days_present = days
            existing.amount = amount
            wage = existing
        elif existing and existing.status == "paid":
            wage = existing  # don't overwrite a paid record
        else:
            wage = Wage(
                employee_id=e.id,
                period_start=body.period_start,
                period_end=body.period_end,
                days_present=days,
                amount=amount,
                status="pending",
            )
            db.add(wage)
        db.flush()
        results.append(
            {
                "wage_id": wage.id,
                "employee": e.name,
                "days_present": days,
                "overtime": round(overtime, 2),
                "amount": float(wage.amount),
                "status": wage.status,
            }
        )
    db.commit()
    return {"period": [body.period_start.isoformat(), body.period_end.isoformat()],
            "wages": results,
            "total": round(sum(r["amount"] for r in results), 2)}


@router.get("/api/wages")
def list_wages(
    _=Depends(require_resource("wages")),
    db: Session = Depends(get_db),
):
    rows = db.query(Wage).order_by(Wage.id.desc()).all()
    out = []
    for w in rows:
        emp = db.query(Employee).filter(Employee.id == w.employee_id).first()
        out.append(
            {
                "id": w.id,
                "employee": emp.name if emp else "",
                "period_start": w.period_start.isoformat(),
                "period_end": w.period_end.isoformat(),
                "days_present": float(w.days_present),
                "amount": float(w.amount),
                "status": w.status,
                "paid_at": w.paid_at,
            }
        )
    return out


@router.post("/api/wages/{wage_id}/pay")
def pay_wage(
    wage_id: int,
    _=Depends(require_resource("wages")),
    db: Session = Depends(get_db),
):
    w = db.query(Wage).filter(Wage.id == wage_id).first()
    if w is None:
        raise HTTPException(status_code=404, detail="Wage record not found")
    if w.status == "paid":
        raise HTTPException(status_code=409, detail="Wage already paid")
    w.status = "paid"
    w.paid_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "wage_id": w.id, "status": "paid"}

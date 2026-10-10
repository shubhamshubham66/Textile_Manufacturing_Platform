"""My tasks — instructions from the Supermanager, for department managers.

A department manager sees the tasks for their department, hands each to one
of their workers, and posts progress updates (status + note).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session

from datetime import date, timezone

from app.database import get_db
from app.departments import DEPT_LABEL, dept_of
from app.deps import get_current_user, require_resource
from app.models import Attendance, Employee, Task, TaskUpdate, User
from app.services import super_data as sd

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _mine(db: Session, user: User):
    """Tasks this manager can see and work on.

    A manager sees every task in the department(s) they run — not only the ones
    directly assigned to them. This way a newly-created department manager (made
    by the Supermanager) sees the same department instructions as the existing
    manager, instead of an empty list because the auto-tasks were stamped with
    another manager's id. Tasks explicitly assigned to this user are always
    included too.
    """
    from app.routers.purchase import _my_depts

    depts = _my_depts(user)
    return db.query(Task).filter(or_(Task.manager_user_id == user.id,
                                     Task.department.in_(depts)))


@router.get("/mine")
def my_tasks(user: User = Depends(get_current_user), _=Depends(require_resource("my_tasks")),
             db: Session = Depends(get_db)):
    dept = dept_of(user)
    rows = [sd.task_row(db, t) for t in _mine(db, user).order_by(Task.id.desc()).all()]
    workers = (db.query(Employee).filter(Employee.is_active.isnot(False),
                                         or_(Employee.department == dept, Employee.manager_user_id == user.id))
               .order_by(Employee.name).all())
    return {"department": dept, "department_label": DEPT_LABEL.get(dept, ""), "tasks": rows,
            "workers": [{"id": w.id, "name": w.name} for w in workers]}


class ProgressIn(BaseModel):
    status: str
    note: str | None = Field(default=None, max_length=1000)
    worker_employee_id: int | None = None

    @field_validator("status")
    @classmethod
    def _st(cls, v):
        if v not in ("pending", "in_progress", "completed"):
            raise ValueError("status must be pending, in_progress or completed")
        return v


@router.post("/{task_id}/progress")
def post_progress(task_id: int, body: ProgressIn, user: User = Depends(get_current_user),
                  _=Depends(require_resource("my_tasks")), db: Session = Depends(get_db)):
    t = _mine(db, user).filter(Task.id == task_id).first()
    if t is None:
        raise HTTPException(404, "Task not found")  # not yours = not found
    if "worker_employee_id" in body.model_fields_set:
        if body.worker_employee_id is not None and db.get(Employee, body.worker_employee_id) is None:
            raise HTTPException(400, "Unknown worker")
        t.worker_employee_id = body.worker_employee_id
    if t.manager_user_id is None:
        t.manager_user_id = user.id  # whoever picks up an unassigned task owns it
    t.status = body.status
    t.updated_at = datetime.utcnow()
    db.add(TaskUpdate(task_id=t.id, user_id=user.id, status=body.status, note=(body.note or "").strip() or None))
    db.commit()
    return sd.task_row(db, t)


# --------------------------------------------------------------------------- #
# Worker attendance verification (manager verifies before Accounts uses wages)
# --------------------------------------------------------------------------- #
def _my_workers(db: Session, user: User):
    """Employees in this manager's department(s) or reporting to them."""
    dept = dept_of(user)
    return db.query(Employee).filter(
        or_(Employee.manager_user_id == user.id, Employee.department == dept)
    )


@router.get("/attendance")
def workers_attendance(
    work_date: date | None = None,
    user: User = Depends(get_current_user),
    _=Depends(require_resource("my_tasks")),
    db: Session = Depends(get_db),
):
    """Attendance for this manager's workers (default: today), with what still
    needs verification before Accounts can use it for wages."""
    day = work_date or date.today()
    emp_ids = [e.id for e in _my_workers(db, user).all()]
    names = {e.id: e.name for e in db.query(Employee).filter(Employee.id.in_(emp_ids or [0])).all()}
    rows = (
        db.query(Attendance)
        .filter(Attendance.employee_id.in_(emp_ids or [0]), Attendance.work_date == day)
        .order_by(Attendance.employee_id)
        .all()
    )
    out = []
    for a in rows:
        out.append({
            "id": a.id, "employee": names.get(a.employee_id, ""),
            "status": a.status, "shift": a.shift,
            "hours_worked": float(a.hours_worked or 0),
            "overtime_hours": float(getattr(a, "overtime_hours", 0) or 0),
            "check_in": a.check_in.isoformat() if getattr(a, "check_in", None) else None,
            "check_out": a.check_out.isoformat() if getattr(a, "check_out", None) else None,
            "source": getattr(a, "source", "manager"),
            "verified": bool(getattr(a, "verified", False)),
        })
    return {"day": day.isoformat(), "rows": out,
            "pending_verification": sum(1 for r in out if not r["verified"])}


@router.post("/attendance/{attendance_id}/verify")
def verify_attendance(
    attendance_id: int,
    user: User = Depends(get_current_user),
    _=Depends(require_resource("my_tasks")),
    db: Session = Depends(get_db),
):
    """Verify a worker's attendance/overtime so Accounts can use it for wages.
    Only the worker's own department manager may verify (else 404)."""
    a = db.get(Attendance, attendance_id)
    if a is None:
        raise HTTPException(404, "Attendance record not found")
    emp = db.get(Employee, a.employee_id)
    allowed = {e.id for e in _my_workers(db, user).all()}
    if emp is None or emp.id not in allowed:
        raise HTTPException(404, "Attendance record not found")  # not your worker
    a.verified = True
    a.verified_by_user_id = user.id
    a.verified_at = datetime.utcnow()
    # Tell Accounts the verified attendance is ready for wage processing.
    from app.models import Notification
    from app import rbac as _rbac

    db.add(Notification(to_role=_rbac.ROLE_ACCOUNTS_MANAGER, kind="info",
                        title="Verified attendance ready for wages",
                        body=f"{emp.name}: {a.work_date.isoformat()} verified by {user.name}",
                        from_user_name=user.name))
    db.commit()
    return {"ok": True, "attendance_id": a.id, "verified": True}

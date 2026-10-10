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

from app.database import get_db
from app.departments import DEPT_LABEL, dept_of
from app.deps import get_current_user, require_resource
from app.models import Employee, Task, TaskUpdate, User
from app.services import super_data as sd

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _mine(db: Session, user: User):
    from app.routers.purchase import _my_depts

    depts = _my_depts(user)
    return db.query(Task).filter(or_(Task.manager_user_id == user.id,
                                     Task.department.in_(depts) & Task.manager_user_id.is_(None)))


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

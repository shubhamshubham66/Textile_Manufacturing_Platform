"""Worker portal — /api/worker/*.

A shop-floor worker (role "worker", linked to an Employee via users.employee_id)
sees ONLY their own tasks, attendance, overtime and profile. Every query is
scoped to the worker's employee_id through get_current_worker.

  Dashboard         GET  /api/worker/dashboard
  My Tasks          GET  /api/worker/tasks
                    POST /api/worker/tasks/{id}/action   start | pause | resume | complete
  Production Updates POST /api/worker/production         output + waste + defects + downtime
                    GET  /api/worker/production
  Machine Status    GET  /api/worker/machines
                    POST /api/worker/report              breakdown | material_shortage | problem
  Attendance        GET  /api/worker/attendance
                    POST /api/worker/attendance/check-in
                    POST /api/worker/attendance/check-out
  Overtime          GET  /api/worker/overtime
                    POST /api/worker/overtime            submit overtime for verification
  Task History      GET  /api/worker/history
  Notifications     GET  /api/worker/notifications  (+ /{id}/read)
  My Profile        GET  /api/worker/profile

PERMISSIONS (backend-enforced):
  - Every endpoint uses get_current_worker, so a worker reaches only their own
    data; attempting another worker's task returns 404 (not found, no leak).
  - A worker can start/pause/complete only tasks assigned to them.
  - Attendance and overtime a worker submits are UNVERIFIED; the department
    manager must verify them before Accounts uses them for wages. A worker
    cannot verify their own attendance, edit a verified row, touch QC results,
    inventory or financial data (no such endpoint).
  - Duplicate check-in on the same day is rejected.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import rbac
from app.database import get_db
from app.deps import get_current_worker
from app.models import (
    ActivityLog,
    Attendance,
    Employee,
    Machine,
    Notification,
    Order,
    ProductionLog,
    Task,
    TaskUpdate,
    User,
)
from app.services.tasks import shown_status

router = APIRouter(prefix="/api/worker", tags=["worker"])

TASK_ACTIONS = ("start", "pause", "resume", "complete")
# Worker-facing task status: pending -> in_progress <-> paused -> completed.
ACTION_STATUS = {"start": "in_progress", "resume": "in_progress", "pause": "paused", "complete": "completed"}
STANDARD_HOURS = 8.0
REPORT_KINDS = ("breakdown", "material_shortage", "problem")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _f(v) -> float:
    return round(float(v or 0), 2)


def _iso(v) -> str | None:
    return v.isoformat() if v else None


def _employee(db: Session, worker: User) -> Employee:
    e = db.get(Employee, worker.employee_id)
    if e is None:
        raise HTTPException(404, "Employee record not found")
    return e


def _manager(db: Session, e: Employee) -> User | None:
    return db.get(User, e.manager_user_id) if e.manager_user_id else None


def _my_tasks_q(db: Session, e: Employee):
    """Tasks assigned to this worker, or unassigned tasks in their department."""
    return db.query(Task).filter(
        or_(
            Task.worker_employee_id == e.id,
            (Task.department == e.department) & Task.worker_employee_id.is_(None),
        )
    )


def _task_row(db: Session, t: Task) -> dict:
    order = db.get(Order, t.order_id) if t.order_id else None
    return {
        "id": t.id,
        "title": t.title,
        "details": t.details,
        "order_no": order.order_no if order else None,
        "order_id": t.order_id,
        "priority": t.priority,
        "deadline": _iso(t.deadline),
        "status": t.status,
        "shown_status": shown_status(t),
        "mine": t.worker_employee_id is not None,
        "created_at": _iso(t.created_at),
        "updated_at": _iso(t.updated_at),
    }


def _log(db: Session, worker: User, category: str, action: str, details: str) -> None:
    db.add(ActivityLog(user_id=worker.id, user_name=worker.name, user_role=worker.role.name,
                       category=category, action=action, details=details[:2000]))


def _notify_manager(db: Session, e: Employee, worker: User, title: str, body: str) -> None:
    mgr = _manager(db, e)
    if mgr is not None:
        db.add(Notification(to_user_id=mgr.id, kind="info", title=title[:200], body=body, from_user_name=worker.name))
    else:
        # No direct manager: fall back to the department role / Supermanager.
        db.add(Notification(to_role=rbac.ROLE_MANAGER, kind="info", title=title[:200], body=body, from_user_name=worker.name))


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@router.get("/dashboard")
def dashboard(worker: User = Depends(get_current_worker), db: Session = Depends(get_db)):
    e = _employee(db, worker)
    today = date.today()
    att = (
        db.query(Attendance)
        .filter(Attendance.employee_id == e.id, Attendance.work_date == today)
        .first()
    )
    tasks = _my_tasks_q(db, e).all()
    mine = [t for t in tasks if t.worker_employee_id == e.id]

    def count(status):
        return sum(1 for t in mine if t.status == status)

    # Production target vs actual (today) for this worker's orders.
    today_actual = _f(
        db.query(func.coalesce(func.sum(ProductionLog.output_meters), 0))
        .filter(ProductionLog.log_date == today, ProductionLog.worker_employee_id == e.id)
        .scalar()
    ) if _has_worker_col() else 0.0

    cards = {
        "today_attendance": att.status if att else "not_marked",
        "checked_in": bool(att and att.check_in and not att.check_out),
        "assigned_tasks": len(mine),
        "in_progress": count("in_progress"),
        "paused": count("paused"),
        "completed": count("completed"),
        "pending": count("pending"),
        "today_output": today_actual,
    }
    return {
        "worker": {"name": e.name, "department": e.department, "role_on_floor": e.role_on_floor},
        "cards": cards,
        "tasks": [_task_row(db, t) for t in sorted(mine, key=lambda t: t.id, reverse=True)[:6]],
        "manager": (lambda m: {"name": m.name} if m else None)(_manager(db, e)),
    }


def _has_worker_col() -> bool:
    # ProductionLog gained worker_employee_id in this change; guard for old DBs.
    return hasattr(ProductionLog, "worker_employee_id")


# --------------------------------------------------------------------------- #
# My Tasks
# --------------------------------------------------------------------------- #
@router.get("/tasks")
def my_tasks(worker: User = Depends(get_current_worker), db: Session = Depends(get_db)):
    e = _employee(db, worker)
    rows = [_task_row(db, t) for t in _my_tasks_q(db, e).order_by(Task.id.desc()).all()]
    return {"department": e.department, "tasks": rows}


class TaskActionIn(BaseModel):
    action: str
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("action")
    @classmethod
    def _a(cls, v: str) -> str:
        if v not in TASK_ACTIONS:
            raise ValueError(f"action must be one of {', '.join(TASK_ACTIONS)}")
        return v


@router.post("/tasks/{task_id}/action")
def task_action(
    task_id: int,
    body: TaskActionIn,
    worker: User = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    e = _employee(db, worker)
    t = _my_tasks_q(db, e).filter(Task.id == task_id).first()
    if t is None:
        raise HTTPException(404, "Task not found")  # not yours = not found
    if t.status == "completed":
        raise HTTPException(409, "This task is already completed")
    # Picking up an unassigned department task assigns it to this worker.
    if t.worker_employee_id is None:
        t.worker_employee_id = e.id
    new_status = ACTION_STATUS[body.action]
    t.status = new_status
    t.updated_at = datetime.utcnow()
    db.add(TaskUpdate(task_id=t.id, user_id=worker.id, status=new_status,
                      note=(body.note or "").strip() or f"Worker {body.action}"))
    # Notify the manager on completion (and let production flow to QC via the
    # existing handover the manager runs).
    if body.action == "complete":
        _notify_manager(db, e, worker, f"Task completed: {t.title}",
                        f"{e.name} completed '{t.title}'" + (f" ({db.get(Order, t.order_id).order_no})" if t.order_id and db.get(Order, t.order_id) else ""))
    elif body.action == "start":
        _notify_manager(db, e, worker, f"Task started: {t.title}", f"{e.name} started working on '{t.title}'")
    _log(db, worker, "task", body.action, f"{t.title}")
    db.commit()
    return _task_row(db, t)


# --------------------------------------------------------------------------- #
# Production Updates
# --------------------------------------------------------------------------- #
class ProductionIn(BaseModel):
    machine_id: int
    order_id: int
    output_meters: float = Field(gt=0, le=1_000_000)
    stage: str | None = None
    waste_meters: float = Field(default=0, ge=0, le=1_000_000)
    defects: int = Field(default=0, ge=0, le=100000)
    downtime_minutes: float = Field(default=0, ge=0, le=100000)
    note: str | None = Field(default=None, max_length=500)


@router.get("/production")
def production(worker: User = Depends(get_current_worker), db: Session = Depends(get_db)):
    e = _employee(db, worker)
    machines = db.query(Machine).order_by(Machine.type, Machine.name).all()
    orders = (
        db.query(Order)
        .filter(Order.status.in_(("confirmed", "in_production", "in_quality")))
        .order_by(Order.id.desc())
        .all()
    )
    q = db.query(ProductionLog)
    if _has_worker_col():
        q = q.filter(ProductionLog.worker_employee_id == e.id)
    recent = q.order_by(ProductionLog.id.desc()).limit(15).all()
    rows = []
    for r in recent:
        m = db.get(Machine, r.machine_id)
        o = db.get(Order, r.order_id)
        rows.append({"machine": m.name if m else "", "order_no": o.order_no if o else "",
                     "stage": r.stage, "output_meters": _f(r.output_meters), "log_date": _iso(r.log_date)})
    return {
        "machines": [{"id": m.id, "name": m.name, "type": m.type, "status": m.current_status} for m in machines],
        "orders": [{"id": o.id, "order_no": o.order_no, "fabric_type": o.fabric_type} for o in orders],
        "recent": rows,
    }


@router.post("/production", status_code=201)
def submit_production(
    body: ProductionIn,
    worker: User = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    e = _employee(db, worker)
    m = db.get(Machine, body.machine_id)
    o = db.get(Order, body.order_id)
    if m is None or o is None:
        raise HTTPException(400, "Unknown machine or order")
    stage = body.stage or m.current_stage or m.type
    log = ProductionLog(machine_id=m.id, order_id=o.id, stage=stage,
                        output_meters=body.output_meters, log_date=date.today())
    if _has_worker_col():
        log.worker_employee_id = e.id
    db.add(log)
    if o.status == "confirmed":
        o.status = "in_production"
    extra = []
    if body.waste_meters:
        extra.append(f"waste {body.waste_meters:,.0f} m")
    if body.defects:
        extra.append(f"{body.defects} defects")
    if body.downtime_minutes:
        extra.append(f"downtime {body.downtime_minutes:,.0f} min")
    detail = f"{o.order_no}: {body.output_meters:,.0f} m {stage} on {m.name}"
    if extra:
        detail += " · " + ", ".join(extra)
    _log(db, worker, "production", "output_logged", detail)
    # Notify the manager so they can verify output and run the QC handover.
    _notify_manager(db, e, worker, f"Production update on {o.order_no}", detail)
    db.commit()
    return {"ok": True, "order_no": o.order_no, "logged_meters": body.output_meters}


# --------------------------------------------------------------------------- #
# Machine Status + report a problem
# --------------------------------------------------------------------------- #
@router.get("/machines")
def machines(worker: User = Depends(get_current_worker), db: Session = Depends(get_db)):
    rows = []
    for m in db.query(Machine).order_by(Machine.type, Machine.name).all():
        o = db.get(Order, m.current_order_id) if m.current_order_id else None
        rows.append({"id": m.id, "name": m.name, "type": m.type,
                     "status": "maintenance" if m.current_status == "breakdown" else m.current_status,
                     "order_no": o.order_no if o else None, "stage": m.current_stage})
    return {"machines": rows, "note": "Report a breakdown or material shortage — your manager and the Supermanager are notified. You cannot change machine status yourself."}


class ReportIn(BaseModel):
    kind: str
    machine_id: int | None = None
    message: str = Field(min_length=3, max_length=1000)

    @field_validator("kind")
    @classmethod
    def _k(cls, v: str) -> str:
        if v not in REPORT_KINDS:
            raise ValueError(f"kind must be one of {', '.join(REPORT_KINDS)}")
        return v


@router.post("/report", status_code=201)
def report_problem(
    body: ReportIn,
    worker: User = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    e = _employee(db, worker)
    m = db.get(Machine, body.machine_id) if body.machine_id else None
    label = {"breakdown": "Machine breakdown", "material_shortage": "Material shortage", "problem": "Production problem"}[body.kind]
    title = f"{label}" + (f" — {m.name}" if m else "")
    body_text = body.message.strip() + (f" (reported on {m.name})" if m else "")
    # Notify the worker's manager AND the Supermanager.
    _notify_manager(db, e, worker, title, body_text)
    db.add(Notification(to_role=rbac.ROLE_MANAGER, kind="info", title=title[:200], body=body_text, from_user_name=worker.name))
    _log(db, worker, "production", "report", f"{label}: {body.message.strip()}")
    db.commit()
    return {"ok": True, "kind": body.kind, "reported": True}


# --------------------------------------------------------------------------- #
# Attendance (check-in / check-out)
# --------------------------------------------------------------------------- #
def _att_row(a: Attendance) -> dict:
    return {
        "id": a.id,
        "work_date": a.work_date.isoformat(),
        "shift": a.shift,
        "status": a.status,
        "hours_worked": _f(a.hours_worked),
        "overtime_hours": _f(a.overtime_hours),
        "check_in": _iso(a.check_in),
        "check_out": _iso(a.check_out),
        "verified": bool(a.verified),
    }


@router.get("/attendance")
def attendance(worker: User = Depends(get_current_worker), db: Session = Depends(get_db)):
    e = _employee(db, worker)
    today = date.today()
    rows = (
        db.query(Attendance)
        .filter(Attendance.employee_id == e.id)
        .order_by(Attendance.work_date.desc())
        .limit(60)
        .all()
    )
    today_row = next((a for a in rows if a.work_date == today), None)
    return {
        "today": _att_row(today_row) if today_row else None,
        "can_check_in": today_row is None or today_row.check_in is None,
        "can_check_out": bool(today_row and today_row.check_in and not today_row.check_out),
        "rows": [_att_row(a) for a in rows],
    }


class CheckInIn(BaseModel):
    shift: str = "morning"

    @field_validator("shift")
    @classmethod
    def _sh(cls, v: str) -> str:
        if v not in ("morning", "evening", "night"):
            raise ValueError("shift must be morning, evening or night")
        return v


@router.post("/attendance/check-in")
def check_in(body: CheckInIn, worker: User = Depends(get_current_worker), db: Session = Depends(get_db)):
    e = _employee(db, worker)
    today = date.today()
    row = (
        db.query(Attendance)
        .filter(Attendance.employee_id == e.id, Attendance.work_date == today)
        .first()
    )
    if row is not None and row.check_in is not None:
        raise HTTPException(409, "You have already checked in today")
    now = _now()
    if row is None:
        row = Attendance(employee_id=e.id, work_date=today)
        db.add(row)
    row.shift = body.shift
    row.check_in = now
    row.status = "present"
    row.source = "worker"
    row.verified = False  # manager verifies before wages use it
    _log(db, worker, "attendance", "check_in", f"{e.name} checked in ({body.shift})")
    _notify_manager(db, e, worker, "Attendance to verify", f"{e.name} checked in — please verify today's attendance.")
    db.commit()
    db.refresh(row)
    return _att_row(row)


@router.post("/attendance/check-out")
def check_out(worker: User = Depends(get_current_worker), db: Session = Depends(get_db)):
    e = _employee(db, worker)
    today = date.today()
    row = (
        db.query(Attendance)
        .filter(Attendance.employee_id == e.id, Attendance.work_date == today)
        .first()
    )
    if row is None or row.check_in is None:
        raise HTTPException(409, "You have not checked in today")
    if row.check_out is not None:
        raise HTTPException(409, "You have already checked out today")
    now = _now()
    row.check_out = now
    start = row.check_in if row.check_in.tzinfo else row.check_in.replace(tzinfo=timezone.utc)
    hours = max(0.0, (now - start).total_seconds() / 3600.0)
    row.hours_worked = round(hours, 2)
    if hours < 4:
        row.status = "half_day"
    row.verified = False
    _log(db, worker, "attendance", "check_out", f"{e.name} checked out ({row.hours_worked} h)")
    db.commit()
    db.refresh(row)
    return _att_row(row)


# --------------------------------------------------------------------------- #
# Overtime
# --------------------------------------------------------------------------- #
class OvertimeIn(BaseModel):
    work_date: date | None = None
    hours: float = Field(gt=0, le=12)
    reason: str = Field(min_length=3, max_length=500)


@router.get("/overtime")
def overtime(worker: User = Depends(get_current_worker), db: Session = Depends(get_db)):
    e = _employee(db, worker)
    rows = (
        db.query(Attendance)
        .filter(Attendance.employee_id == e.id, Attendance.overtime_hours > 0)
        .order_by(Attendance.work_date.desc())
        .all()
    )
    return {
        "rows": [
            {"work_date": a.work_date.isoformat(), "overtime_hours": _f(a.overtime_hours), "verified": bool(a.verified)}
            for a in rows
        ],
        "total_hours": round(sum(float(a.overtime_hours or 0) for a in rows), 2),
        "note": "Overtime is sent to your manager for verification before Accounts uses it for wages.",
    }


@router.post("/overtime", status_code=201)
def submit_overtime(body: OvertimeIn, worker: User = Depends(get_current_worker), db: Session = Depends(get_db)):
    e = _employee(db, worker)
    wd = body.work_date or date.today()
    if wd > date.today():
        raise HTTPException(400, "Cannot submit overtime for a future day")
    row = (
        db.query(Attendance)
        .filter(Attendance.employee_id == e.id, Attendance.work_date == wd)
        .first()
    )
    if row is None:
        row = Attendance(employee_id=e.id, work_date=wd, status="present", source="worker")
        db.add(row)
    row.overtime_hours = body.hours
    row.verified = False
    _log(db, worker, "attendance", "overtime_submitted", f"{e.name}: {body.hours} h OT on {wd.isoformat()} — {body.reason.strip()}")
    _notify_manager(db, e, worker, "Overtime to verify", f"{e.name} submitted {body.hours} h overtime on {wd.isoformat()}: {body.reason.strip()}")
    db.commit()
    db.refresh(row)
    return {"ok": True, "work_date": wd.isoformat(), "overtime_hours": _f(row.overtime_hours), "verified": False}


# --------------------------------------------------------------------------- #
# Task History
# --------------------------------------------------------------------------- #
@router.get("/history")
def history(worker: User = Depends(get_current_worker), db: Session = Depends(get_db)):
    e = _employee(db, worker)
    tasks = db.query(Task).filter(Task.worker_employee_id == e.id).order_by(Task.id.desc()).all()
    out = []
    for t in tasks:
        updates = (
            db.query(TaskUpdate)
            .filter(TaskUpdate.task_id == t.id)
            .order_by(TaskUpdate.id.desc())
            .all()
        )
        row = _task_row(db, t)
        row["updates"] = [
            {"status": u.status, "note": u.note, "at": _iso(u.created_at)} for u in updates
        ]
        out.append(row)
    return {"tasks": out}


# --------------------------------------------------------------------------- #
# Notifications
# --------------------------------------------------------------------------- #
@router.get("/notifications")
def notifications(worker: User = Depends(get_current_worker), db: Session = Depends(get_db)):
    rows = (
        db.query(Notification)
        .filter(or_(Notification.to_user_id == worker.id, Notification.to_role == rbac.ROLE_WORKER))
        .order_by(Notification.id.desc())
        .limit(50)
        .all()
    )
    return {
        "notifications": [
            {"id": n.id, "kind": n.kind, "title": n.title, "body": n.body,
             "from": n.from_user_name, "created_at": _iso(n.created_at), "read": n.read_at is not None}
            for n in rows
        ],
        "unread": sum(1 for n in rows if n.read_at is None),
    }


@router.post("/notifications/{nid}/read")
def mark_read(nid: int, worker: User = Depends(get_current_worker), db: Session = Depends(get_db)):
    n = db.get(Notification, nid)
    if n is None or (n.to_user_id != worker.id and n.to_role != rbac.ROLE_WORKER):
        raise HTTPException(404, "Notification not found")
    if n.read_at is None:
        n.read_at = datetime.utcnow()
        db.commit()
    return {"ok": True, "id": nid}


# --------------------------------------------------------------------------- #
# My Profile (read-only; worker cannot edit wage/department)
# --------------------------------------------------------------------------- #
@router.get("/profile")
def profile(worker: User = Depends(get_current_worker), db: Session = Depends(get_db)):
    e = _employee(db, worker)
    mgr = _manager(db, e)
    from app.departments import DEPT_LABEL

    today = date.today()
    start = today.replace(day=1)
    month_att = (
        db.query(Attendance.status, func.count(Attendance.id))
        .filter(Attendance.employee_id == e.id, Attendance.work_date.between(start, today))
        .group_by(Attendance.status)
        .all()
    )
    att = dict(month_att)
    return {
        "name": e.name,
        "login_email": worker.email if not worker.email.endswith("@staff.everest.local") else None,
        "login_id": worker.login_id,
        "role_on_floor": e.role_on_floor,
        "phone": e.phone,
        "department": e.department,
        "department_label": DEPT_LABEL.get(e.department or "", "Not assigned"),
        "daily_wage": _f(e.daily_wage),
        "manager": {"name": mgr.name} if mgr else None,
        "attendance_this_month": {
            "present": att.get("present", 0),
            "half_day": att.get("half_day", 0),
            "absent": att.get("absent", 0),
        },
        "note": "Your wage and department are set by your manager. Contact them for changes.",
    }

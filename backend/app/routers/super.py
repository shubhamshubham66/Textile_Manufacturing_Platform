"""Supermanager control panel — /api/super/*.

The Supermanager (role "manager") manages department managers, workers and
instructions, and monitors production, inventory, quality, dispatch,
attendance and accounts. Payments themselves stay with the accountant; here
they are read-only. Every endpoint is guarded on the backend by the RBAC
resource of the page that uses it.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import rbac
from app.database import get_db
from app.departments import DEPARTMENTS, DEPT_LABEL, DEPT_MANAGER_ROLES, DEPT_ROLE, dept_of
from app.deps import get_current_user, require_any_resource, require_resource
from app.models import (
    ActivityLog,
    Attendance,
    Dispatch,
    DispatchItem,
    Employee,
    Invoice,
    Machine,
    MachineStatusLog,
    Order,
    Payment,
    ProductionLog,
    PurchaseOrder,
    QualityInspection,
    Role,
    Roll,
    Supplier,
    Task,
    TaskUpdate,
    User,
    YarnReceipt,
    YarnStock,
)
from app.security import hash_password
from app.services import super_data as sd
from app.services.reports import cost_per_order, profit_or_loss, wages_report
from app.services.tasks import shown_status
from app.settings_store import ALERT_KINDS, get_setting, set_setting

router = APIRouter(prefix="/api/super", tags=["supermanager"])

DEPT_KEYS = tuple(k for k, _ in DEPARTMENTS)
PRIORITIES = ("low", "medium", "high", "urgent")
TASK_STATUSES = ("pending", "in_progress", "completed")


def _dept(v: str | None) -> str | None:
    if v is None:
        return v
    if v not in DEPT_KEYS:
        raise ValueError(f"department must be one of {', '.join(DEPT_KEYS)}")
    return v


def _password_ok(pw: str) -> str:
    if len(pw) < 8 or not any(c.isalpha() for c in pw) or not any(c.isdigit() for c in pw):
        raise ValueError("password needs at least 8 characters with letters and numbers")
    return pw


def _log(db: Session, user: User, category: str, action: str, details: str) -> None:
    db.add(ActivityLog(user_id=user.id, user_name=user.name, user_role=user.role.name,
                       category=category, action=action, details=details[:2000]))


def _window(start: date | None, end: date | None) -> tuple[date, date]:
    if start and end:
        if end < start:
            raise HTTPException(400, "end must be on or after start")
        return start, end
    return sd.month_window()


# --------------------------------------------------------------------------- #
# Dashboard + search
# --------------------------------------------------------------------------- #
@router.get("/overview")
def overview(_=Depends(require_resource("super_dashboard")), db: Session = Depends(get_db)):
    return sd.overview(db)


@router.get("/search")
def search(
    q: str = Query(..., min_length=1, max_length=60),
    _=Depends(require_resource("super_dashboard")),
    db: Session = Depends(get_db),
):
    like = f"%{q.strip()}%"
    orders = (db.query(Order).filter(or_(Order.order_no.ilike(like), Order.fabric_type.ilike(like),
                                         Order.colour.ilike(like))).order_by(Order.id.desc()).limit(6).all())
    workers = db.query(Employee).filter(Employee.name.ilike(like)).limit(6).all()
    managers = [u for u in sd.dept_managers(db) if q.strip().lower() in (u.name or "").lower()][:6]
    rolls = db.query(Roll).filter(Roll.roll_no.ilike(like)).limit(6).all()
    return {
        "orders": [{"id": o.id, "label": o.order_no, "sub": f"{o.buyer.name if o.buyer else ''} · {o.status.replace('_', ' ')}", "page": "/app/order-desk"} for o in orders],
        "workers": [{"id": w.id, "label": w.name, "sub": DEPT_LABEL.get(w.department or "", w.role_on_floor or ""), "page": "/app/super-workers"} for w in workers],
        "managers": [{"id": u.id, "label": u.name, "sub": DEPT_LABEL.get(dept_of(u), ""), "page": "/app/super-managers"} for u in managers],
        "rolls": [{"id": r.id, "label": r.roll_no, "sub": r.status, "page": "/app/super-inventory"} for r in rolls],
    }


# --------------------------------------------------------------------------- #
# Department managers
# --------------------------------------------------------------------------- #
def _manager_out(db: Session, u: User, perf: dict) -> dict:
    d = dept_of(u)
    tasks = db.query(Task).filter(Task.manager_user_id == u.id).all()
    return {
        "id": u.id, "name": u.name, "login_id": u.login_id,
        "email": None if (u.email or "").endswith("@staff.everest.local") else u.email,
        "department": d, "department_label": DEPT_LABEL.get(d, ""),
        "role": u.role.name, "is_active": bool(u.is_active),
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "tasks_open": sum(1 for t in tasks if t.status != "completed"),
        "tasks_overdue": sum(1 for t in tasks if shown_status(t) == "delayed"),
        "tasks_done": sum(1 for t in tasks if t.status == "completed"),
        "department_metrics": perf.get(d, {}).get("metrics", []),
    }


@router.get("/managers")
def list_managers(_=Depends(require_resource("super_managers")), db: Session = Depends(get_db)):
    start, end = sd.month_window()
    perf = {p["department"]: p for p in sd.department_performance(db, start, end)}
    return {
        "managers": [_manager_out(db, u, perf) for u in sd.dept_managers(db)],
        "departments": [{"key": k, "label": v} for k, v in DEPARTMENTS],
    }


class ManagerIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=180)
    department: str
    password: str
    confirm_password: str

    _d = field_validator("department")(classmethod(lambda cls, v: _dept(v)))
    _p = field_validator("password")(classmethod(lambda cls, v: _password_ok(v)))

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("enter a valid email")
        return v


class ManagerEdit(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=180)
    department: str

    _d = field_validator("department")(classmethod(lambda cls, v: _dept(v)))

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("enter a valid email")
        return v


class ActiveIn(BaseModel):
    active: bool


class PasswordIn(BaseModel):
    password: str
    confirm_password: str

    _p = field_validator("password")(classmethod(lambda cls, v: _password_ok(v)))


def _get_dept_manager(db: Session, user_id: int) -> User:
    u = db.get(User, user_id)
    if u is None or u.role.name not in DEPT_MANAGER_ROLES:
        raise HTTPException(404, "Department manager not found")
    return u


def _role(db: Session, name: str) -> Role:
    r = db.query(Role).filter(Role.name == name).first()
    if r is None:
        raise HTTPException(503, f"Role {name} is not set up yet; restart the server")
    return r


@router.post("/managers", status_code=201)
def create_manager(body: ManagerIn, me: User = Depends(get_current_user),
                   _=Depends(require_resource("super_managers")), db: Session = Depends(get_db)):
    if body.password != body.confirm_password:
        raise HTTPException(400, "Passwords do not match")
    if db.query(User).filter(func.lower(User.email) == body.email).first():
        raise HTTPException(409, "That email already has an account")
    u = User(name=body.name.strip(), email=body.email, password_hash=hash_password(body.password),
             role=_role(db, DEPT_ROLE[body.department]), department=body.department, is_active=True)
    db.add(u)
    db.commit()
    start, end = sd.month_window()
    perf = {p["department"]: p for p in sd.department_performance(db, start, end)}
    return _manager_out(db, u, perf)


@router.put("/managers/{user_id}")
def edit_manager(user_id: int, body: ManagerEdit, _=Depends(require_resource("super_managers")),
                 db: Session = Depends(get_db)):
    u = _get_dept_manager(db, user_id)
    clash = db.query(User).filter(func.lower(User.email) == body.email, User.id != u.id).first()
    if clash:
        raise HTTPException(409, "That email already has an account")
    u.name = body.name.strip()
    u.email = body.email
    u.department = body.department
    u.role = _role(db, DEPT_ROLE[body.department])
    db.commit()
    start, end = sd.month_window()
    perf = {p["department"]: p for p in sd.department_performance(db, start, end)}
    return _manager_out(db, u, perf)


@router.post("/managers/{user_id}/active")
def set_manager_active(user_id: int, body: ActiveIn, _=Depends(require_resource("super_managers")),
                       db: Session = Depends(get_db)):
    u = _get_dept_manager(db, user_id)
    u.is_active = body.active
    db.commit()
    return {"id": u.id, "is_active": u.is_active}


@router.post("/managers/{user_id}/reset-password")
def reset_manager_password(user_id: int, body: PasswordIn, _=Depends(require_resource("super_managers")),
                           db: Session = Depends(get_db)):
    if body.password != body.confirm_password:
        raise HTTPException(400, "Passwords do not match")
    u = _get_dept_manager(db, user_id)
    u.password_hash = hash_password(body.password)
    db.commit()
    return {"id": u.id, "reset": True}  # the password itself is never returned


# --------------------------------------------------------------------------- #
# Workers
# --------------------------------------------------------------------------- #
def _worker_out(db: Session, e: Employee, start: date, end: date) -> dict:
    att = (db.query(Attendance.status, func.count(Attendance.id))
           .filter(Attendance.employee_id == e.id, Attendance.work_date.between(start, end))
           .group_by(Attendance.status).all())
    a = dict(att)
    mgr = db.get(User, e.manager_user_id) if e.manager_user_id else None
    tasks = db.query(Task).filter(Task.worker_employee_id == e.id).order_by(Task.id.desc()).all()
    login = db.query(User).filter(User.employee_id == e.id).first()
    return {
        "id": e.id, "name": e.name, "role_on_floor": e.role_on_floor, "phone": e.phone,
        "daily_wage": sd._f(e.daily_wage), "department": e.department,
        "department_label": DEPT_LABEL.get(e.department or "", ""),
        "manager": sd.user_brief(mgr), "is_active": e.is_active is not False,
        "attendance": {"present": a.get("present", 0), "half_day": a.get("half_day", 0), "absent": a.get("absent", 0)},
        "tasks": [{"id": t.id, "title": t.title, "status": shown_status(t)} for t in tasks[:5]],
        "tasks_open": sum(1 for t in tasks if t.status != "completed"),
        "has_login": login is not None,
        "login_email": login.email if login else None,
    }


@router.get("/workers")
def list_workers(
    q: str | None = None, department: str | None = None, status: str | None = None,
    _=Depends(require_resource("super_workers")), db: Session = Depends(get_db),
):
    start, end = sd.month_window()
    query = db.query(Employee)
    if q:
        query = query.filter(or_(Employee.name.ilike(f"%{q}%"), Employee.role_on_floor.ilike(f"%{q}%")))
    if department == "none":
        query = query.filter(Employee.department.is_(None))
    elif department:
        query = query.filter(Employee.department == department)
    if status == "active":
        query = query.filter(Employee.is_active.isnot(False))
    elif status == "inactive":
        query = query.filter(Employee.is_active.is_(False))
    rows = query.order_by(Employee.name).all()
    return {
        "workers": [_worker_out(db, e, start, end) for e in rows],
        "departments": [{"key": k, "label": v} for k, v in DEPARTMENTS],
        "managers": [sd.user_brief(u) for u in sd.dept_managers(db) if u.is_active],
        "month": {"start": start.isoformat(), "end": end.isoformat()},
    }


class WorkerIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    role_on_floor: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=30)
    daily_wage: float = Field(ge=0, le=100000)
    department: str | None = None
    manager_user_id: int | None = None
    # Optional worker login: create a sign-in account for this worker.
    login_email: str | None = Field(default=None, max_length=180)
    login_password: str | None = None

    _d = field_validator("department")(classmethod(lambda cls, v: _dept(v or None)))

    @field_validator("login_email")
    @classmethod
    def _email(cls, v):
        v = (v or "").strip().lower()
        if not v:
            return None
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("enter a valid login email, or leave it empty")
        return v


class WorkerLoginIn(BaseModel):
    email: str = Field(min_length=5, max_length=180)
    password: str
    confirm_password: str

    _p = field_validator("password")(classmethod(lambda cls, v: _password_ok(v)))

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("enter a valid email")
        return v


def _check_manager(db: Session, manager_user_id: int | None) -> None:
    if manager_user_id is None:
        return
    u = db.get(User, manager_user_id)
    if u is None or u.role.name not in DEPT_MANAGER_ROLES:
        raise HTTPException(400, "Reporting manager must be a department manager")


def _create_worker_login(db: Session, employee: Employee, email: str, password: str) -> User:
    """Create a `worker` User linked to the Employee (one login per worker)."""
    email = email.strip().lower()
    if db.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(409, "That email already has an account")
    role = _role(db, rbac.ROLE_WORKER)
    u = User(name=employee.name, email=email, password_hash=hash_password(password),
             role=role, department=employee.department, employee_id=employee.id, is_active=True)
    db.add(u)
    return u


@router.post("/workers", status_code=201)
def create_worker(body: WorkerIn, _=Depends(require_resource("super_workers")), db: Session = Depends(get_db)):
    _check_manager(db, body.manager_user_id)
    e = Employee(name=body.name.strip(), role_on_floor=(body.role_on_floor or "").strip() or None,
                 phone=(body.phone or "").strip() or None, daily_wage=body.daily_wage,
                 department=body.department, manager_user_id=body.manager_user_id, is_active=True)
    db.add(e)
    db.flush()
    # Optionally give the worker a login in the same step.
    if body.login_email and body.login_password:
        if not _password_ok(body.login_password):
            raise HTTPException(400, "Password needs at least 8 characters with letters and numbers")
        _create_worker_login(db, e, body.login_email, body.login_password)
    db.commit()
    s, en = sd.month_window()
    return _worker_out(db, e, s, en)


@router.post("/workers/{emp_id}/login", status_code=201)
def set_worker_login(emp_id: int, body: WorkerLoginIn, _=Depends(require_resource("super_workers")),
                     db: Session = Depends(get_db)):
    """Create or reset the login for an existing worker."""
    if body.password != body.confirm_password:
        raise HTTPException(400, "Passwords do not match")
    e = db.get(Employee, emp_id)
    if e is None:
        raise HTTPException(404, "Worker not found")
    existing = db.query(User).filter(User.employee_id == e.id).first()
    if existing is not None:
        clash = db.query(User).filter(func.lower(User.email) == body.email, User.id != existing.id).first()
        if clash:
            raise HTTPException(409, "That email already has an account")
        existing.email = body.email
        existing.password_hash = hash_password(body.password)
        existing.is_active = True
        db.commit()
        return {"ok": True, "employee_id": e.id, "email": existing.email, "reset": True}
    _create_worker_login(db, e, body.email, body.password)
    db.commit()
    return {"ok": True, "employee_id": e.id, "email": body.email, "created": True}


@router.put("/workers/{emp_id}")
def edit_worker(emp_id: int, body: WorkerIn, _=Depends(require_resource("super_workers")),
                db: Session = Depends(get_db)):
    e = db.get(Employee, emp_id)
    if e is None:
        raise HTTPException(404, "Worker not found")
    _check_manager(db, body.manager_user_id)
    e.name = body.name.strip()
    e.role_on_floor = (body.role_on_floor or "").strip() or None
    e.phone = (body.phone or "").strip() or None
    e.daily_wage = body.daily_wage
    e.department = body.department
    e.manager_user_id = body.manager_user_id
    db.commit()
    s, en = sd.month_window()
    return _worker_out(db, e, s, en)


@router.post("/workers/{emp_id}/active")
def set_worker_active(emp_id: int, body: ActiveIn, _=Depends(require_resource("super_workers")),
                      db: Session = Depends(get_db)):
    e = db.get(Employee, emp_id)
    if e is None:
        raise HTTPException(404, "Worker not found")
    e.is_active = body.active
    db.commit()
    return {"id": e.id, "is_active": e.is_active}


# --------------------------------------------------------------------------- #
# Instructions (tasks)
# --------------------------------------------------------------------------- #
class TaskIn(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    details: str | None = Field(default=None, max_length=4000)
    department: str
    manager_user_id: int | None = None
    order_id: int | None = None
    priority: str = "medium"
    deadline: date | None = None

    _d = field_validator("department")(classmethod(lambda cls, v: _dept(v)))

    @field_validator("priority")
    @classmethod
    def _prio(cls, v: str) -> str:
        if v not in PRIORITIES:
            raise ValueError(f"priority must be one of {', '.join(PRIORITIES)}")
        return v


class TaskEdit(BaseModel):
    priority: str | None = None
    deadline: date | None = None
    status: str | None = None
    manager_user_id: int | None = None

    @field_validator("priority")
    @classmethod
    def _prio(cls, v):
        if v is not None and v not in PRIORITIES:
            raise ValueError(f"priority must be one of {', '.join(PRIORITIES)}")
        return v

    @field_validator("status")
    @classmethod
    def _status(cls, v):
        if v is not None and v not in TASK_STATUSES:
            raise ValueError(f"status must be one of {', '.join(TASK_STATUSES)}")
        return v


@router.get("/tasks")
def list_tasks(
    department: str | None = None, status: str | None = None, priority: str | None = None,
    _=Depends(require_resource("super_tasks")), db: Session = Depends(get_db),
):
    q = db.query(Task)
    if department:
        q = q.filter(Task.department == department)
    if priority:
        q = q.filter(Task.priority == priority)
    rows = [sd.task_row(db, t) for t in q.order_by(Task.id.desc()).all()]
    if status:
        rows = [r for r in rows if r["shown_status"] == status]
    managers = [sd.user_brief(u) for u in sd.dept_managers(db) if u.is_active]
    orders = (db.query(Order).filter(Order.status.notin_(("closed", "cancelled", "rejected")))
              .order_by(Order.id.desc()).all())
    return {
        "tasks": rows,
        "departments": [{"key": k, "label": v} for k, v in DEPARTMENTS],
        "managers": managers,
        "orders": [{"id": o.id, "order_no": o.order_no, "status": o.status} for o in orders],
    }


@router.post("/tasks", status_code=201)
def create_task(body: TaskIn, me: User = Depends(get_current_user),
                _=Depends(require_resource("super_tasks")), db: Session = Depends(get_db)):
    if body.manager_user_id is not None:
        mgr = _get_dept_manager(db, body.manager_user_id)
        if dept_of(mgr) != body.department:
            raise HTTPException(400, f"{mgr.name} does not run {DEPT_LABEL[body.department]}")
    if body.order_id is not None and db.get(Order, body.order_id) is None:
        raise HTTPException(400, "Unknown order")
    t = Task(title=body.title.strip(), details=(body.details or "").strip() or None,
             department=body.department, manager_user_id=body.manager_user_id, order_id=body.order_id,
             priority=body.priority, deadline=body.deadline, status="pending",
             created_by_user_id=me.id, auto=False)
    db.add(t)
    db.commit()
    return sd.task_row(db, t)


@router.put("/tasks/{task_id}")
def edit_task(task_id: int, body: TaskEdit, me: User = Depends(get_current_user),
              _=Depends(require_resource("super_tasks")), db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if t is None:
        raise HTTPException(404, "Task not found")
    if body.priority:
        t.priority = body.priority
    if "deadline" in body.model_fields_set:
        t.deadline = body.deadline
    if "manager_user_id" in body.model_fields_set:
        if body.manager_user_id is not None:
            mgr = _get_dept_manager(db, body.manager_user_id)
            if dept_of(mgr) != t.department:
                raise HTTPException(400, f"{mgr.name} does not run this department")
        t.manager_user_id = body.manager_user_id
    if body.status and body.status != t.status:
        t.status = body.status
        db.add(TaskUpdate(task_id=t.id, user_id=me.id, status=body.status, note="Status set by the Supermanager"))
    t.updated_at = datetime.utcnow()
    db.commit()
    return sd.task_row(db, t)


@router.get("/tasks/{task_id}/updates")
def task_updates(task_id: int, _=Depends(require_any_resource("super_tasks", "my_tasks")),
                 db: Session = Depends(get_db)):
    if db.get(Task, task_id) is None:
        raise HTTPException(404, "Task not found")
    rows = db.query(TaskUpdate).filter(TaskUpdate.task_id == task_id).order_by(TaskUpdate.id.desc()).all()
    names = {u.id: u.name for u in db.query(User).filter(User.id.in_([r.user_id for r in rows if r.user_id])).all()}
    return [{"id": r.id, "status": r.status, "note": r.note, "user": names.get(r.user_id, "—"),
             "at": r.created_at.isoformat() if r.created_at else None} for r in rows]


# --------------------------------------------------------------------------- #
# Production monitoring
# --------------------------------------------------------------------------- #
@router.get("/production")
def production(_=Depends(require_resource("super_production")), db: Session = Depends(get_db)):
    today = date.today()
    orders = (db.query(Order).filter(Order.status.in_(sd.ACTIVE_ORDER + ("dispatched",)))
              .order_by(Order.deadline.is_(None), Order.deadline, Order.id).all())
    rows = []
    for o in orders:
        r = sd.order_row(db, o)
        r["stages"] = sd.stage_metres(db, o.id)
        r["days_left"] = (o.deadline - today).days if o.deadline else None
        r["delay"] = ("late" if r["late"] else
                      "at_risk" if (o.deadline and (o.deadline - today).days <= 3 and r["progress"] < 80
                                    and o.status in ("confirmed", "in_production")) else None)
        rows.append(r)
    machines = []
    for m in db.query(Machine).order_by(Machine.type, Machine.name).all():
        made = (db.query(func.coalesce(func.sum(ProductionLog.output_meters), 0))
                .filter(ProductionLog.machine_id == m.id).scalar())
        cur = db.get(Order, m.current_order_id) if m.current_order_id else None
        last_break = (db.query(MachineStatusLog).filter(MachineStatusLog.machine_id == m.id,
                                                        MachineStatusLog.status == "breakdown")
                      .order_by(MachineStatusLog.id.desc()).first())
        machines.append({
            "id": m.id, "name": m.name, "type": m.type,
            "status": "maintenance" if m.current_status == "breakdown" else m.current_status,
            "raw_status": m.current_status,
            "since": m.status_since.isoformat() if m.status_since else None,
            "order_no": cur.order_no if cur else None, "stage": m.current_stage,
            "total_meters": sd._f(made),
            "last_breakdown_reason": last_break.reason if last_break else None,
        })
    counts = {s: sum(1 for m in machines if m["status"] == s) for s in ("running", "idle", "maintenance")}
    stage_totals = {s: sum(r["stages"][s] for r in rows) for s in sd.STAGES}
    return {"orders": rows, "machines": machines, "machine_counts": counts, "stage_totals": stage_totals,
            "delays": [r for r in rows if r["delay"]],
            "breakdowns": [m for m in machines if m["status"] == "maintenance"]}


# --------------------------------------------------------------------------- #
# Inventory monitoring
# --------------------------------------------------------------------------- #
@router.get("/inventory")
def inventory(_=Depends(require_resource("super_inventory")), db: Session = Depends(get_db)):
    stock = []
    for s in db.query(YarnStock).order_by(YarnStock.yarn_type, YarnStock.colour).all():
        q, lvl = sd._f(s.quantity_kg), sd._f(s.reorder_level_kg)
        stock.append({"id": s.id, "yarn_type": s.yarn_type, "colour": s.colour, "quantity_kg": q,
                      "reorder_level_kg": lvl, "low": q <= lvl,
                      "updated_at": s.updated_at.isoformat() if s.updated_at else None})
    rolls = []
    for r in db.query(Roll).filter(Roll.status.in_(("pass", "pending", "rework"))).order_by(Roll.id.desc()).all():
        o = db.get(Order, r.order_id)
        rolls.append({"roll_no": r.roll_no, "order_no": o.order_no if o else None,
                      "fabric": f"{o.fabric_type} {o.colour}" if o else "", "length_meters": sd._f(r.length_meters),
                      "status": r.status})
    moves = []
    for rc in db.query(YarnReceipt).order_by(YarnReceipt.received_at.desc()).limit(30).all():
        sup = db.get(Supplier, rc.supplier_id) if rc.supplier_id else None
        moves.append({"at": rc.received_at.isoformat() if rc.received_at else None, "kind": "in",
                      "what": f"{rc.yarn_type} {rc.colour}", "qty": f"+{sd._f(rc.quantity_kg):,.0f} kg",
                      "party": sup.name if sup else ""})
    for a in (db.query(ActivityLog).filter(ActivityLog.category == "stock", ActivityLog.action == "changed")
              .order_by(ActivityLog.id.desc()).limit(30).all()):
        moves.append({"at": a.at.isoformat() if a.at else None, "kind": "change", "what": a.details,
                      "qty": "", "party": a.user_name or ""})
    for d in db.query(Dispatch).order_by(Dispatch.dispatched_at.desc()).limit(30).all():
        o = db.get(Order, d.order_id)
        moves.append({"at": d.dispatched_at.isoformat() if d.dispatched_at else None, "kind": "out",
                      "what": f"{d.dispatch_no} · {o.order_no if o else ''}",
                      "qty": f"−{d.total_rolls} rolls / {sd._f(d.total_meters):,.0f} m",
                      "party": o.buyer.name if o and o.buyer else ""})
    moves.sort(key=lambda m: m["at"] or "", reverse=True)
    finished_m = sum(r["length_meters"] for r in rolls if r["status"] == "pass")
    return {
        "yarn": stock, "low_stock": [s for s in stock if s["low"]],
        "rolls": rolls, "finished_meters": round(finished_m, 2),
        "totals": {"yarn_kg": round(sum(s["quantity_kg"] for s in stock), 2), "lines": len(stock),
                   "rolls_ready": sum(1 for r in rolls if r["status"] == "pass")},
        "exceptions": sd.inventory_exceptions(db),
        "movements": moves[:40],
        "dispatch_history": [m for m in moves if m["kind"] == "out"][:20],
    }


# --------------------------------------------------------------------------- #
# Purchase request approvals (the purchase desk cannot commit without these)
# --------------------------------------------------------------------------- #
@router.get("/purchase-requests")
def purchase_requests(_=Depends(require_resource("super_inventory")), db: Session = Depends(get_db)):
    from app.models import PurchaseRequest
    from app.routers.purchase import low_stock_rows, pr_out, requirements

    pending = db.query(PurchaseRequest).filter(PurchaseRequest.status == "pending").order_by(PurchaseRequest.id).all()
    recent = (db.query(PurchaseRequest).filter(PurchaseRequest.status != "pending")
              .order_by(PurchaseRequest.id.desc()).limit(15).all())
    short = [r for r in requirements(db) if r["confirmed"] and r["short_kg"] > 0]
    return {"pending": [pr_out(db, r) for r in pending], "recent": [pr_out(db, r) for r in recent],
            "short_orders": short, "low_stock": low_stock_rows(db)}


class DecisionIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)


def _decide(db: Session, me: User, rid: int, approve: bool, note: str | None):
    from app.models import Notification, PurchaseRequest
    from app.routers.purchase import pr_out

    r = db.get(PurchaseRequest, rid)
    if r is None:
        raise HTTPException(404, "Purchase request not found")
    if r.status != "pending":
        raise HTTPException(409, f"{r.pr_no} is already {r.status}")
    if not approve and len((note or "").strip()) < 3:
        raise HTTPException(400, "Give a reason for rejecting (at least 3 characters)")
    r.status = "approved" if approve else "rejected"
    r.decided_by_user_id, r.decided_at = me.id, datetime.utcnow()
    r.decision_note = (note or "").strip() or None
    what = f"{float(r.quantity_kg):,.0f} kg {r.yarn_type} {r.colour}"
    db.add(Notification(to_user_id=r.requested_by_user_id, kind="approval" if approve else "rejection",
                        title=f"{r.pr_no} {'approved' if approve else 'rejected'}",
                        body=what + (f" · {r.decision_note}" if r.decision_note else ""), from_user_name=me.name))
    db.commit()
    return pr_out(db, r)


@router.post("/purchase-requests/{rid}/approve")
def approve_purchase_request(rid: int, body: DecisionIn, me: User = Depends(get_current_user),
                             _=Depends(require_resource("super_inventory")), db: Session = Depends(get_db)):
    return _decide(db, me, rid, True, body.note)


@router.post("/purchase-requests/{rid}/reject")
def reject_purchase_request(rid: int, body: DecisionIn, me: User = Depends(get_current_user),
                            _=Depends(require_resource("super_inventory")), db: Session = Depends(get_db)):
    return _decide(db, me, rid, False, body.note)


# --------------------------------------------------------------------------- #
# Quality
# --------------------------------------------------------------------------- #
@router.get("/quality")
def quality(_=Depends(require_resource("super_quality")), db: Session = Depends(get_db)):
    pending = []
    for r in db.query(Roll).filter(Roll.status == "pending").order_by(Roll.id).all():
        o = db.get(Order, r.order_id)
        mch = db.get(Machine, r.machine_id)
        pending.append({"roll_no": r.roll_no, "order_no": o.order_no if o else None,
                        "length_meters": sd._f(r.length_meters), "machine": mch.name if mch else "",
                        "made_at": r.created_at.isoformat() if r.created_at else None})
    res = {"pass": [0, 0.0], "rework": [0, 0.0], "reject": [0, 0.0]}
    defects: dict[str, int] = {}
    by_order: dict[int, dict] = {}
    for insp in db.query(QualityInspection).all():
        r = db.get(Roll, insp.roll_id)
        if r is None:
            continue
        if insp.result in res:
            res[insp.result][0] += 1
            res[insp.result][1] += float(r.length_meters or 0)
        if insp.defect_type and insp.defect_type != "none":
            defects[insp.defect_type] = defects.get(insp.defect_type, 0) + 1
        b = by_order.setdefault(r.order_id, {"pass": 0, "rework": 0, "reject": 0})
        if insp.result in b:
            b[insp.result] += 1
    orders = []
    for oid, b in by_order.items():
        o = db.get(Order, oid)
        if o is None:
            continue
        waiting = db.query(Roll).filter(Roll.order_id == oid, Roll.status == "pending").count()
        state = "issues" if (b["reject"] or b["rework"]) else ("waiting" if waiting else "ok")
        orders.append({"order_no": o.order_no, "status": o.status, **b, "waiting": waiting, "quality": state})
    orders.sort(key=lambda x: x["order_no"])
    exceptions = []
    for r in db.query(Roll).filter(Roll.status.in_(("rework", "reject"))).all():
        o = db.get(Order, r.order_id)
        insp = db.query(QualityInspection).filter(QualityInspection.roll_id == r.id).first()
        exceptions.append({"roll_no": r.roll_no, "order_no": o.order_no if o else None, "result": r.status,
                           "defect": insp.defect_type if insp else None, "notes": insp.notes if insp else None})
    for e in sd.inventory_exceptions(db):
        if e["kind"] == "unapproved_dispatched":
            exceptions.append({"roll_no": None, "order_no": None, "result": "dispatched", "defect": None, "notes": e["detail"]})
    eligible = db.query(Roll).filter(Roll.status == "pass").count()
    return {
        "pending": pending,
        "results": {k: {"rolls": v[0], "meters": round(v[1], 2)} for k, v in res.items()},
        "defects": sorted(({"defect": k, "count": v} for k, v in defects.items()), key=lambda x: -x["count"]),
        "orders": orders, "exceptions": exceptions,
        "dispatch_eligible": eligible,
        "rule": "Only rolls with a QC result of pass can be dispatched (enforced by the dispatch screen).",
    }


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #
@router.get("/dispatch")
def dispatch(_=Depends(require_resource("super_dispatch")), db: Session = Depends(get_db)):
    ready = []
    for o in db.query(Order).filter(Order.status == "ready_to_ship").order_by(Order.deadline).all():
        passed = db.query(Roll).filter(Roll.order_id == o.id, Roll.status == "pass").all()
        ready.append({**sd.order_row(db, o), "rolls_ready": len(passed),
                      "meters_ready": round(sum(float(r.length_meters or 0) for r in passed), 2)})
    rows = []
    for d in db.query(Dispatch).order_by(Dispatch.dispatched_at.desc()).all():
        o = db.get(Order, d.order_id)
        items = db.query(DispatchItem).filter(DispatchItem.dispatch_id == d.id).all()
        roll_nos = []
        for i in items:
            r = db.get(Roll, i.roll_id)
            roll_nos.append(r.roll_no if r else str(i.roll_id))
        inv = db.query(Invoice).filter(Invoice.dispatch_id == d.id).first()
        rows.append({"dispatch_no": d.dispatch_no, "order_no": o.order_no if o else None,
                     "buyer": o.buyer.name if o and o.buyer else "", "status": d.status,
                     "total_rolls": d.total_rolls, "total_meters": sd._f(d.total_meters),
                     "ordered_meters": sd._f(o.quantity_meters) if o else None,
                     "rolls": roll_nos, "invoice_no": inv.invoice_no if inv else None,
                     "at": d.dispatched_at.isoformat() if d.dispatched_at else None})
    stages = {s: sum(1 for r in rows if r["status"] == s) for s in ("packed", "loaded", "shipped")}
    return {"ready": ready, "dispatches": rows, "progress": stages, "exceptions": sd.dispatch_exceptions(db)}


# --------------------------------------------------------------------------- #
# Attendance
# --------------------------------------------------------------------------- #
ATT_STATUSES = ("present", "absent", "half_day")


@router.get("/attendance")
def attendance(day: date | None = None, _=Depends(require_resource("super_attendance")),
               db: Session = Depends(get_db)):
    day = day or date.today()
    workers = db.query(Employee).filter(Employee.is_active.isnot(False)).order_by(Employee.name).all()
    recs = {a.employee_id: a for a in db.query(Attendance).filter(Attendance.work_date == day).all()}
    rows, by_dept = [], {}
    for e in workers:
        a = recs.get(e.id)
        st = a.status if a else "not_marked"
        rows.append({"employee_id": e.id, "name": e.name, "department": e.department,
                     "department_label": DEPT_LABEL.get(e.department or "", "Not assigned"),
                     "status": st, "shift": a.shift if a else None,
                     "hours": sd._f(a.hours_worked) if a else None, "attendance_id": a.id if a else None})
        d = by_dept.setdefault(e.department or "none", {"present": 0, "half_day": 0, "absent": 0, "not_marked": 0})
        d[st] = d.get(st, 0) + 1
    corrections = (db.query(ActivityLog).filter(ActivityLog.category == "attendance",
                                                ActivityLog.action.in_(("corrected", "exception_recorded")))
                   .order_by(ActivityLog.id.desc()).limit(20).all())
    totals = {s: sum(1 for r in rows if r["status"] == s) for s in ATT_STATUSES + ("not_marked",)}
    last = db.query(func.max(Attendance.work_date)).scalar()
    return {
        "day": day.isoformat(), "rows": rows, "totals": totals,
        "by_department": [{"department": k, "label": DEPT_LABEL.get(k, "Not assigned"), **v} for k, v in by_dept.items()],
        "exceptions": [r for r in rows if r["status"] in ("absent", "not_marked")],
        "corrections": [sd.activity_row(a) for a in corrections],
        "last_marked_day": last.isoformat() if last else None,
        "not_tracked": "Late arrival, leave and check-out times are not recorded by the attendance screen, so they are not shown.",
    }


class AttendanceFix(BaseModel):
    employee_id: int
    work_date: date
    status: str
    reason: str = Field(min_length=3, max_length=300)

    @field_validator("status")
    @classmethod
    def _st(cls, v):
        if v not in ATT_STATUSES:
            raise ValueError(f"status must be one of {', '.join(ATT_STATUSES)}")
        return v

    @field_validator("work_date")
    @classmethod
    def _past(cls, v):
        if v > date.today():
            raise ValueError("cannot record attendance for a future day")
        return v


@router.post("/attendance/exception")
def record_attendance_exception(body: AttendanceFix, me: User = Depends(get_current_user),
                                _=Depends(require_resource("super_attendance")), db: Session = Depends(get_db)):
    """Record an authorised attendance exception (correction) with a reason."""
    e = db.get(Employee, body.employee_id)
    if e is None:
        raise HTTPException(404, "Worker not found")
    a = (db.query(Attendance).filter(Attendance.employee_id == e.id, Attendance.work_date == body.work_date).first())
    before = a.status if a else "not marked"
    if a is None:
        a = Attendance(employee_id=e.id, work_date=body.work_date, status=body.status,
                       hours_worked=8 if body.status == "present" else 4 if body.status == "half_day" else 0)
        db.add(a)
    else:
        a.status = body.status
        a.hours_worked = 8 if body.status == "present" else 4 if body.status == "half_day" else 0
    _log(db, me, "attendance", "exception_recorded",
         f"{e.name} · {body.work_date.isoformat()}: {before} → {body.status} · reason: {body.reason.strip()}")
    db.commit()
    return {"employee_id": e.id, "work_date": body.work_date.isoformat(), "status": a.status}


def _buyer_name(db: Session, buyer_id: int | None) -> str:
    from app.models import Buyer

    b = db.get(Buyer, buyer_id) if buyer_id else None
    return b.name if b else ""


# --------------------------------------------------------------------------- #
# Accounts & reports (read-only; payments stay with the accountant)
# --------------------------------------------------------------------------- #
@router.get("/accounts")
def accounts(start: date | None = None, end: date | None = None,
             _=Depends(require_resource("super_accounts")), db: Session = Depends(get_db)):
    s, e = _window(start, end)
    s_dt, e_dt = datetime.combine(s, datetime.min.time()), datetime.combine(e, datetime.max.time())
    invs = db.query(Invoice).filter(Invoice.created_at.between(s_dt, e_dt)).all()
    inv_paid = {}
    for i in invs:
        inv_paid[i.id] = float(db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
            Payment.invoice_id == i.id, Payment.direction == "incoming", Payment.voided_at.is_(None)).scalar() or 0)
    pays = db.query(Payment).filter(Payment.voided_at.is_(None), Payment.paid_at.between(s_dt, e_dt)).all()
    pos = db.query(PurchaseOrder).filter(PurchaseOrder.created_at.between(s_dt, e_dt),
                                         PurchaseOrder.status != "cancelled").all()
    wages = wages_report(db, s, e)
    costs = cost_per_order(db, s, e)
    pl = profit_or_loss(db, s, e)
    # Date-wise: production metres and money in/out per day.
    daily: dict[str, dict] = {}
    for d in range((e - s).days + 1):
        day = s + timedelta(days=d)
        daily[day.isoformat()] = {"day": day.isoformat(), "meters": 0.0, "money_in": 0.0, "money_out": 0.0}
    for pl_row in (db.query(ProductionLog.log_date, func.sum(ProductionLog.output_meters))
                   .filter(ProductionLog.log_date.between(s, e)).group_by(ProductionLog.log_date).all()):
        daily[pl_row[0].isoformat()]["meters"] = sd._f(pl_row[1])
    for p in pays:
        k = sd._d(p.paid_at).isoformat()
        if k in daily:
            daily[k]["money_in" if p.direction == "incoming" else "money_out"] += float(p.amount)
    daily_rows = [r for r in daily.values() if r["meters"] or r["money_in"] or r["money_out"]]
    return {
        "start": s.isoformat(), "end": e.isoformat(),
        "sales": {"invoices": len(invs), "invoiced": round(sum(float(i.total or 0) for i in invs), 2),
                  "received": round(sum(inv_paid.values()), 2),
                  "outstanding": round(sum(max(0.0, float(i.total or 0) - inv_paid[i.id]) for i in invs), 2),
                  "rows": [{"invoice_no": i.invoice_no, "buyer": _buyer_name(db, i.buyer_id),
                            "total": sd._f(i.total), "status": i.status, "date": sd._d(i.created_at).isoformat() if i.created_at else None}
                           for i in invs]},
        "buyer_payments": round(sum(float(p.amount) for p in pays if p.direction == "incoming"), 2),
        "supplier_bills": {"raised": round(sum(float(p.quantity_kg or 0) * float(p.unit_cost or 0) for p in pos), 2),
                           "count": len(pos),
                           "paid": round(sum(float(p.amount) for p in pays if p.direction == "outgoing"), 2)},
        "wages": {"total": wages["total_wages"], "paid": wages["total_paid"], "due": wages["total_unpaid"]},
        "production_cost": {"total": round(sum(r["total_cost"] for r in costs), 2), "orders": len(costs),
                            "has_estimates": any(r.get("yarn_basis") == "estimate" for r in costs)},
        "profit": pl,
        "departments": sd.department_performance(db, s, e),
        "daily": daily_rows,
        "note": "Payments are recorded and changed only by the accountant; this page is read-only.",
    }


# --------------------------------------------------------------------------- #
# Alerts + activity
# --------------------------------------------------------------------------- #
@router.get("/alerts")
def list_alerts(_=Depends(require_resource("super_alerts")), db: Session = Depends(get_db)):
    al = sd.alerts(db)
    return {"alerts": al, "kinds": [{"key": k, "label": v, "count": sum(1 for a in al if a["kind"] == k)}
                                    for k, v in ALERT_KINDS]}


@router.get("/activity")
def activity(category: str | None = None, q: str | None = None,
             limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
             _=Depends(require_resource("super_activity")), db: Session = Depends(get_db)):
    qry = db.query(ActivityLog)
    if category:
        qry = qry.filter(ActivityLog.category == category)
    if q:
        like = f"%{q}%"
        qry = qry.filter(or_(ActivityLog.details.ilike(like), ActivityLog.user_name.ilike(like)))
    total = qry.count()
    rows = qry.order_by(ActivityLog.id.desc()).offset(offset).limit(limit).all()
    cats = [c for (c,) in db.query(ActivityLog.category).distinct().all()]
    return {"rows": [sd.activity_row(a) for a in rows], "total": total, "categories": sorted(cats)}


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
@router.get("/settings")
def get_settings_(_=Depends(require_resource("super_settings")), db: Session = Depends(get_db)):
    mgrs = sd.dept_managers(db)
    depts = [{"key": k, "label": v, "role": DEPT_ROLE[k],
              "managers": [u.name for u in mgrs if dept_of(u) == k and u.is_active]} for k, v in DEPARTMENTS]
    perms = [{"role": r, "pages": [i["label"] for i in items]} for r, items in rbac.MENU_CONFIG.items()]
    return {
        "capacity_m_per_machine_day": get_setting(db, "capacity_m_per_machine_day"),
        "purchase_auto_approve_kg": get_setting(db, "purchase_auto_approve_kg"),
        "alerts": get_setting(db, "alerts"),
        "alert_kinds": [{"key": k, "label": v} for k, v in ALERT_KINDS],
        "departments": depts,
        "permissions": perms,
    }


class SettingsIn(BaseModel):
    capacity_m_per_machine_day: float | None = Field(default=None, gt=0, le=100000)
    purchase_auto_approve_kg: float | None = Field(default=None, ge=0, le=1_000_000)
    alerts: dict[str, bool] | None = None


@router.put("/settings")
def put_settings(body: SettingsIn, me: User = Depends(get_current_user),
                 _=Depends(require_resource("super_settings")), db: Session = Depends(get_db)):
    changed = []
    if body.capacity_m_per_machine_day is not None:
        set_setting(db, "capacity_m_per_machine_day", body.capacity_m_per_machine_day)
        changed.append(f"capacity {body.capacity_m_per_machine_day:,.0f} m/loom/day")
    if body.purchase_auto_approve_kg is not None:
        set_setting(db, "purchase_auto_approve_kg", body.purchase_auto_approve_kg)
        changed.append("purchase auto-approve " + (f"up to {body.purchase_auto_approve_kg:,.0f} kg"
                                                    if body.purchase_auto_approve_kg else "off"))
    if body.alerts is not None:
        valid = {k for k, _ in ALERT_KINDS}
        cur = get_setting(db, "alerts")
        cur.update({k: bool(v) for k, v in body.alerts.items() if k in valid})
        set_setting(db, "alerts", cur)
        off = [k for k, v in cur.items() if not v]
        changed.append("alerts off: " + (", ".join(off) if off else "none"))
    if changed:
        _log(db, me, "settings", "updated", "; ".join(changed))
    db.commit()
    return get_settings_(None, db)


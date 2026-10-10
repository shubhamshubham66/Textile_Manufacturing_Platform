"""Production Manager control panel — /api/prod/*.

The Production Manager (role "production_manager") runs the production floor:

  Dashboard          GET  /api/prod/dashboard
  Production Orders  GET  /api/prod/orders            confirmed work from the Supermanager
  Production Planning POST /api/prod/plan              assign machine + stage + target to an order
  Production Stages  GET  /api/prod/stages            spinning / weaving / dyeing progress
  Machine Management GET  /api/prod/machines
                     POST /api/prod/machines/{id}/status   running/idle/breakdown (+ reason)
  Worker & Tasks     GET  /api/prod/workers
                     POST /api/prod/tasks                  create a worker task
                     POST /api/prod/tasks/{id}/assign      hand a task to a worker
                     POST /api/prod/tasks/{id}/status      update progress
  Production Monitoring GET /api/prod/monitoring       live output, waste, downtime
                     POST /api/prod/output                 log metres produced (+ optional waste)
  Material Requests  GET  /api/prod/materials
                     POST /api/prod/materials              raise a shortage request to Purchase/Store
  QC Handover        GET  /api/prod/qc
                     POST /api/prod/qc/handover            submit finished rolls to QC
                     POST /api/prod/qc/rework              assign rework for a rejected roll
  Production Reports GET  /api/prod/reports
  Notifications      GET  /api/prod/notifications
                     POST /api/prod/notifications/{id}/read
                     POST /api/prod/notify-delay           tell the Supermanager an order is delayed
  Activity Logs      GET  /api/prod/activity

PERMISSIONS (enforced on the backend, not just hidden in the UI):
  - Every endpoint is guarded by `require_resource("pm_*")`, so only the
    Production Manager role reaches it (403 otherwise).
  - The manager plans production and assigns worker tasks, logs output/downtime,
    submits batches to QC and raises material shortage requests.
  - It CANNOT confirm buyer orders (only the Supermanager), approve/reject QC
    results (only the QC inspector), edit financial records, directly change
    stock quantities, or dispatch goods. None of those writes exist here;
    material needs go through the existing PurchaseRequest workflow and QC
    results stay with the quality module.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import rbac
from app.database import get_db
from app.deps import get_current_user, require_resource
from app.models import (
    ActivityLog,
    Employee,
    Machine,
    MachineStatusLog,
    Notification,
    Order,
    ProductionLog,
    PurchaseRequest,
    Roll,
    Task,
    TaskUpdate,
    User,
)
from app.services import prod_manager as pm
from app.services.production import order_progress_percent
from app.services.tasks import shown_status

router = APIRouter(prefix="/api/prod", tags=["production-manager"])

VALID_STAGES = ("spinning", "weaving", "dyeing")
VALID_STATUSES = ("running", "idle", "breakdown")
LOSS_STATUSES = ("idle", "breakdown")
PRIORITIES = ("low", "medium", "high", "urgent")
TASK_STATUSES = ("pending", "in_progress", "completed")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_order(db: Session, order_id: int) -> Order:
    o = db.get(Order, order_id)
    if o is None:
        raise HTTPException(404, "Order not found")
    return o


def _get_machine(db: Session, machine_id: int) -> Machine:
    m = db.get(Machine, machine_id)
    if m is None:
        raise HTTPException(404, "Machine not found")
    return m


def _close_open_logs(db: Session, machine_id: int, when: datetime) -> None:
    for log in (
        db.query(MachineStatusLog)
        .filter(MachineStatusLog.machine_id == machine_id, MachineStatusLog.end_time.is_(None))
        .all()
    ):
        log.end_time = when


def _log(db: Session, me: User, category: str, action: str, details: str) -> None:
    db.add(
        ActivityLog(
            user_id=me.id,
            user_name=me.name,
            user_role=me.role.name,
            category=category,
            action=action,
            details=details[:2000],
        )
    )


def _production_workers(db: Session, me: User):
    """Active workers in the production department (or reporting to this user)."""
    return (
        db.query(Employee)
        .filter(
            Employee.is_active.isnot(False),
            or_(Employee.department == "production", Employee.manager_user_id == me.id),
        )
        .order_by(Employee.name)
    )


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@router.get("/dashboard")
def dashboard(_=Depends(require_resource("pm_dashboard")), db: Session = Depends(get_db)):
    return pm.dashboard(db)


# --------------------------------------------------------------------------- #
# Production Orders (received from the Supermanager; read-only here)
# --------------------------------------------------------------------------- #
@router.get("/orders")
def orders(
    status: str | None = None,
    q: str | None = None,
    _=Depends(require_resource("pm_orders")),
    db: Session = Depends(get_db),
):
    query = db.query(Order).filter(Order.status.in_(pm.PRODUCTION_ORDERS + ("ready_to_ship", "dispatched")))
    if status:
        query = query.filter(Order.status == status)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(Order.order_no.ilike(like), Order.fabric_type.ilike(like), Order.colour.ilike(like)))
    rows = query.order_by(Order.deadline.is_(None), Order.deadline, Order.id).all()
    machines = db.query(Machine).order_by(Machine.type, Machine.name).all()
    return {
        "orders": [pm.order_row(db, o) for o in rows],
        "machines": [
            {"id": m.id, "name": m.name, "type": m.type, "status": m.current_status, "order_id": m.current_order_id}
            for m in machines
        ],
        "note": "Orders are confirmed by the Supermanager. You plan and produce them; you cannot confirm or cancel an order.",
    }


# --------------------------------------------------------------------------- #
# Production Planning — assign a machine + stage (+ record a target)
# --------------------------------------------------------------------------- #
class PlanIn(BaseModel):
    order_id: int
    machine_id: int
    stage: str
    target_meters: float | None = Field(default=None, ge=0, le=1_000_000)
    shift: str | None = Field(default=None, max_length=20)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("stage")
    @classmethod
    def _stage_ok(cls, v: str) -> str:
        if v not in VALID_STAGES:
            raise ValueError(f"stage must be one of {', '.join(VALID_STAGES)}")
        return v


@router.get("/planning")
def planning(_=Depends(require_resource("pm_planning")), db: Session = Depends(get_db)):
    orders = (
        db.query(Order)
        .filter(Order.status.in_(pm.PRODUCTION_ORDERS))
        .order_by(Order.deadline.is_(None), Order.deadline, Order.id)
        .all()
    )
    machines = db.query(Machine).order_by(Machine.type, Machine.name).all()
    return {
        "orders": [pm.order_row(db, o) for o in orders],
        "machines": [pm.machine_row(db, m) for m in machines],
        "stages": list(VALID_STAGES),
        "shortages": pm.material_shortages(db),
    }


@router.post("/plan")
def create_plan(
    body: PlanIn,
    me: User = Depends(get_current_user),
    _=Depends(require_resource("pm_planning")),
    db: Session = Depends(get_db),
):
    o = _get_order(db, body.order_id)
    if o.status not in pm.PRODUCTION_ORDERS:
        raise HTTPException(409, f"{o.order_no} is {o.status.replace('_', ' ')} and is not in production")
    m = _get_machine(db, body.machine_id)
    # Stage should suit the machine type (a dyeing machine does dyeing, etc.).
    if m.type != body.stage:
        raise HTTPException(400, f"{m.name} is a {m.type} machine and cannot run the {body.stage} stage")
    m.current_order_id = o.id
    m.current_stage = body.stage
    # Planning work starts the order moving into production (manager action;
    # the order itself was already confirmed by the Supermanager).
    if o.status == "confirmed":
        o.status = "in_production"
    tgt = f" · target {body.target_meters:,.0f} m" if body.target_meters else ""
    shift = f" · {body.shift} shift" if body.shift else ""
    note = f" · {body.note.strip()}" if body.note else ""
    _log(db, me, "production", "planned",
         f"Assigned {o.order_no} to {m.name} for {body.stage}{tgt}{shift}{note}")
    db.commit()
    return {"ok": True, "order_no": o.order_no, "machine": m.name, "stage": body.stage,
            "order_status": o.status, "progress": order_progress_percent(db, o)}


# --------------------------------------------------------------------------- #
# Production Stages (spinning / weaving / dyeing)
# --------------------------------------------------------------------------- #
@router.get("/stages")
def stages(_=Depends(require_resource("pm_stages")), db: Session = Depends(get_db)):
    orders = (
        db.query(Order)
        .filter(Order.status.in_(pm.PRODUCTION_ORDERS))
        .order_by(Order.deadline.is_(None), Order.deadline, Order.id)
        .all()
    )
    order_rows = [pm.order_row(db, o) for o in orders]
    out = {}
    for stage in VALID_STAGES:
        machines = [pm.machine_row(db, m) for m in db.query(Machine).filter(Machine.type == stage).order_by(Machine.name).all()]
        total = pm._f(
            db.query(func.coalesce(func.sum(ProductionLog.output_meters), 0))
            .filter(ProductionLog.stage == stage)
            .scalar()
        )
        today = pm._f(
            db.query(func.coalesce(func.sum(ProductionLog.output_meters), 0))
            .filter(ProductionLog.stage == stage, ProductionLog.log_date == date.today())
            .scalar()
        )
        out[stage] = {
            "machines": machines,
            "running": sum(1 for m in machines if m["status"] == "running"),
            "total_meters": total,
            "today_meters": today,
            "orders": [
                {"order_no": r["order_no"], "stage_meters": r["stages"][stage], "quantity_meters": r["quantity_meters"]}
                for r in order_rows
                if r["stages"][stage] > 0
            ],
        }
    return {"stages": out, "orders": order_rows}


# --------------------------------------------------------------------------- #
# Machine Management
# --------------------------------------------------------------------------- #
class StatusIn(BaseModel):
    status: str
    reason: str | None = None

    @field_validator("status")
    @classmethod
    def _status_ok(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {', '.join(VALID_STATUSES)}")
        return v


@router.get("/machines")
def machines(_=Depends(require_resource("pm_machines")), db: Session = Depends(get_db)):
    rows = [pm.machine_row(db, m) for m in db.query(Machine).order_by(Machine.type, Machine.name).all()]
    counts = {s: sum(1 for m in rows if m["status"] == s) for s in ("running", "idle", "maintenance")}
    total_loss = round(sum(m["loss_rupees"] for m in rows), 2)
    total_lost_hours = round(sum(m["lost_hours"] for m in rows), 2)
    return {
        "machines": rows,
        "counts": counts,
        "idle_loss": {"total_rupees": total_loss, "total_hours": total_lost_hours},
    }


@router.post("/machines/{machine_id}/status")
def set_machine_status(
    machine_id: int,
    body: StatusIn,
    me: User = Depends(get_current_user),
    _=Depends(require_resource("pm_machines")),
    db: Session = Depends(get_db),
):
    m = _get_machine(db, machine_id)
    if body.status in LOSS_STATUSES and not (body.reason and body.reason.strip()):
        raise HTTPException(400, f"A reason is required when setting status to '{body.status}'")
    now = _now()
    _close_open_logs(db, m.id, now)
    db.add(
        MachineStatusLog(
            machine_id=m.id,
            logged_by_user_id=me.id,
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
    return pm.machine_row(db, m)


# --------------------------------------------------------------------------- #
# Worker & Task Assignment
# --------------------------------------------------------------------------- #
class TaskIn(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    details: str | None = Field(default=None, max_length=2000)
    order_id: int | None = None
    worker_employee_id: int | None = None
    priority: str = "medium"
    deadline: date | None = None

    @field_validator("priority")
    @classmethod
    def _prio(cls, v: str) -> str:
        if v not in PRIORITIES:
            raise ValueError(f"priority must be one of {', '.join(PRIORITIES)}")
        return v


class AssignIn(BaseModel):
    worker_employee_id: int | None = None


class TaskStatusIn(BaseModel):
    status: str
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("status")
    @classmethod
    def _st(cls, v: str) -> str:
        if v not in TASK_STATUSES:
            raise ValueError(f"status must be one of {', '.join(TASK_STATUSES)}")
        return v


@router.get("/workers")
def workers(_=Depends(require_resource("pm_workers")), db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    emps = _production_workers(db, me).all()
    worker_rows = []
    for e in emps:
        tasks = db.query(Task).filter(Task.worker_employee_id == e.id).order_by(Task.id.desc()).all()
        worker_rows.append(
            {
                "id": e.id,
                "name": e.name,
                "role_on_floor": e.role_on_floor,
                "phone": e.phone,
                "open_tasks": sum(1 for t in tasks if t.status != "completed"),
                "tasks": [{"id": t.id, "title": t.title, "status": shown_status(t)} for t in tasks[:5]],
            }
        )
    tasks = (
        db.query(Task)
        .filter(Task.department == "production")
        .order_by(Task.id.desc())
        .all()
    )
    orders = (
        db.query(Order)
        .filter(Order.status.in_(pm.PRODUCTION_ORDERS))
        .order_by(Order.id.desc())
        .all()
    )
    return {
        "workers": worker_rows,
        "tasks": [pm.task_row(db, t) for t in tasks],
        "orders": [{"id": o.id, "order_no": o.order_no, "status": o.status} for o in orders],
    }


@router.post("/tasks", status_code=201)
def create_task(
    body: TaskIn,
    me: User = Depends(get_current_user),
    _=Depends(require_resource("pm_workers")),
    db: Session = Depends(get_db),
):
    if body.order_id is not None and db.get(Order, body.order_id) is None:
        raise HTTPException(400, "Unknown order")
    if body.worker_employee_id is not None:
        w = db.get(Employee, body.worker_employee_id)
        if w is None:
            raise HTTPException(400, "Unknown worker")
    t = Task(
        title=body.title.strip(),
        details=(body.details or "").strip() or None,
        department="production",
        manager_user_id=me.id,
        order_id=body.order_id,
        worker_employee_id=body.worker_employee_id,
        priority=body.priority,
        deadline=body.deadline,
        status="pending",
        created_by_user_id=me.id,
        auto=False,
    )
    db.add(t)
    db.commit()
    return pm.task_row(db, t)


def _get_prod_task(db: Session, me: User, task_id: int) -> Task:
    t = db.get(Task, task_id)
    # A production manager works only production tasks (its own or unassigned).
    if t is None or t.department != "production":
        raise HTTPException(404, "Task not found")
    return t


@router.post("/tasks/{task_id}/assign")
def assign_task(
    task_id: int,
    body: AssignIn,
    me: User = Depends(get_current_user),
    _=Depends(require_resource("pm_workers")),
    db: Session = Depends(get_db),
):
    t = _get_prod_task(db, me, task_id)
    if body.worker_employee_id is not None:
        w = db.get(Employee, body.worker_employee_id)
        if w is None:
            raise HTTPException(400, "Unknown worker")
    t.worker_employee_id = body.worker_employee_id
    if t.manager_user_id is None:
        t.manager_user_id = me.id
    t.updated_at = datetime.utcnow()
    worker = db.get(Employee, body.worker_employee_id) if body.worker_employee_id else None
    db.add(
        TaskUpdate(
            task_id=t.id,
            user_id=me.id,
            status=t.status,
            note=f"Assigned to {worker.name}" if worker else "Unassigned",
        )
    )
    db.commit()
    return pm.task_row(db, t)


@router.post("/tasks/{task_id}/status")
def update_task_status(
    task_id: int,
    body: TaskStatusIn,
    me: User = Depends(get_current_user),
    _=Depends(require_resource("pm_workers")),
    db: Session = Depends(get_db),
):
    t = _get_prod_task(db, me, task_id)
    t.status = body.status
    t.updated_at = datetime.utcnow()
    db.add(TaskUpdate(task_id=t.id, user_id=me.id, status=body.status, note=(body.note or "").strip() or None))
    db.commit()
    return pm.task_row(db, t)


# --------------------------------------------------------------------------- #
# Production Monitoring (output, waste, downtime) + log output
# --------------------------------------------------------------------------- #
class OutputIn(BaseModel):
    machine_id: int
    order_id: int
    output_meters: float = Field(gt=0, le=1_000_000)
    stage: str | None = None
    waste_meters: float = Field(default=0, ge=0, le=1_000_000)
    shift: str | None = Field(default=None, max_length=20)

    @field_validator("stage")
    @classmethod
    def _stage_ok(cls, v):
        if v is not None and v not in VALID_STAGES:
            raise ValueError(f"stage must be one of {', '.join(VALID_STAGES)}")
        return v


@router.get("/monitoring")
def monitoring(_=Depends(require_resource("pm_monitoring")), db: Session = Depends(get_db)):
    today = date.today()
    orders = (
        db.query(Order)
        .filter(Order.status.in_(pm.PRODUCTION_ORDERS))
        .order_by(Order.deadline.is_(None), Order.deadline, Order.id)
        .all()
    )
    order_rows = [pm.order_row(db, o) for o in orders]
    machines = [pm.machine_row(db, m) for m in db.query(Machine).order_by(Machine.type, Machine.name).all()]
    today_output = pm._f(
        db.query(func.coalesce(func.sum(ProductionLog.output_meters), 0))
        .filter(ProductionLog.log_date == today)
        .scalar()
    )
    # Recent output logs.
    recent = (
        db.query(ProductionLog)
        .order_by(ProductionLog.id.desc())
        .limit(15)
        .all()
    )
    recent_rows = []
    for r in recent:
        o = db.get(Order, r.order_id)
        mch = db.get(Machine, r.machine_id)
        recent_rows.append(
            {
                "machine": mch.name if mch else "",
                "order_no": o.order_no if o else "",
                "stage": r.stage,
                "output_meters": pm._f(r.output_meters),
                "log_date": pm._iso(r.log_date),
            }
        )
    downtime = [m for m in machines if m["status"] in ("idle", "maintenance")]
    return {
        "orders": order_rows,
        "machines": machines,
        "machine_counts": {s: sum(1 for m in machines if m["status"] == s) for s in ("running", "idle", "maintenance")},
        "today_output": today_output,
        "recent_output": recent_rows,
        "downtime": downtime,
        "idle_loss_total": round(sum(m["loss_rupees"] for m in machines), 2),
        "delays": [r for r in order_rows if r["delay"]],
    }


@router.post("/output")
def log_output(
    body: OutputIn,
    me: User = Depends(get_current_user),
    _=Depends(require_resource("pm_monitoring")),
    db: Session = Depends(get_db),
):
    m = _get_machine(db, body.machine_id)
    o = _get_order(db, body.order_id)
    if o.status not in pm.PRODUCTION_ORDERS:
        raise HTTPException(409, f"{o.order_no} is not in production")
    stage = body.stage or m.current_stage or m.type
    db.add(
        ProductionLog(
            machine_id=m.id,
            order_id=o.id,
            stage=stage,
            output_meters=body.output_meters,
            log_date=date.today(),
        )
    )
    if o.status == "confirmed":
        o.status = "in_production"
    waste = f" · waste {body.waste_meters:,.0f} m" if body.waste_meters else ""
    shift = f" · {body.shift} shift" if body.shift else ""
    _log(db, me, "production", "output_logged",
         f"{o.order_no}: {body.output_meters:,.0f} m {stage} on {m.name}{waste}{shift}")
    db.flush()
    progress = order_progress_percent(db, o)
    db.commit()
    return {
        "ok": True,
        "order_no": o.order_no,
        "machine": m.name,
        "logged_meters": body.output_meters,
        "waste_meters": body.waste_meters,
        "order_progress_percent": progress,
    }


# --------------------------------------------------------------------------- #
# Material Requests (shortage requests go to the existing Purchase/Store flow)
# --------------------------------------------------------------------------- #
class MaterialIn(BaseModel):
    yarn_type: str = Field(min_length=1, max_length=80)
    colour: str = Field(min_length=1, max_length=60)
    quantity_kg: float = Field(gt=0, le=1_000_000)
    order_id: int | None = None
    required_date: date | None = None
    reason: str | None = Field(default=None, max_length=1000)


@router.get("/materials")
def materials(_=Depends(require_resource("pm_materials")), db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    shortages = pm.material_shortages(db)
    # Requests this production manager has raised.
    mine = (
        db.query(PurchaseRequest)
        .filter(PurchaseRequest.requested_by_user_id == me.id)
        .order_by(PurchaseRequest.id.desc())
        .limit(30)
        .all()
    )
    requests = []
    for r in mine:
        o = db.get(Order, r.order_id) if r.order_id else None
        requests.append(
            {
                "id": r.id,
                "pr_no": r.pr_no,
                "yarn_type": r.yarn_type,
                "colour": r.colour,
                "quantity_kg": pm._f(r.quantity_kg),
                "order_no": o.order_no if o else None,
                "required_date": pm._iso(r.required_date),
                "status": r.status,
                "reason": r.reason,
                "decision_note": r.decision_note,
                "created_at": pm._iso(r.created_at),
            }
        )
    return {
        "shortages": shortages,
        "requests": requests,
        "note": "Shortage requests go to the Purchase/Store desk for approval. You cannot change stock yourself.",
    }


@router.post("/materials", status_code=201)
def request_material(
    body: MaterialIn,
    me: User = Depends(get_current_user),
    _=Depends(require_resource("pm_materials")),
    db: Session = Depends(get_db),
):
    from app.settings_store import get_setting

    if body.order_id is not None and db.get(Order, body.order_id) is None:
        raise HTTPException(400, "Unknown order")
    # Reuse the store's PR numbering so numbers never collide.
    n = db.query(func.count(PurchaseRequest.id)).scalar() or 0
    r = PurchaseRequest(
        pr_no=f"PR-{5001 + n}",
        yarn_type=body.yarn_type.strip(),
        colour=body.colour.strip(),
        quantity_kg=body.quantity_kg,
        required_date=body.required_date,
        reason=(body.reason or "").strip() or f"Raised by production for {body.colour} yarn shortage",
        source="production",
        order_id=body.order_id,
        status="pending",
        requested_by_user_id=me.id,
    )
    db.add(r)
    # Honour the same auto-approve threshold the store uses.
    limit = float(get_setting(db, "purchase_auto_approve_kg") or 0)
    if limit > 0 and body.quantity_kg <= limit:
        r.status = "approved"
        r.decision_note = f"Approved automatically (up to {limit:,.0f} kg)."
        r.decided_at = datetime.utcnow()
    else:
        db.add(
            Notification(
                to_role=rbac.ROLE_MANAGER,
                kind="approval",
                title=f"Material request {r.pr_no} needs approval",
                body=f"{body.quantity_kg:,.0f} kg {body.yarn_type} {body.colour}"
                + (f" · {r.reason}" if r.reason else ""),
                from_user_name=me.name,
            )
        )
        # Also tell the store desk a production request has arrived.
        db.add(
            Notification(
                to_role=rbac.ROLE_STORE_MANAGER,
                kind="availability",
                title=f"Production raised {r.pr_no}",
                body=f"{body.quantity_kg:,.0f} kg {body.yarn_type} {body.colour}",
                from_user_name=me.name,
            )
        )
    _log(db, me, "stock", "material_requested",
         f"{r.pr_no}: {body.quantity_kg:,.0f} kg {body.yarn_type} {body.colour}")
    db.commit()
    return {"ok": True, "pr_no": r.pr_no, "status": r.status, "quantity_kg": pm._f(r.quantity_kg)}


# --------------------------------------------------------------------------- #
# QC Handover (submit batches to QC; assign rework for rejects)
# --------------------------------------------------------------------------- #
class HandoverIn(BaseModel):
    order_id: int
    machine_id: int
    rolls: int = Field(gt=0, le=200)
    length_meters: float = Field(gt=0, le=100000)


class ReworkIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


@router.get("/qc")
def qc(_=Depends(require_resource("pm_qc")), db: Session = Depends(get_db)):
    orders = (
        db.query(Order)
        .filter(Order.status.in_(pm.PRODUCTION_ORDERS))
        .order_by(Order.id.desc())
        .all()
    )
    machines = db.query(Machine).order_by(Machine.type, Machine.name).all()
    # Results summary per order from existing rolls.
    recent = []
    for r in db.query(Roll).order_by(Roll.id.desc()).limit(20).all():
        o = db.get(Order, r.order_id)
        recent.append(
            {
                "roll_no": r.roll_no,
                "order_no": o.order_no if o else None,
                "length_meters": pm._f(r.length_meters),
                "status": r.status,
            }
        )
    return {
        "pending": pm.qc_pending(db),
        "rework_rejects": pm.rejected_rolls(db),
        "recent_rolls": recent,
        "orders": [{"id": o.id, "order_no": o.order_no, "fabric_type": o.fabric_type} for o in orders],
        "machines": [{"id": m.id, "name": m.name} for m in machines],
        "rule": "QC inspects every roll you hand over. Only the QC Manager can pass, rework or reject — you cannot approve quality yourself.",
    }


@router.post("/qc/handover", status_code=201)
def qc_handover(
    body: HandoverIn,
    me: User = Depends(get_current_user),
    _=Depends(require_resource("pm_qc")),
    db: Session = Depends(get_db),
):
    o = _get_order(db, body.order_id)
    if o.status not in pm.PRODUCTION_ORDERS:
        raise HTTPException(409, f"{o.order_no} is not in production")
    m = _get_machine(db, body.machine_id)
    per_roll = round(body.length_meters / body.rolls, 2)
    start = db.query(func.count(Roll.id)).scalar() or 0
    created = []
    for i in range(body.rolls):
        roll = Roll(
            order_id=o.id,
            machine_id=m.id,
            roll_no=f"R-{start + i + 1:04d}",
            length_meters=per_roll,
            status="pending",  # 'pending' = waiting for QC inspection
        )
        db.add(roll)
        created.append(roll.roll_no)
    # Finished producing: move the order into the quality stage. The QC Manager
    # owns the pass/reject decision from here.
    if o.status in ("confirmed", "in_production"):
        o.status = "in_quality"
    _log(db, me, "qc", "handover",
         f"Submitted {body.rolls} roll(s) ({body.length_meters:,.0f} m) of {o.order_no} to QC")
    db.commit()
    return {"ok": True, "order_no": o.order_no, "rolls_created": created, "order_status": o.status}


@router.post("/qc/rework/{roll_id}")
def assign_rework(
    roll_id: int,
    body: ReworkIn,
    me: User = Depends(get_current_user),
    _=Depends(require_resource("pm_qc")),
    db: Session = Depends(get_db),
):
    r = db.get(Roll, roll_id)
    if r is None:
        raise HTTPException(404, "Roll not found")
    if r.status != "rework":
        raise HTTPException(409, "Only rolls QC marked for rework can be sent back to production")
    o = db.get(Order, r.order_id)
    # Create a worker task so the rework is tracked and assignable.
    t = Task(
        title=f"Rework roll {r.roll_no}" + (f" ({o.order_no})" if o else ""),
        details=(body.note or "").strip() or "Roll returned by QC for rework.",
        department="production",
        manager_user_id=me.id,
        order_id=r.order_id,
        priority="high",
        status="pending",
        created_by_user_id=me.id,
        auto=False,
    )
    db.add(t)
    _log(db, me, "qc", "rework_assigned", f"Rework assigned for roll {r.roll_no}")
    db.commit()
    return {"ok": True, "roll_no": r.roll_no, "task_id": t.id}


# --------------------------------------------------------------------------- #
# Production Reports
# --------------------------------------------------------------------------- #
@router.get("/reports")
def reports(
    start: date | None = None,
    end: date | None = None,
    _=Depends(require_resource("pm_reports")),
    db: Session = Depends(get_db),
):
    today = date.today()
    s = start or today.replace(day=1)
    e = end or today
    if e < s:
        raise HTTPException(400, "end must be on or after start")

    # Output per machine and per stage in the window.
    per_machine = []
    for m in db.query(Machine).order_by(Machine.type, Machine.name).all():
        out_m = pm._f(
            db.query(func.coalesce(func.sum(ProductionLog.output_meters), 0))
            .filter(ProductionLog.machine_id == m.id, ProductionLog.log_date.between(s, e))
            .scalar()
        )
        loss = pm.idle_loss_for_machine(db, m.id, float(m.hourly_cost or 0), now=_now())
        per_machine.append(
            {
                "machine": m.name,
                "type": m.type,
                "output_meters": out_m,
                "lost_hours": loss["lost_hours"],
                "loss_rupees": loss["loss_rupees"],
            }
        )
    per_stage = {}
    for stage in VALID_STAGES:
        per_stage[stage] = pm._f(
            db.query(func.coalesce(func.sum(ProductionLog.output_meters), 0))
            .filter(ProductionLog.stage == stage, ProductionLog.log_date.between(s, e))
            .scalar()
        )
    # Output per order in the window.
    per_order = []
    order_ids = [
        oid
        for (oid,) in db.query(ProductionLog.order_id)
        .filter(ProductionLog.log_date.between(s, e))
        .distinct()
        .all()
    ]
    for oid in order_ids:
        o = db.get(Order, oid)
        if o is None:
            continue
        made = pm._f(
            db.query(func.coalesce(func.sum(ProductionLog.output_meters), 0))
            .filter(ProductionLog.order_id == oid, ProductionLog.log_date.between(s, e))
            .scalar()
        )
        per_order.append(
            {
                "order_no": o.order_no,
                "fabric": f"{o.fabric_type} {o.colour}",
                "ordered_meters": pm._f(o.quantity_meters),
                "output_meters": made,
                "status": o.status,
            }
        )
    per_order.sort(key=lambda r: -r["output_meters"])
    # Daily output trend.
    daily = [
        {"day": pm._iso(d), "meters": pm._f(v)}
        for d, v in db.query(ProductionLog.log_date, func.sum(ProductionLog.output_meters))
        .filter(ProductionLog.log_date.between(s, e))
        .group_by(ProductionLog.log_date)
        .order_by(ProductionLog.log_date)
        .all()
    ]
    total_output = round(sum(r["output_meters"] for r in per_machine), 2)
    return {
        "start": s.isoformat(),
        "end": e.isoformat(),
        "total_output": total_output,
        "total_lost_hours": round(sum(r["lost_hours"] for r in per_machine), 2),
        "total_loss_rupees": round(sum(r["loss_rupees"] for r in per_machine), 2),
        "per_machine": per_machine,
        "per_stage": per_stage,
        "per_order": per_order,
        "daily": daily,
    }


# --------------------------------------------------------------------------- #
# Notifications (bell list for the production manager)
# --------------------------------------------------------------------------- #
@router.get("/notifications")
def notifications(_=Depends(require_resource("pm_notifications")), db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    rows = (
        db.query(Notification)
        .filter(
            or_(
                Notification.to_user_id == me.id,
                Notification.to_role == rbac.ROLE_PRODUCTION_MANAGER,
            )
        )
        .order_by(Notification.id.desc())
        .limit(50)
        .all()
    )
    return {
        "notifications": [
            {
                "id": n.id,
                "kind": n.kind,
                "title": n.title,
                "body": n.body,
                "from": n.from_user_name,
                "created_at": pm._iso(n.created_at),
                "read": n.read_at is not None,
            }
            for n in rows
        ],
        "unread": sum(1 for n in rows if n.read_at is None),
    }


@router.post("/notifications/{nid}/read")
def mark_read(nid: int, _=Depends(require_resource("pm_notifications")), db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    n = db.get(Notification, nid)
    if n is None or (n.to_user_id != me.id and n.to_role != rbac.ROLE_PRODUCTION_MANAGER):
        raise HTTPException(404, "Notification not found")
    if n.read_at is None:
        n.read_at = datetime.utcnow()
        db.commit()
    return {"ok": True, "id": nid}


class DelayIn(BaseModel):
    order_id: int
    message: str = Field(min_length=3, max_length=1000)


@router.post("/notify-delay")
def notify_delay(
    body: DelayIn,
    me: User = Depends(get_current_user),
    _=Depends(require_resource("pm_notifications")),
    db: Session = Depends(get_db),
):
    o = _get_order(db, body.order_id)
    db.add(
        Notification(
            to_role=rbac.ROLE_MANAGER,
            kind="info",
            title=f"Delay reported on {o.order_no}",
            body=body.message.strip(),
            from_user_name=me.name,
        )
    )
    _log(db, me, "order", "delay_reported", f"{o.order_no}: {body.message.strip()}")
    db.commit()
    return {"ok": True, "order_no": o.order_no}


# --------------------------------------------------------------------------- #
# Activity Logs (floor-relevant trail, read-only)
# --------------------------------------------------------------------------- #
@router.get("/activity")
def activity(
    category: str | None = None,
    q: str | None = None,
    limit: int = Query(60, ge=1, le=200),
    _=Depends(require_resource("pm_activity")),
    db: Session = Depends(get_db),
):
    floor_cats = ("production", "task", "qc", "order", "worker", "stock")
    query = db.query(ActivityLog).filter(ActivityLog.category.in_(floor_cats))
    if category:
        query = query.filter(ActivityLog.category == category)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(ActivityLog.details.ilike(like), ActivityLog.user_name.ilike(like)))
    rows = query.order_by(ActivityLog.id.desc()).limit(limit).all()
    return {
        "rows": [pm.activity_row(a) for a in rows],
        "categories": list(floor_cats),
    }

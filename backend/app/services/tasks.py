"""Instructions (tasks) for department managers."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.departments import DEPT_MANAGER_ROLES, dept_of
from app.models import Role, Task, User


def manager_for_department(db: Session, dept: str) -> User | None:
    """First active department manager running `dept` (None if nobody)."""
    users = (
        db.query(User).join(Role)
        .filter(Role.name.in_(DEPT_MANAGER_ROLES), User.is_active.is_(True))
        .order_by(User.id).all()
    )
    for u in users:
        if dept_of(u) == dept:
            return u
    return None


def is_overdue(t: Task, today: date | None = None) -> bool:
    today = today or date.today()
    return bool(t.deadline and t.status != "completed" and t.deadline < today)


def shown_status(t: Task) -> str:
    """pending | in_progress | completed | delayed (= overdue and not done)."""
    return "delayed" if is_overdue(t) else t.status


def create_order_tasks(db: Session, order, actor_id: int | None, yarn_short_kg: float) -> list[Task]:
    """On confirmation, give each department its instruction for the order."""
    deadline = order.deadline
    before = (lambda days: max(date.today(), deadline - timedelta(days=days))) if deadline else (lambda days: None)
    plan = []
    if yarn_short_kg > 0:
        plan.append(("purchase", "urgent", before(10),
                     f"Buy {yarn_short_kg:.0f} kg {order.colour} yarn for {order.order_no}",
                     f"Stock is short by {yarn_short_kg:.2f} kg. Raise a purchase order and receive it into the store."))
    plan += [
        ("store", "high", before(8), f"Issue yarn for {order.order_no}",
         f"Reserve and issue {order.colour} yarn for {float(order.quantity_meters):,.0f} m of {order.fabric_type}."),
        ("production", "high", before(4), f"Produce {order.order_no}",
         f"{float(order.quantity_meters):,.0f} m {order.fabric_type}, {order.colour}. Spinning → weaving → dyeing."),
        ("qc", "medium", before(2), f"Inspect rolls of {order.order_no}",
         "Inspect every roll; only passed rolls may be dispatched."),
        ("dispatch", "medium", deadline, f"Dispatch {order.order_no}",
         "Pack passed rolls, check roll IDs and quantity against the order, load and ship."),
    ]
    tasks = []
    for dept, prio, dl, title, details in plan:
        mgr = manager_for_department(db, dept)
        t = Task(title=title, details=details, department=dept,
                 manager_user_id=mgr.id if mgr else None, order_id=order.id,
                 priority=prio, deadline=dl, status="pending",
                 created_by_user_id=actor_id, auto=True)
        db.add(t)
        tasks.append(t)
    return tasks


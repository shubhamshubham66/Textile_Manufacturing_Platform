"""Real-time updates: turn database changes into live events for open screens.

How it works
- SQLAlchemy session hooks watch what each request saves (machine status,
  order stage, yarn stock, rolls/quality, payments, production, wages).
- After the transaction COMMITS, each change becomes one small event and is
  handed to the in-process `bus`. A rolled-back change never becomes an event.
- `/api/live/stream` (routers/live.py) keeps a Server-Sent Events connection per
  open browser and forwards only the events that user's role may see. A buyer
  only gets events about their own orders and payments.

The bus lives in this process, which fits the single Uvicorn worker on Render.
Running several workers would need a shared broker (e.g. Redis pub/sub).
"""

from __future__ import annotations

import asyncio
import itertools
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session

from app import rbac

OWNER = rbac.ROLE_OWNER
STORE = rbac.ROLE_STORE_MANAGER
QUALITY = rbac.ROLE_QUALITY_INSPECTOR
ACCOUNTS = rbac.ROLE_ACCOUNTANT
MANAGER = rbac.ROLE_MANAGER
PROD = rbac.ROLE_PRODUCTION_MANAGER
SALES = rbac.ROLE_SALES_MANAGER
ACCT_MGR = rbac.ROLE_ACCOUNTS_MANAGER
STAFF = [OWNER, MANAGER, PROD, SALES, STORE, QUALITY, ACCOUNTS, ACCT_MGR]

# Topic -> roles whose screens should refresh for it. The production manager
# (PROD) watches the floor; the sales & dispatch manager (SALES) watches orders,
# QC-approved stock (quality), dispatches and payment follow-up.
TOPIC_ROLES = {
    "machines": [OWNER, MANAGER, PROD],
    "production": [OWNER, MANAGER, PROD, QUALITY],
    "orders": STAFF,
    "yarn": [OWNER, MANAGER, PROD, STORE],
    "quality": [OWNER, MANAGER, PROD, SALES, QUALITY, STORE],
    "payments": [OWNER, MANAGER, SALES, ACCOUNTS, ACCT_MGR],
    "wages": [OWNER, MANAGER, PROD, ACCOUNTS, ACCT_MGR],
    # Supermanager instructions to department managers.
    "tasks": [MANAGER, PROD, SALES, STORE, QUALITY, ACCOUNTS, ACCT_MGR],
    # Purchase requests, purchase orders, receiving.
    "purchase": [OWNER, MANAGER, PROD, STORE],
    "notifications": [MANAGER, PROD, SALES, STORE, QUALITY, ACCOUNTS, ACCT_MGR],
}

ORDER_STAGE_LABEL = {
    "draft": "Draft",
    "confirmed": "Confirmed",
    "in_production": "In production",
    "in_quality": "In quality check",
    "ready_to_ship": "Ready to ship",
    "dispatched": "Dispatched",
    "closed": "Closed",
}

_ids = itertools.count(1)


@dataclass
class LiveEvent:
    topic: str
    roles: list[str]
    message: str = ""
    level: str = "info"  # info | success | warn | alert
    notify: bool = False  # show in the bell / as a toast (else refresh only)
    notify_roles: list[str] | None = None  # who gets the notification (default: roles)
    buyer_id: int | None = None  # also deliver to this buyer's login
    buyer_message: str | None = None  # wording for the buyer (None = refresh only)
    id: int = field(default_factory=lambda: next(_ids))
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def for_user(self, role: str, buyer_id: int | None) -> dict | None:
        """The event as this user should see it, or None if not for them."""
        if role == rbac.ROLE_BUYER:
            if self.buyer_id is None or buyer_id != self.buyer_id:
                return None
            msg = self.buyer_message
            notify = bool(msg)
        elif role in self.roles:
            msg = self.message
            notify = self.notify and role in (self.notify_roles or self.roles)
        else:
            return None
        return {
            "id": self.id,
            "topic": self.topic,
            "message": msg or "",
            "level": self.level,
            "notify": notify,
            "at": self.at,
        }


class LiveBus:
    """Fan-out of events to every open stream, safe to call from any thread."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subs: set[asyncio.Queue] = set()
        self._lock = threading.Lock()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        with self._lock:
            self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            self._subs.discard(q)

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subs)

    def publish(self, events: list[LiveEvent]) -> None:
        loop = self._loop
        if loop is None or not events:
            return
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            for ev in events:
                loop.call_soon_threadsafe(_offer, q, ev)


def _offer(q: asyncio.Queue, ev: LiveEvent) -> None:
    try:
        q.put_nowait(ev)
    except asyncio.QueueFull:
        pass  # a stuck client; it resyncs on reconnect anyway


bus = LiveBus()


# --------------------------------------------------------------------------- #
# Turning saved changes into events
# --------------------------------------------------------------------------- #
def _changed(obj, attr: str, session: Session | None = None):
    """(old, new) if `attr` changed in this flush, else None.

    After a commit the object's attributes are expired, so a later change has
    no remembered old value; then the old value is read from the database
    (still unchanged, since this runs before the flush writes anything).
    """
    hist = inspect(obj).attrs[attr].history
    if not hist.has_changes():
        return None
    new = hist.added[0] if hist.added else None
    if hist.deleted:
        old = hist.deleted[0]
    elif session is not None:
        cls = type(obj)
        old = session.execute(
            select(getattr(cls, attr)).where(cls.id == obj.id)
        ).scalar_one_or_none()
    else:
        old = None
    return old, new


def _rupees(v) -> str:
    try:
        n = float(v)
    except (TypeError, ValueError):
        return str(v)
    return f"₹{n:,.0f}"


def _collect(session: Session) -> list[LiveEvent]:
    from app import models as m  # local import: models imports database, not us

    out: list[LiveEvent] = []
    with session.no_autoflush:
        for obj in list(session.new) + list(session.dirty):
            is_new = obj in session.new

            if isinstance(obj, m.Machine) and is_new:
                out.append(LiveEvent("machines", TOPIC_ROLES["machines"],
                                     f"New machine added: {obj.name}", "info", notify=True,
                                     notify_roles=[OWNER]))

            elif isinstance(obj, m.Machine) and not is_new:
                ch = _changed(obj, "current_status", session)
                if ch and ch[0] != ch[1]:
                    status = ch[1]
                    level = {"breakdown": "alert", "idle": "warn"}.get(status, "success")
                    word = {"breakdown": "broke down", "idle": "is idle", "running": "is running again"}.get(status, f"is {status}")
                    out.append(LiveEvent("machines", TOPIC_ROLES["machines"], f"{obj.name} {word}", level, notify=True))
                else:
                    # Other machine edits (name / costs) — refresh the machine views.
                    out.append(LiveEvent("machines", TOPIC_ROLES["machines"]))

            elif isinstance(obj, m.Buyer):
                # New or edited buyer — refresh order/payment screens that list them.
                out.append(LiveEvent("orders", STAFF))

            elif isinstance(obj, m.Supplier):
                out.append(LiveEvent("payments", TOPIC_ROLES["payments"] + [STORE]))
                out.append(LiveEvent("purchase", TOPIC_ROLES["purchase"]))

            elif isinstance(obj, m.Employee):
                out.append(LiveEvent("wages", TOPIC_ROLES["wages"]))

            elif isinstance(obj, m.PurchaseRequest):
                if is_new:
                    need = obj.status == "pending"
                    out.append(LiveEvent("purchase", TOPIC_ROLES["purchase"],
                                         f"Purchase request {obj.pr_no}: {float(obj.quantity_kg):,.0f} kg {obj.colour}"
                                         + (" needs approval" if need else " approved automatically"),
                                         "info", notify=True, notify_roles=[MANAGER] if need else [STORE]))
                else:
                    ch = _changed(obj, "status", session)
                    if ch and ch[0] != ch[1] and ch[1] in ("approved", "rejected"):
                        out.append(LiveEvent("purchase", TOPIC_ROLES["purchase"],
                                             f"Purchase request {obj.pr_no} {ch[1]}",
                                             "success" if ch[1] == "approved" else "warn", notify=True, notify_roles=[STORE]))
                    else:
                        out.append(LiveEvent("purchase", TOPIC_ROLES["purchase"]))

            elif isinstance(obj, m.PurchaseOrder):
                out.append(LiveEvent("purchase", TOPIC_ROLES["purchase"]))

            elif isinstance(obj, m.YarnReceipt):
                if is_new and obj.status == "recorded":
                    out.append(LiveEvent("purchase", TOPIC_ROLES["purchase"],
                                         f"Delivery recorded: {float(obj.quantity_kg):,.0f} kg {obj.yarn_type} {obj.colour}"
                                         + (f" — flagged {obj.discrepancy.replace(',', ', ')}" if obj.discrepancy else ""),
                                         "warn" if obj.discrepancy else "info", notify=True, notify_roles=[STORE]))
                else:
                    out.append(LiveEvent("purchase", TOPIC_ROLES["purchase"]))

            elif isinstance(obj, m.Notification) and is_new:
                roles = [obj.to_role] if obj.to_role else TOPIC_ROLES["notifications"]
                # Approvals already announce themselves; shared availability is news.
                out.append(LiveEvent("notifications", roles, obj.title, "info",
                                     notify=bool(obj.to_role) and obj.kind == "availability"))

            elif isinstance(obj, m.Task):
                if is_new:
                    out.append(LiveEvent("tasks", TOPIC_ROLES["tasks"], f"New instruction: {obj.title}", "info",
                                         notify=True, notify_roles=[PROD, STORE, QUALITY, ACCOUNTS]))
                else:
                    out.append(LiveEvent("tasks", TOPIC_ROLES["tasks"], f"Task updated: {obj.title} ({obj.status.replace('_', ' ')})",
                                         "info", notify=True, notify_roles=[MANAGER]))

            elif isinstance(obj, m.Order):
                if is_new:
                    out.append(LiveEvent("orders", TOPIC_ROLES["orders"], f"New order {obj.order_no}", "info",
                                         notify=True, notify_roles=[OWNER, MANAGER, STORE], buyer_id=obj.buyer_id,
                                         buyer_message=f"Order {obj.order_no} was placed"))
                else:
                    ch = _changed(obj, "status", session)
                    if ch and ch[0] != ch[1]:
                        stage = ORDER_STAGE_LABEL.get(ch[1], ch[1])
                        out.append(LiveEvent("orders", TOPIC_ROLES["orders"], f"{obj.order_no} moved to {stage}", "info",
                                             notify=True, buyer_id=obj.buyer_id,
                                             buyer_message=f"Your order {obj.order_no} is now {stage}"))

            elif isinstance(obj, m.YarnStock):
                ch = None if is_new else _changed(obj, "quantity_kg", session)
                if is_new or ch:
                    qty = float(obj.quantity_kg or 0)
                    level_kg = float(obj.reorder_level_kg or 0)
                    was = float(ch[0]) if ch and ch[0] is not None else None
                    dropped_below = level_kg > 0 and qty < level_kg and (was is None or was >= level_kg)
                    if dropped_below:
                        out.append(LiveEvent("yarn", TOPIC_ROLES["yarn"],
                                             f"Low stock: {obj.yarn_type} ({obj.colour}) at {qty:,.0f} kg", "warn", notify=True))
                    else:
                        out.append(LiveEvent("yarn", TOPIC_ROLES["yarn"]))

            elif isinstance(obj, m.QualityInspection) and is_new:
                roll = obj.roll or session.get(m.Roll, obj.roll_id)
                name = roll.roll_no if roll else f"#{obj.roll_id}"
                level = {"pass": "success", "rework": "warn", "reject": "alert"}.get(obj.result, "info")
                out.append(LiveEvent("quality", TOPIC_ROLES["quality"], f"Roll {name}: {obj.result}", level, notify=True,
                                     notify_roles=[OWNER, QUALITY, PROD] + ([STORE, SALES, MANAGER] if obj.result == "pass" else []),
                                     buyer_id=roll.order.buyer_id if roll and roll.order else None))

            elif isinstance(obj, m.Roll):
                order = obj.order or (session.get(m.Order, obj.order_id) if obj.order_id else None)
                out.append(LiveEvent("quality", TOPIC_ROLES["quality"],
                                     buyer_id=order.buyer_id if order else None))

            elif isinstance(obj, (m.ProductionLog, m.MachineStatusLog)):
                out.append(LiveEvent("production", TOPIC_ROLES["production"]))

            elif isinstance(obj, m.Payment) and is_new:
                if obj.direction == "incoming":
                    buyer = session.get(m.Buyer, obj.buyer_id) if obj.buyer_id else None
                    who = f" from {buyer.name}" if buyer else ""
                    out.append(LiveEvent("payments", TOPIC_ROLES["payments"], f"{_rupees(obj.amount)} received{who}", "success",
                                         notify=True, buyer_id=obj.buyer_id,
                                         buyer_message=f"Payment of {_rupees(obj.amount)} recorded"))
                else:
                    out.append(LiveEvent("payments", TOPIC_ROLES["payments"], f"{_rupees(obj.amount)} paid to supplier", "info", notify=True))

            elif isinstance(obj, m.Payment) and not is_new:
                ch = _changed(obj, "voided_at", session)
                if ch and ch[0] is None and ch[1] is not None:
                    out.append(LiveEvent("payments", TOPIC_ROLES["payments"],
                                         f"{_rupees(obj.amount)} payment voided", "warn", notify=True,
                                         buyer_id=obj.buyer_id,
                                         buyer_message=(f"A payment of {_rupees(obj.amount)} was voided"
                                                        if obj.direction == "incoming" else None)))

            elif isinstance(obj, (m.Invoice, m.Dispatch)):
                out.append(LiveEvent("payments" if isinstance(obj, m.Invoice) else "orders",
                                     TOPIC_ROLES["payments"] + [STORE, SALES], buyer_id=getattr(obj, "buyer_id", None)))

            elif isinstance(obj, (m.Attendance, m.Wage)):
                out.append(LiveEvent("wages", TOPIC_ROLES["wages"]))
    return out


@event.listens_for(Session, "before_flush")
def _before_flush(session, flush_context, instances):  # noqa: ARG001
    try:
        found = _collect(session)
    except Exception:  # noqa: BLE001 - live updates must never break a save
        found = []
    if found:
        session.info.setdefault("live_events", []).extend(found)


@event.listens_for(Session, "after_commit")
def _after_commit(session):
    events = session.info.pop("live_events", None)
    if events:
        bus.publish(events)


@event.listens_for(Session, "after_rollback")
def _after_rollback(session):
    session.info.pop("live_events", None)

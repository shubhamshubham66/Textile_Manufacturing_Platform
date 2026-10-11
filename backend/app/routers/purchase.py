"""Purchase & Raw Material desk — /api/purchase/* (store manager role).

Flow: instruction / low stock → purchase request → Supermanager approval
(unless under the auto-approve limit) → purchase order → receipt recorded →
receipt validated (only now does stock go up) → PO partial/received.

Every stock change writes a StockMovement (app/activity.py) and an activity
log entry. Nothing here deletes history: requests and POs are cancelled or
rejected, receipts are rejected, never removed.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import rbac
from app.config import get_settings
from app.database import get_db
from app.departments import dept_of
from app.deps import get_current_user, require_resource
from app.models import (
    Notification,
    Order,
    OrderItem,
    ProductionLog,
    PurchaseOrder,
    PurchaseRequest,
    StockMovement,
    Supplier,
    Task,
    User,
    YarnReceipt,
    YarnStock,
)
from app.services.tasks import shown_status
from app.settings_store import get_setting

settings = get_settings()
router = APIRouter(prefix="/api/purchase", tags=["purchase"])

ACTIVE = ("confirmed", "in_production")
UPCOMING = ("draft", "pending_review", "clarification")
OPEN_PO = ("raised", "partial")


def _f(v) -> float:
    return round(float(v or 0), 2)


def _iso(v):
    return v.isoformat() if v else None


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _clean(v: str | None, n: int) -> str | None:
    v = (v or "").strip()
    return v[:n] or None


def _strip_required(v: str) -> str:
    v = (v or "").strip()
    if not v:
        raise ValueError("must not be blank")
    return v


# --------------------------------------------------------------------------- #
# Shared calculations
# --------------------------------------------------------------------------- #
def reserved_by_colour(db: Session) -> dict[str, float]:
    """Yarn already promised to confirmed / in-production orders (by colour).
    Order yarn need = metres × YARN_KG_PER_METER, less what has been woven."""
    out: dict[str, float] = defaultdict(float)
    for o in db.query(Order).filter(Order.status.in_(ACTIVE)).all():
        out[_norm(o.colour)] += _order_need_left(db, o)
    return out


def _order_need_kg(db: Session, o: Order) -> float:
    item = db.query(OrderItem).filter(OrderItem.order_id == o.id).first()
    if item is not None:
        return float(item.required_qty_kg or 0)
    return float(o.quantity_meters or 0) * settings.yarn_kg_per_meter


def _order_need_left(db: Session, o: Order) -> float:
    need = _order_need_kg(db, o)
    spun = db.query(func.coalesce(func.sum(ProductionLog.output_meters), 0)).filter(
        ProductionLog.order_id == o.id, ProductionLog.stage == "spinning").scalar() or 0
    used = float(spun) * settings.yarn_kg_per_meter
    return max(0.0, need - used)


def stock_rows(db: Session) -> list[dict]:
    reserved = reserved_by_colour(db)
    left = dict(reserved)
    rows = []
    for s in db.query(YarnStock).order_by(YarnStock.yarn_type, YarnStock.colour).all():
        qty = _f(s.quantity_kg)
        r = min(qty, left.get(_norm(s.colour), 0.0))
        left[_norm(s.colour)] = left.get(_norm(s.colour), 0.0) - r
        lvl = _f(s.reorder_level_kg) or settings.default_reorder_level_kg
        rows.append({
            "id": s.id, "yarn_type": s.yarn_type, "colour": s.colour, "unit": "kg",
            "quantity_kg": qty, "reserved_kg": round(r, 2), "available_kg": round(qty - r, 2),
            "reorder_level_kg": _f(s.reorder_level_kg), "low": qty <= lvl,
            "location": s.location, "unit_cost": _f(s.unit_cost),
            "value": round(qty * float(s.unit_cost or 0), 2),
            "updated_at": _iso(s.updated_at),
        })
    return rows


def _po_received(db: Session, po_id: int) -> float:
    rows = db.query(YarnReceipt).filter(YarnReceipt.purchase_order_id == po_id,
                                        YarnReceipt.status == "validated").all()
    return round(sum(float(r.quantity_kg or 0) - float(r.damaged_kg or 0) for r in rows), 2)


def _sup_name(db: Session, sid: int | None) -> str:
    s = db.get(Supplier, sid) if sid else None
    return s.name if s else ""


def _user_name(db: Session, uid: int | None) -> str | None:
    u = db.get(User, uid) if uid else None
    return u.name if u else None


def _my_depts(user: User) -> set[str]:
    """Departments whose instructions this store-role login handles. A store
    manager with no explicit department covers purchase, store and dispatch.
    The dedicated Purchase & Raw Material manager covers purchase + store (it
    does not run dispatch)."""
    if user.role.name == rbac.ROLE_STORE_MANAGER and not user.department:
        return {"purchase", "store", "dispatch"}
    if user.role.name == rbac.ROLE_PURCHASE_MANAGER:
        return {"purchase", "store"}
    d = dept_of(user)
    return {d} if d else set()


def _instructions(db: Session, user: User) -> list[Task]:
    # See every instruction for the department(s) this login runs, plus anything
    # assigned directly to this user — not only unassigned tasks, so a second
    # manager in the same department sees the same list.
    depts = _my_depts(user)
    return (db.query(Task).filter(or_(Task.manager_user_id == user.id,
                                      Task.department.in_(depts)))
            .order_by(Task.id.desc()).all())


def pr_out(db: Session, r: PurchaseRequest) -> dict:
    po = db.query(PurchaseOrder).filter(PurchaseOrder.purchase_request_id == r.id).order_by(PurchaseOrder.id.desc()).first()
    order = db.get(Order, r.order_id) if r.order_id else None
    return {
        "id": r.id, "pr_no": r.pr_no, "yarn_type": r.yarn_type, "colour": r.colour,
        "quantity_kg": _f(r.quantity_kg), "required_date": _iso(r.required_date), "reason": r.reason,
        "source": r.source, "task_id": r.task_id, "order_no": order.order_no if order else None,
        "status": r.status, "requested_by": _user_name(db, r.requested_by_user_id),
        "decided_by": _user_name(db, r.decided_by_user_id), "decided_at": _iso(r.decided_at),
        "decision_note": r.decision_note, "created_at": _iso(r.created_at),
        "po_no": po.po_no if po else None,
    }


def po_out(db: Session, po: PurchaseOrder) -> dict:
    got = _po_received(db, po.id)
    qty = _f(po.quantity_kg)
    sub = qty * float(po.unit_cost or 0)
    tax = sub * float(po.tax_percent or 0) / 100
    pr = db.get(PurchaseRequest, po.purchase_request_id) if po.purchase_request_id else None
    pending = db.query(YarnReceipt).filter(YarnReceipt.purchase_order_id == po.id,
                                           YarnReceipt.status == "recorded").count()
    late = bool(po.expected_date and po.status in OPEN_PO and po.expected_date < date.today())
    return {
        "id": po.id, "po_no": po.po_no, "supplier_id": po.supplier_id, "supplier": _sup_name(db, po.supplier_id),
        "yarn_type": po.yarn_type, "colour": po.colour, "quantity_kg": qty, "unit_cost": _f(po.unit_cost),
        "tax_percent": _f(po.tax_percent), "subtotal": round(sub, 2), "tax": round(tax, 2), "total": round(sub + tax, 2),
        "expected_date": _iso(po.expected_date), "status": po.status, "late": late,
        "received_kg": got, "outstanding_kg": round(max(0.0, qty - got), 2), "receipts_waiting": pending,
        "pr_no": pr.pr_no if pr else None, "created_at": _iso(po.created_at),
    }


def receipt_out(db: Session, r: YarnReceipt) -> dict:
    po = db.get(PurchaseOrder, r.purchase_order_id) if r.purchase_order_id else None
    return {
        "id": r.id, "po_no": po.po_no if po else None, "purchase_order_id": r.purchase_order_id,
        "supplier": _sup_name(db, r.supplier_id), "yarn_type": r.yarn_type, "colour": r.colour,
        "quantity_kg": _f(r.quantity_kg), "damaged_kg": _f(r.damaged_kg),
        "accepted_kg": round(_f(r.quantity_kg) - _f(r.damaged_kg), 2), "batch_no": r.batch_no,
        "received_at": _iso(r.received_at), "status": r.status, "discrepancy": r.discrepancy,
        "discrepancy_note": r.discrepancy_note, "recorded_by": _user_name(db, r.recorded_by_user_id),
        "validated_by": _user_name(db, r.validated_by_user_id), "validated_at": _iso(r.validated_at),
    }


def low_stock_rows(db: Session) -> list[dict]:
    open_pr = defaultdict(float)
    for r in db.query(PurchaseRequest).filter(PurchaseRequest.status.in_(("pending", "approved", "ordered"))).all():
        open_pr[(_norm(r.yarn_type), _norm(r.colour))] += float(r.quantity_kg or 0)
    open_po = defaultdict(float)
    for po in db.query(PurchaseOrder).filter(PurchaseOrder.status.in_(OPEN_PO)).all():
        open_po[(_norm(po.yarn_type), _norm(po.colour))] += max(0.0, float(po.quantity_kg) - _po_received(db, po.id))
    out = []
    for s in stock_rows(db):
        if not s["low"]:
            continue
        lvl = s["reorder_level_kg"] or settings.default_reorder_level_kg
        key = (_norm(s["yarn_type"]), _norm(s["colour"]))
        required = round(max(0.0, lvl - s["available_kg"]), 2)
        coming = round(open_pr[key] + open_po[key], 2)
        # Refill to twice the minimum level, less what is already on its way.
        suggested = round(max(0.0, 2 * lvl - s["available_kg"] - coming), 2)
        out.append({**s, "minimum_kg": lvl, "required_kg": required, "on_order_kg": coming,
                    "suggested_kg": suggested})
    return out


def requirements(db: Session) -> list[dict]:
    stock_by_colour = defaultdict(float)
    for s in db.query(YarnStock).all():
        stock_by_colour[_norm(s.colour)] += float(s.quantity_kg or 0)
    left = dict(stock_by_colour)
    rows = []
    orders = (db.query(Order).filter(Order.status.in_(ACTIVE + UPCOMING))
              .order_by(Order.deadline.is_(None), Order.deadline, Order.id).all())
    # Confirmed work takes yarn first, then orders still being decided.
    orders.sort(key=lambda o: 0 if o.status in ACTIVE else 1)
    for o in orders:
        need = round(_order_need_left(db, o), 2)
        have = left.get(_norm(o.colour), 0.0)
        covered = min(have, need)
        left[_norm(o.colour)] = have - covered
        short = round(need - covered, 2)
        days = (o.deadline - date.today()).days if o.deadline else None
        rows.append({
            "order_id": o.id, "order_no": o.order_no, "buyer": o.buyer.name if o.buyer else "",
            "fabric": f"{o.fabric_type} {o.colour}", "colour": o.colour, "status": o.status,
            "confirmed": o.status in ACTIVE, "deadline": _iso(o.deadline), "days_left": days,
            "need_kg": need, "covered_kg": round(covered, 2), "short_kg": short,
            "risk": "short" if short > 0 and o.status in ACTIVE else ("watch" if short > 0 else "ok"),
            "delay_risk": bool(short > 0 and days is not None and days <= 10 and o.status in ACTIVE),
        })
    return rows


def _next_no(db: Session, model, prefix: str, start: int) -> str:
    n = db.query(func.count(model.id)).scalar() or 0
    return f"{prefix}-{start + n}"


def _notify(db: Session, title: str, body: str, kind: str, me: User, to_role: str | None = None,
            to_user_id: int | None = None) -> None:
    db.add(Notification(to_role=to_role, to_user_id=to_user_id, kind=kind, title=title[:200],
                        body=body, from_user_name=me.name))


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@router.get("/overview")
def overview(user: User = Depends(get_current_user), _=Depends(require_resource("purchase_dashboard")),
             db: Session = Depends(get_db)):
    today = date.today()
    t0 = datetime.combine(today, datetime.min.time())
    stock = stock_rows(db)
    pos = db.query(PurchaseOrder).order_by(PurchaseOrder.id.desc()).all()
    receipts_today = (db.query(YarnReceipt).filter(YarnReceipt.received_at >= t0).all())
    recent = db.query(YarnReceipt).order_by(YarnReceipt.id.desc()).limit(6).all()
    tasks = [t for t in _instructions(db, user) if t.status != "completed"]
    by_colour = defaultdict(float)
    for s in stock:
        by_colour[s["colour"]] += s["quantity_kg"]
    moves = db.query(StockMovement).order_by(StockMovement.id.desc()).limit(8).all()
    return {
        "cards": {
            "suppliers": db.query(Supplier).filter(Supplier.is_active.isnot(False)).count(),
            "purchase_orders": len(pos),
            "pending_pos": sum(1 for p in pos if p.status in OPEN_PO),
            "stock_kg": round(sum(s["quantity_kg"] for s in stock), 2),
            "low_stock": sum(1 for s in stock if s["low"]),
            "receipts_today": len(receipts_today),
            "receipts_today_kg": round(sum(float(r.quantity_kg or 0) for r in receipts_today), 2),
        },
        "stock_by_colour": sorted(({"label": k, "value": round(v, 2)} for k, v in by_colour.items()), key=lambda x: -x["value"]),
        "pending_pos": [po_out(db, p) for p in pos if p.status in OPEN_PO][:6],
        "recent_receipts": [receipt_out(db, r) for r in recent],
        "low_stock": low_stock_rows(db)[:6],
        "requests_waiting": db.query(PurchaseRequest).filter(PurchaseRequest.status == "pending").count(),
        "approved_to_order": db.query(PurchaseRequest).filter(PurchaseRequest.status == "approved").count(),
        "receipts_to_validate": db.query(YarnReceipt).filter(YarnReceipt.status == "recorded").count(),
        "instructions": [{"id": t.id, "title": t.title, "priority": t.priority, "deadline": _iso(t.deadline),
                          "status": shown_status(t)} for t in tasks[:5]],
        "activity": [{"id": m.id, "at": _iso(m.at), "what": f"{m.yarn_type} {m.colour}", "change_kg": _f(m.change_kg),
                      "balance_kg": _f(m.balance_kg), "kind": m.kind, "reference": m.reference, "user": m.user_name}
                     for m in moves],
    }


# --------------------------------------------------------------------------- #
# Suppliers
# --------------------------------------------------------------------------- #
def supplier_out(db: Session, s: Supplier) -> dict:
    pos = db.query(PurchaseOrder).filter(PurchaseOrder.supplier_id == s.id).all()
    return {
        "id": s.id, "name": s.name, "contact_person": s.contact_person, "phone": s.phone, "email": s.email,
        "address": s.address, "yarn_types": s.yarn_types, "is_active": s.is_active is not False,
        "po_count": len(pos), "open_pos": sum(1 for p in pos if p.status in OPEN_PO),
        "ordered_kg": round(sum(float(p.quantity_kg or 0) for p in pos if p.status != "cancelled"), 2),
    }


class SupplierIn(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    contact_person: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=180)
    address: str | None = Field(default=None, max_length=500)
    yarn_types: str | None = Field(default=None, max_length=500)

    _n = field_validator("name")(classmethod(lambda cls, v: _strip_required(v)))

    @field_validator("email")
    @classmethod
    def _e(cls, v):
        v = (v or "").strip().lower()
        if v and ("@" not in v or "." not in v.split("@")[-1]):
            raise ValueError("enter a valid email")
        return v or None

    @field_validator("phone")
    @classmethod
    def _p(cls, v):
        v = (v or "").strip()
        if v and not all(c.isdigit() or c in "+- " for c in v):
            raise ValueError("phone may contain digits, spaces, + and - only")
        return v or None


@router.get("/suppliers")
def list_suppliers(q: str | None = None, status: str | None = None,
                   _=Depends(require_resource("suppliers_desk")), db: Session = Depends(get_db)):
    qry = db.query(Supplier)
    if q:
        like = f"%{q.strip()}%"
        qry = qry.filter(or_(Supplier.name.ilike(like), Supplier.yarn_types.ilike(like), Supplier.contact_person.ilike(like)))
    if status == "active":
        qry = qry.filter(Supplier.is_active.isnot(False))
    elif status == "inactive":
        qry = qry.filter(Supplier.is_active.is_(False))
    return [supplier_out(db, s) for s in qry.order_by(Supplier.name).all()]


@router.post("/suppliers", status_code=201)
def create_supplier(body: SupplierIn, _=Depends(require_resource("suppliers_desk")), db: Session = Depends(get_db)):
    if db.query(Supplier).filter(func.lower(Supplier.name) == body.name.lower()).first():
        raise HTTPException(409, f"A supplier named {body.name} already exists")
    s = Supplier(name=body.name, contact_person=_clean(body.contact_person, 120), phone=body.phone,
                 email=body.email, address=_clean(body.address, 500), yarn_types=_clean(body.yarn_types, 500),
                 is_active=True)
    db.add(s)
    db.commit()
    return supplier_out(db, s)


@router.put("/suppliers/{sid}")
def edit_supplier(sid: int, body: SupplierIn, _=Depends(require_resource("suppliers_desk")),
                  db: Session = Depends(get_db)):
    s = db.get(Supplier, sid)
    if s is None:
        raise HTTPException(404, "Supplier not found")
    if db.query(Supplier).filter(func.lower(Supplier.name) == body.name.lower(), Supplier.id != sid).first():
        raise HTTPException(409, f"A supplier named {body.name} already exists")
    s.name, s.contact_person, s.phone, s.email = body.name, _clean(body.contact_person, 120), body.phone, body.email
    s.address, s.yarn_types = _clean(body.address, 500), _clean(body.yarn_types, 500)
    db.commit()
    return supplier_out(db, s)


class ActiveIn(BaseModel):
    active: bool


@router.post("/suppliers/{sid}/active")
def supplier_active(sid: int, body: ActiveIn, _=Depends(require_resource("suppliers_desk")),
                    db: Session = Depends(get_db)):
    s = db.get(Supplier, sid)
    if s is None:
        raise HTTPException(404, "Supplier not found")
    s.is_active = body.active
    db.commit()
    return supplier_out(db, s)


@router.get("/suppliers/{sid}/history")
def supplier_history(sid: int, _=Depends(require_resource("suppliers_desk")), db: Session = Depends(get_db)):
    s = db.get(Supplier, sid)
    if s is None:
        raise HTTPException(404, "Supplier not found")
    pos = db.query(PurchaseOrder).filter(PurchaseOrder.supplier_id == sid).order_by(PurchaseOrder.id.desc()).all()
    recs = db.query(YarnReceipt).filter(YarnReceipt.supplier_id == sid).order_by(YarnReceipt.id.desc()).all()
    return {"supplier": supplier_out(db, s), "purchase_orders": [po_out(db, p) for p in pos],
            "receipts": [receipt_out(db, r) for r in recs]}


# --------------------------------------------------------------------------- #
# Inventory
# --------------------------------------------------------------------------- #
@router.get("/inventory")
def inventory(q: str | None = None, colour: str | None = None, low: bool = False,
              _=Depends(require_resource("stock")), db: Session = Depends(get_db)):
    rows = stock_rows(db)
    if q:
        s = q.strip().lower()
        rows = [r for r in rows if s in f"{r['yarn_type']} {r['colour']} {r['location'] or ''}".lower()]
    if colour:
        rows = [r for r in rows if _norm(r["colour"]) == _norm(colour)]
    if low:
        rows = [r for r in rows if r["low"]]
    colours = sorted({s.colour for s in db.query(YarnStock).all()})
    return {"rows": rows, "colours": colours,
            "totals": {"kg": round(sum(r["quantity_kg"] for r in rows), 2),
                       "reserved": round(sum(r["reserved_kg"] for r in rows), 2),
                       "available": round(sum(r["available_kg"] for r in rows), 2)},
            "reserved_note": "Reserved = yarn still needed by confirmed and in-production orders of the same colour."}


class StockEdit(BaseModel):
    location: str | None = Field(default=None, max_length=80)
    reorder_level_kg: float = Field(ge=0, le=1_000_000)


@router.put("/inventory/{stock_id}")
def edit_stock(stock_id: int, body: StockEdit, _=Depends(require_resource("stock")), db: Session = Depends(get_db)):
    """Storage location and minimum-stock level only. Quantities change only
    through validated receipts (or the owner's audited correction)."""
    s = db.get(YarnStock, stock_id)
    if s is None:
        raise HTTPException(404, "Stock line not found")
    s.location = _clean(body.location, 80)
    s.reorder_level_kg = body.reorder_level_kg
    db.commit()
    return next(r for r in stock_rows(db) if r["id"] == stock_id)


@router.get("/movements")
def movements(stock_id: int | None = None, limit: int = Query(100, ge=1, le=500),
              _=Depends(require_resource("stock")), db: Session = Depends(get_db)):
    q = db.query(StockMovement)
    if stock_id:
        s = db.get(YarnStock, stock_id)
        if s is None:
            raise HTTPException(404, "Stock line not found")
        q = q.filter(func.lower(StockMovement.yarn_type) == s.yarn_type.lower(),
                     func.lower(StockMovement.colour) == s.colour.lower())
    rows = q.order_by(StockMovement.id.desc()).limit(limit).all()
    return [{"id": m.id, "at": _iso(m.at), "yarn_type": m.yarn_type, "colour": m.colour, "change_kg": _f(m.change_kg),
             "balance_kg": _f(m.balance_kg), "kind": m.kind, "reference": m.reference, "user": m.user_name}
            for m in rows]


# --------------------------------------------------------------------------- #
# Purchase requests
# --------------------------------------------------------------------------- #
class RequestIn(BaseModel):
    yarn_type: str = Field(min_length=1, max_length=80)
    colour: str = Field(min_length=1, max_length=60)
    quantity_kg: float = Field(gt=0, le=1_000_000)
    required_date: date | None = None
    reason: str | None = Field(default=None, max_length=1000)
    source: str = "manual"
    task_id: int | None = None
    order_id: int | None = None

    _s = field_validator("yarn_type", "colour")(classmethod(lambda cls, v: _strip_required(v)))

    @field_validator("source")
    @classmethod
    def _src(cls, v):
        if v not in ("manual", "low_stock", "instruction", "order"):
            raise ValueError("unknown source")
        return v

    @field_validator("required_date")
    @classmethod
    def _rd(cls, v):
        if v is not None and v < date.today():
            raise ValueError("required date cannot be in the past")
        return v


@router.get("/requests")
def list_requests(status: str | None = None, user: User = Depends(get_current_user),
                  _=Depends(require_resource("purchase_requests")), db: Session = Depends(get_db)):
    q = db.query(PurchaseRequest)
    if status:
        q = q.filter(PurchaseRequest.status == status)
    tasks = _instructions(db, user)
    limit = float(get_setting(db, "purchase_auto_approve_kg") or 0)
    return {
        "requests": [pr_out(db, r) for r in q.order_by(PurchaseRequest.id.desc()).all()],
        "instructions": [{"id": t.id, "title": t.title, "details": t.details, "priority": t.priority,
                          "deadline": _iso(t.deadline), "status": shown_status(t), "department": t.department,
                          "order_id": t.order_id,
                          "has_request": db.query(PurchaseRequest).filter(PurchaseRequest.task_id == t.id).count() > 0}
                         for t in tasks if t.status != "completed"],
        "workflow": ("Every request needs Supermanager approval." if limit <= 0 else
                     f"Requests up to {limit:,.0f} kg are approved automatically; larger ones need Supermanager approval."),
    }


@router.post("/requests", status_code=201)
def create_request(body: RequestIn, user: User = Depends(get_current_user),
                   _=Depends(require_resource("purchase_requests")), db: Session = Depends(get_db)):
    if body.task_id is not None:
        t = db.get(Task, body.task_id)
        if t is None:
            raise HTTPException(400, "Unknown instruction")
        if t.status == "pending":
            t.status = "in_progress"
            t.updated_at = datetime.utcnow()
    if body.order_id is not None and db.get(Order, body.order_id) is None:
        raise HTTPException(400, "Unknown order")
    r = PurchaseRequest(pr_no=_next_no(db, PurchaseRequest, "PR", 5001), yarn_type=body.yarn_type,
                        colour=body.colour, quantity_kg=body.quantity_kg, required_date=body.required_date,
                        reason=_clean(body.reason, 1000), source=body.source, task_id=body.task_id,
                        order_id=body.order_id, status="pending", requested_by_user_id=user.id)
    db.add(r)
    limit = float(get_setting(db, "purchase_auto_approve_kg") or 0)
    if limit > 0 and body.quantity_kg <= limit:
        r.status = "approved"
        r.decision_note = f"Approved automatically (up to {limit:,.0f} kg)."
        r.decided_at = datetime.utcnow()
    else:
        _notify(db, f"Purchase request {r.pr_no} needs approval",
                f"{body.quantity_kg:,.0f} kg {body.yarn_type} {body.colour}" + (f" · {r.reason}" if r.reason else ""),
                "approval_needed", user, to_role=rbac.ROLE_MANAGER)
    db.commit()
    return pr_out(db, r)


@router.post("/requests/{rid}/cancel")
def cancel_request(rid: int, _=Depends(require_resource("purchase_requests")), db: Session = Depends(get_db)):
    r = db.get(PurchaseRequest, rid)
    if r is None:
        raise HTTPException(404, "Request not found")
    if r.status not in ("pending", "approved"):
        raise HTTPException(409, f"Request is {r.status} and can no longer be cancelled")
    r.status = "cancelled"
    db.commit()
    return pr_out(db, r)


# --------------------------------------------------------------------------- #
# Purchase orders
# --------------------------------------------------------------------------- #
class POIn(BaseModel):
    purchase_request_id: int
    supplier_id: int
    quantity_kg: float = Field(gt=0, le=1_000_000)
    unit_cost: float = Field(gt=0, le=100_000)
    tax_percent: float = Field(default=0, ge=0, le=40)
    expected_date: date

    @field_validator("expected_date")
    @classmethod
    def _ed(cls, v):
        if v < date.today():
            raise ValueError("delivery date cannot be in the past")
        return v


@router.get("/orders")
def list_pos(status: str | None = None, _=Depends(require_resource("purchase")), db: Session = Depends(get_db)):
    q = db.query(PurchaseOrder)
    if status == "open":
        q = q.filter(PurchaseOrder.status.in_(OPEN_PO))
    elif status:
        q = q.filter(PurchaseOrder.status == status)
    approved = db.query(PurchaseRequest).filter(PurchaseRequest.status == "approved").order_by(PurchaseRequest.id).all()
    sups = db.query(Supplier).filter(Supplier.is_active.isnot(False)).order_by(Supplier.name).all()
    return {"orders": [po_out(db, p) for p in q.order_by(PurchaseOrder.id.desc()).all()],
            "approved_requests": [pr_out(db, r) for r in approved],
            "suppliers": [{"id": s.id, "name": s.name, "yarn_types": s.yarn_types} for s in sups]}


@router.post("/orders", status_code=201)
def create_po(body: POIn, user: User = Depends(get_current_user), _=Depends(require_resource("purchase")),
              db: Session = Depends(get_db)):
    """Only from an APPROVED request, so no purchase is committed without the
    approval the workflow requires. Quantity may not exceed the request by >10%."""
    r = db.get(PurchaseRequest, body.purchase_request_id)
    if r is None:
        raise HTTPException(400, "Unknown purchase request")
    if r.status != "approved":
        raise HTTPException(409, f"{r.pr_no} is {r.status} — a purchase order needs an approved request")
    if body.quantity_kg > float(r.quantity_kg) * 1.10 + 1e-6:
        raise HTTPException(400, f"Quantity is more than the approved {float(r.quantity_kg):,.0f} kg (+10%)")
    s = db.get(Supplier, body.supplier_id)
    if s is None or s.is_active is False:
        raise HTTPException(400, "Choose an active supplier")
    po = PurchaseOrder(supplier_id=s.id, po_no=_next_no(db, PurchaseOrder, "PO", 1001), yarn_type=r.yarn_type,
                       colour=r.colour, quantity_kg=body.quantity_kg, unit_cost=body.unit_cost,
                       tax_percent=body.tax_percent, expected_date=body.expected_date, status="raised",
                       purchase_request_id=r.id, created_by_user_id=user.id)
    db.add(po)
    r.status = "ordered"
    db.commit()
    return po_out(db, po)


@router.post("/orders/{po_id}/cancel")
def cancel_po(po_id: int, _=Depends(require_resource("purchase")), db: Session = Depends(get_db)):
    po = db.get(PurchaseOrder, po_id)
    if po is None:
        raise HTTPException(404, "Purchase order not found")
    if po.status != "raised" or db.query(YarnReceipt).filter(YarnReceipt.purchase_order_id == po.id).count():
        raise HTTPException(409, "Only a purchase order with nothing received can be cancelled")
    po.status = "cancelled"
    r = db.get(PurchaseRequest, po.purchase_request_id) if po.purchase_request_id else None
    if r is not None and r.status == "ordered":
        r.status = "approved"  # can be ordered again from another supplier
    db.commit()
    return po_out(db, po)


# --------------------------------------------------------------------------- #
# Receiving
# --------------------------------------------------------------------------- #
class ReceiptIn(BaseModel):
    purchase_order_id: int | None = None
    supplier_id: int | None = None
    yarn_type: str = Field(min_length=1, max_length=80)
    colour: str = Field(min_length=1, max_length=60)
    quantity_kg: float = Field(gt=0, le=1_000_000)
    damaged_kg: float = Field(default=0, ge=0)
    batch_no: str = Field(min_length=1, max_length=60)
    received_date: date
    note: str | None = Field(default=None, max_length=1000)

    _s = field_validator("yarn_type", "colour", "batch_no")(classmethod(lambda cls, v: _strip_required(v)))

    @field_validator("received_date")
    @classmethod
    def _rd(cls, v):
        if v > date.today():
            raise ValueError("received date cannot be in the future")
        return v


@router.get("/receipts")
def list_receipts(status: str | None = None, _=Depends(require_resource("yarn")), db: Session = Depends(get_db)):
    q = db.query(YarnReceipt)
    if status:
        q = q.filter(YarnReceipt.status == status)
    open_pos = db.query(PurchaseOrder).filter(PurchaseOrder.status.in_(OPEN_PO)).order_by(PurchaseOrder.id).all()
    sups = db.query(Supplier).filter(Supplier.is_active.isnot(False)).order_by(Supplier.name).all()
    return {"receipts": [receipt_out(db, r) for r in q.order_by(YarnReceipt.id.desc()).limit(200).all()],
            "open_pos": [po_out(db, p) for p in open_pos],
            "suppliers": [{"id": s.id, "name": s.name} for s in sups]}


@router.post("/receipts", status_code=201)
def record_receipt(body: ReceiptIn, user: User = Depends(get_current_user), _=Depends(require_resource("yarn")),
                   db: Session = Depends(get_db)):
    """Record what actually arrived. Stock is NOT changed until validated."""
    if body.damaged_kg > body.quantity_kg:
        raise HTTPException(400, "Damaged quantity cannot be more than the quantity received")
    flags, notes = [], []
    supplier_id = body.supplier_id
    po = None
    if body.purchase_order_id is not None:
        po = db.get(PurchaseOrder, body.purchase_order_id)
        if po is None:
            raise HTTPException(400, "Unknown purchase order")
        if po.status not in OPEN_PO:
            raise HTTPException(409, f"{po.po_no} is {po.status} — nothing more is expected on it")
        supplier_id = po.supplier_id
        if _norm(po.yarn_type) != _norm(body.yarn_type) or _norm(po.colour) != _norm(body.colour):
            flags.append("mismatch")
            notes.append(f"PO is for {po.yarn_type} {po.colour}")
        outstanding = max(0.0, float(po.quantity_kg) - _po_received(db, po.id))
        pending = sum(float(r.quantity_kg or 0) - float(r.damaged_kg or 0) for r in db.query(YarnReceipt).filter(
            YarnReceipt.purchase_order_id == po.id, YarnReceipt.status == "recorded").all())
        due = max(0.0, outstanding - pending)
        good = body.quantity_kg - body.damaged_kg
        if good < due - 0.01:
            flags.append("shortage")
            notes.append(f"{due - good:,.2f} kg short of the {due:,.2f} kg still due")
        elif good > due + 0.01:
            flags.append("excess")
            notes.append(f"{good - due:,.2f} kg more than the {due:,.2f} kg still due")
    elif supplier_id is not None and db.get(Supplier, supplier_id) is None:
        raise HTTPException(400, "Unknown supplier")
    if body.damaged_kg > 0:
        flags.append("damaged")
        notes.append(f"{body.damaged_kg:,.2f} kg damaged")
    if body.note:
        notes.append(body.note.strip())
    r = YarnReceipt(supplier_id=supplier_id, purchase_order_id=po.id if po else None,
                    yarn_type=body.yarn_type, colour=body.colour, quantity_kg=body.quantity_kg,
                    unit_cost=float(po.unit_cost) if po else 0, damaged_kg=body.damaged_kg,
                    batch_no=body.batch_no, received_at=datetime.combine(body.received_date, datetime.now().time()),
                    status="recorded", discrepancy=",".join(flags) or None,
                    discrepancy_note=" · ".join(notes) or None, recorded_by_user_id=user.id)
    db.add(r)
    db.commit()
    return receipt_out(db, r)


class ValidateIn(BaseModel):
    accept: bool
    note: str | None = Field(default=None, max_length=1000)


@router.post("/receipts/{rid}/validate")
def validate_receipt(rid: int, body: ValidateIn, user: User = Depends(get_current_user),
                     _=Depends(require_resource("yarn")), db: Session = Depends(get_db)):
    """Accept → stock goes up by (received − damaged), the PO becomes partial or
    received. Reject → nothing enters stock; the record stays for the audit."""
    r = db.get(YarnReceipt, rid)
    if r is None:
        raise HTTPException(404, "Receipt not found")
    if r.status != "recorded":
        raise HTTPException(409, f"Receipt is already {r.status}")
    if not body.accept and not (body.note or "").strip():
        raise HTTPException(400, "Give a reason for rejecting the delivery")
    if body.note:
        r.discrepancy_note = " · ".join(x for x in (r.discrepancy_note, f"Review: {body.note.strip()}") if x)
    r.validated_by_user_id, r.validated_at = user.id, datetime.utcnow()
    if not body.accept:
        r.status = "rejected"
        db.commit()
        return receipt_out(db, r)

    good = float(r.quantity_kg) - float(r.damaged_kg or 0)
    stock = (db.query(YarnStock).filter(func.lower(YarnStock.yarn_type) == r.yarn_type.lower(),
                                        func.lower(YarnStock.colour) == r.colour.lower()).first())
    po = db.get(PurchaseOrder, r.purchase_order_id) if r.purchase_order_id else None
    db.info["stock_ref"] = {"kind": "receipt", "reference": f"Receipt #{r.id}" + (f" · {po.po_no}" if po else "")
                            + (f" · batch {r.batch_no}" if r.batch_no else "")}
    if stock is None:
        stock = YarnStock(yarn_type=r.yarn_type, colour=r.colour, quantity_kg=0,
                          reorder_level_kg=settings.default_reorder_level_kg, unit_cost=r.unit_cost or 0)
        db.add(stock)
        db.flush()
    stock.quantity_kg = float(stock.quantity_kg) + good
    if r.unit_cost:
        stock.unit_cost = r.unit_cost
    stock.updated_at = datetime.utcnow()
    r.yarn_stock_id = stock.id
    r.status = "validated"
    db.flush()
    if po is not None:
        got = _po_received(db, po.id)
        po.status = "received" if got >= float(po.quantity_kg) * 0.98 else "partial"
        pr = db.get(PurchaseRequest, po.purchase_request_id) if po.purchase_request_id else None
        if pr is not None and po.status == "received":
            pr.status = "received"
            if pr.task_id:
                t = db.get(Task, pr.task_id)
                if t is not None and t.status != "completed":
                    t.status, t.updated_at = "completed", datetime.utcnow()
    db.commit()
    db.info.pop("stock_ref", None)
    return receipt_out(db, r)


# --------------------------------------------------------------------------- #
# Low stock, production requirements
# --------------------------------------------------------------------------- #
@router.get("/low-stock")
def low_stock(_=Depends(require_resource("low_stock")), db: Session = Depends(get_db)):
    return {"rows": low_stock_rows(db),
            "rule": "Suggested reorder fills the line to twice its minimum level, less what is already requested or on order."}


@router.get("/requirements")
def material_requirements(_=Depends(require_resource("material_requirements")), db: Session = Depends(get_db)):
    rows = requirements(db)
    return {"rows": rows,
            "totals": {"need_kg": round(sum(r["need_kg"] for r in rows if r["confirmed"]), 2),
                       "short_kg": round(sum(r["short_kg"] for r in rows if r["confirmed"]), 2),
                       "orders_short": sum(1 for r in rows if r["risk"] == "short"),
                       "delay_risk": sum(1 for r in rows if r["delay_risk"])},
            "basis": f"Yarn need = metres × {settings.yarn_kg_per_meter} kg/m, less yarn already spun. "
                     "Stock is matched by colour; confirmed orders are served first."}


class ShareIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


@router.post("/requirements/share")
def share_requirements(body: ShareIn, user: User = Depends(get_current_user),
                       _=Depends(require_resource("material_requirements")), db: Session = Depends(get_db)):
    rows = [r for r in requirements(db) if r["confirmed"]]
    short = [r for r in rows if r["short_kg"] > 0]
    text = ("All confirmed orders have enough yarn." if not short else
            "Short: " + "; ".join(f"{r['order_no']} {r['colour']} {r['short_kg']:,.0f} kg" for r in short))
    if body.note:
        text += f" · Note: {body.note.strip()}"
    for role in (rbac.ROLE_MANAGER, rbac.ROLE_PRODUCTION_MANAGER):
        _notify(db, "Material availability update", text, "availability", user, to_role=role)
    db.commit()
    return {"sent_to": ["Supermanager", "Production manager"], "message": text}


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
@router.get("/reports")
def reports(start: date | None = None, end: date | None = None, _=Depends(require_resource("purchase_reports")),
            db: Session = Depends(get_db)):
    end = end or date.today()
    start = start or (end - timedelta(days=89))
    if end < start:
        raise HTTPException(400, "end must be on or after start")
    s_dt, e_dt = datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.max.time())
    pos = db.query(PurchaseOrder).filter(PurchaseOrder.created_at.between(s_dt, e_dt)).order_by(PurchaseOrder.id.desc()).all()
    history = [po_out(db, p) for p in pos]

    # Supplier performance: delivered vs ordered, on-time against expected date.
    perf = {}
    for p in db.query(PurchaseOrder).filter(PurchaseOrder.status != "cancelled").all():
        d = perf.setdefault(p.supplier_id, {"supplier": _sup_name(db, p.supplier_id), "orders": 0, "ordered_kg": 0.0,
                                            "received_kg": 0.0, "with_date": 0, "on_time": 0, "delay_days": 0.0,
                                            "damaged_kg": 0.0, "late_open": 0})
        d["orders"] += 1
        d["ordered_kg"] += float(p.quantity_kg or 0)
        d["received_kg"] += _po_received(db, p.id)
        recs = db.query(YarnReceipt).filter(YarnReceipt.purchase_order_id == p.id, YarnReceipt.status == "validated").all()
        d["damaged_kg"] += sum(float(r.damaged_kg or 0) for r in recs)
        if p.expected_date and recs:
            last = max(r.received_at for r in recs).date()
            d["with_date"] += 1
            if last <= p.expected_date:
                d["on_time"] += 1
            else:
                d["delay_days"] += (last - p.expected_date).days
        if p.expected_date and p.status in OPEN_PO and p.expected_date < date.today():
            d["late_open"] += 1
    suppliers = []
    for d in perf.values():
        late = d["with_date"] - d["on_time"]
        suppliers.append({**{k: (round(v, 2) if isinstance(v, float) else v) for k, v in d.items()},
                          "fill_rate": round(d["received_kg"] / d["ordered_kg"] * 100) if d["ordered_kg"] else 0,
                          "on_time_rate": round(d["on_time"] / d["with_date"] * 100) if d["with_date"] else None,
                          "avg_delay_days": round(d["delay_days"] / late, 1) if late else 0})
    suppliers.sort(key=lambda x: x["supplier"])

    # Consumption: yarn issued to production (estimate from spun metres) and
    # stock issues recorded as movements.
    cons = defaultdict(float)
    for o_colour, metres in (db.query(Order.colour, func.sum(ProductionLog.output_meters))
                             .join(ProductionLog, ProductionLog.order_id == Order.id)
                             .filter(ProductionLog.stage == "spinning", ProductionLog.log_date.between(start, end))
                             .group_by(Order.colour).all()):
        cons[o_colour] += float(metres or 0) * settings.yarn_kg_per_meter
    issued = defaultdict(float)
    for m in db.query(StockMovement).filter(StockMovement.at.between(s_dt, e_dt), StockMovement.change_kg < 0).all():
        issued[f"{m.yarn_type} {m.colour}"] += -float(m.change_kg)

    stock = stock_rows(db)
    monthly = defaultdict(lambda: {"orders": 0, "kg": 0.0, "value": 0.0})
    for p in history:
        if p["status"] == "cancelled":
            continue
        k = (p["created_at"] or "")[:7]
        monthly[k]["orders"] += 1
        monthly[k]["kg"] += p["quantity_kg"]
        monthly[k]["value"] += p["total"]
    return {
        "start": start.isoformat(), "end": end.isoformat(),
        "history": history,
        "suppliers": suppliers,
        "consumption": [{"colour": k, "kg": round(v, 2)} for k, v in sorted(cons.items())],
        "issued": [{"item": k, "kg": round(v, 2)} for k, v in sorted(issued.items())],
        "consumption_basis": f"Spinning output × {settings.yarn_kg_per_meter} kg/m (estimate).",
        "valuation": {"rows": [{"item": f"{s['yarn_type']} {s['colour']}", "kg": s["quantity_kg"], "rate": s["unit_cost"],
                                "value": s["value"], "has_cost": s["unit_cost"] > 0} for s in stock],
                      "total": round(sum(s["value"] for s in stock), 2),
                      "missing_cost": sum(1 for s in stock if s["unit_cost"] <= 0)},
        "monthly": [{"month": k, "orders": v["orders"], "kg": round(v["kg"], 2), "value": round(v["value"], 2)}
                    for k, v in sorted(monthly.items(), reverse=True)],
    }


# --------------------------------------------------------------------------- #
# Notifications
# --------------------------------------------------------------------------- #
@router.get("/notifications")
def notifications(user: User = Depends(get_current_user), _=Depends(require_resource("purchase_notifications")),
                  db: Session = Depends(get_db)):
    today = date.today()
    items = []
    for t in _instructions(db, user):
        if t.status != "completed":
            items.append({"kind": "instruction", "level": "urgent" if t.priority == "urgent" else "info",
                          "title": f"Instruction: {t.title}", "detail": (t.details or "") + (f" · due {t.deadline.strftime('%d/%m/%Y')}" if t.deadline else ""),
                          "at": _iso(t.created_at), "page": "/app/purchase-requests"})
    stored = (db.query(Notification).filter(or_(Notification.to_user_id == user.id, Notification.to_role == user.role.name))
              .order_by(Notification.id.desc()).limit(50).all())
    for n in stored:
        items.append({"kind": n.kind, "level": "warning" if n.kind == "rejection" else "info", "title": n.title,
                      "detail": (n.body or "") + (f" — {n.from_user_name}" if n.from_user_name else ""),
                      "at": _iso(n.created_at), "page": "/app/purchase-requests", "unread": n.read_at is None})
    for p in db.query(PurchaseOrder).filter(PurchaseOrder.status.in_(OPEN_PO), PurchaseOrder.expected_date.isnot(None)).all():
        days = (p.expected_date - today).days
        if days < 0:
            items.append({"kind": "delivery", "level": "warning", "title": f"{p.po_no} is overdue",
                          "detail": f"{_sup_name(db, p.supplier_id)} · expected {p.expected_date.strftime('%d/%m/%Y')}",
                          "at": None, "page": "/app/purchase"})
        elif days <= 7:
            items.append({"kind": "delivery", "level": "info", "title": f"{p.po_no} expected in {days} day{'s' if days != 1 else ''}",
                          "detail": f"{_sup_name(db, p.supplier_id)} · {float(p.quantity_kg):,.0f} kg {p.yarn_type} {p.colour}",
                          "at": None, "page": "/app/yarn"})
    for s in low_stock_rows(db):
        items.append({"kind": "low_stock", "level": "warning", "title": f"Low stock: {s['yarn_type']} {s['colour']}",
                      "detail": f"{s['available_kg']:,.0f} kg available · minimum {s['minimum_kg']:,.0f} kg",
                      "at": None, "page": "/app/low-stock"})
    for r in db.query(YarnReceipt).filter(YarnReceipt.discrepancy.isnot(None), YarnReceipt.status == "recorded").all():
        items.append({"kind": "discrepancy", "level": "warning", "title": f"Receipt #{r.id} flagged: {r.discrepancy.replace(',', ', ')}",
                      "detail": r.discrepancy_note or "", "at": _iso(r.received_at), "page": "/app/yarn"})
    return {"items": items, "unread": sum(1 for i in items if i.get("unread"))}


@router.post("/notifications/read")
def mark_read(user: User = Depends(get_current_user), _=Depends(require_resource("purchase_notifications")),
              db: Session = Depends(get_db)):
    now = datetime.utcnow()
    for n in db.query(Notification).filter(or_(Notification.to_user_id == user.id, Notification.to_role == user.role.name),
                                           Notification.read_at.is_(None)).all():
        n.read_at = now
    db.commit()
    return {"ok": True}

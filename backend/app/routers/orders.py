"""Orders module — scene 1 (order comes in) and the yarn-sufficiency check.

Endpoints (owner only — RBAC resource "orders"):
  GET    /api/orders                 list + status filter + search
  POST   /api/orders                 create a new order (status=draft)
  GET    /api/orders/{id}            order detail
  GET    /api/orders/{id}/check-yarn yarn enough / short by X
  POST   /api/orders/{id}/confirm    set status=confirmed (ready for production)

Yarn requirement is derived from quantity (metres) × YARN_KG_PER_METER, matched by
fabric colour against yarn stock of the same colour.
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import require_resource
from app.models import Buyer, Order, OrderItem, YarnStock

settings = get_settings()
router = APIRouter(prefix="/api/orders", tags=["orders"])

# Any order in these states counts as "active" when reserving stock for the check.
_CONFIRMED_STATES = ("confirmed", "in_production", "in_quality", "ready_to_ship")


# --------------------------- schemas --------------------------- #
class OrderCreate(BaseModel):
    buyer_id: int
    fabric_type: str = Field(min_length=1, max_length=80)
    colour: str = Field(min_length=1, max_length=60)
    quantity_meters: float = Field(gt=0)
    unit_price: float = Field(ge=0)
    deadline: date | None = None
    yarn_type: str | None = None  # which yarn feeds this order (defaults by colour)

    @field_validator("fabric_type", "colour")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class OrderOut(BaseModel):
    id: int
    order_no: str
    buyer_id: int
    buyer_name: str
    fabric_type: str
    colour: str
    quantity_meters: float
    unit: str
    unit_price: float
    deadline: date | None
    status: str
    created_at: datetime


class CheckYarnOut(BaseModel):
    order_id: int
    colour: str
    required_kg: float
    available_kg: float
    enough: bool
    short_by_kg: float
    message: str
    suggested_purchase_kg: float


def _order_out(o: Order) -> OrderOut:
    return OrderOut(
        id=o.id,
        order_no=o.order_no,
        buyer_id=o.buyer_id,
        buyer_name=o.buyer.name if o.buyer else "",
        fabric_type=o.fabric_type,
        colour=o.colour,
        quantity_meters=float(o.quantity_meters),
        unit=o.unit,
        unit_price=float(o.unit_price),
        deadline=o.deadline,
        status=o.status,
        created_at=o.created_at,
    )


def _next_order_no(db: Session) -> str:
    n = db.query(func.count(Order.id)).scalar() or 0
    return f"ORD-{2001 + n}"


def _required_kg(quantity_meters: float) -> float:
    return round(float(quantity_meters) * settings.yarn_kg_per_meter, 2)


def _available_kg(db: Session, colour: str, yarn_type: str | None) -> float:
    q = db.query(func.coalesce(func.sum(YarnStock.quantity_kg), 0)).filter(
        func.lower(YarnStock.colour) == colour.lower()
    )
    if yarn_type:
        q = q.filter(func.lower(YarnStock.yarn_type) == yarn_type.lower())
    return float(q.scalar() or 0)


# --------------------------- endpoints --------------------------- #
@router.get("", response_model=list[OrderOut])
def list_orders(
    status: str | None = Query(None),
    q: str | None = Query(None, description="search order no / fabric / colour"),
    _=Depends(require_resource("orders")),
    db: Session = Depends(get_db),
):
    query = db.query(Order)
    if status:
        query = query.filter(Order.status == status)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Order.order_no.ilike(like),
                Order.fabric_type.ilike(like),
                Order.colour.ilike(like),
            )
        )
    orders = query.order_by(Order.id.desc()).all()
    return [_order_out(o) for o in orders]


@router.post("", response_model=OrderOut, status_code=201)
def create_order(
    body: OrderCreate,
    _=Depends(require_resource("orders")),
    db: Session = Depends(get_db),
):
    buyer = db.query(Buyer).filter(Buyer.id == body.buyer_id).first()
    if buyer is None:
        raise HTTPException(status_code=400, detail="Unknown buyer")

    order = Order(
        order_no=_next_order_no(db),
        buyer_id=body.buyer_id,
        fabric_type=body.fabric_type,
        colour=body.colour,
        quantity_meters=body.quantity_meters,
        unit="meters",
        unit_price=body.unit_price,
        deadline=body.deadline,
        status="draft",
    )
    db.add(order)
    db.flush()

    # Record the yarn requirement as an order item (kg).
    db.add(
        OrderItem(
            order_id=order.id,
            yarn_type=body.yarn_type or f"{body.fabric_type} yarn",
            colour=body.colour,
            required_qty_kg=_required_kg(body.quantity_meters),
            allocated_qty_kg=0,
        )
    )
    db.commit()
    db.refresh(order)
    return _order_out(order)


class BuyerOut(BaseModel):
    id: int
    name: str


@router.get("/_meta/buyers", response_model=list[BuyerOut])
def list_buyers(
    _=Depends(require_resource("orders")),
    db: Session = Depends(get_db),
):
    """Buyers for the New order form (owner only)."""
    rows = db.query(Buyer).order_by(Buyer.name).all()
    return [BuyerOut(id=b.id, name=b.name) for b in rows]


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: int,
    _=Depends(require_resource("orders")),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return _order_out(order)


@router.get("/{order_id}/check-yarn", response_model=CheckYarnOut)
def check_yarn(
    order_id: int,
    _=Depends(require_resource("orders")),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    item = (
        db.query(OrderItem).filter(OrderItem.order_id == order.id).first()
    )
    yarn_type = item.yarn_type if item else None
    required = (
        float(item.required_qty_kg) if item else _required_kg(order.quantity_meters)
    )
    available = _available_kg(db, order.colour, yarn_type)
    enough = available >= required
    short = round(max(0.0, required - available), 2)

    if enough:
        msg = f"Enough yarn: {available:.2f} kg available for {required:.2f} kg needed."
    else:
        msg = (
            f"Short by {short:.2f} kg — only {available:.2f} kg of {order.colour} "
            f"yarn in stock for {required:.2f} kg needed. Raise a purchase."
        )

    return CheckYarnOut(
        order_id=order.id,
        colour=order.colour,
        required_kg=required,
        available_kg=round(available, 2),
        enough=enough,
        short_by_kg=short,
        message=msg,
        suggested_purchase_kg=short,
    )


@router.post("/{order_id}/confirm", response_model=OrderOut)
def confirm_order(
    order_id: int,
    _=Depends(require_resource("orders")),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status not in ("draft", "confirmed"):
        raise HTTPException(
            status_code=409,
            detail=f"Order is '{order.status}' and cannot be confirmed",
        )
    order.status = "confirmed"
    db.commit()
    db.refresh(order)
    return _order_out(order)

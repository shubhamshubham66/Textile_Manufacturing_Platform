"""Yarn store module — scene 1 (yarn arrives) + stock + purchase.

Endpoints (store_manager — RBAC resources "yarn"/"stock"/"purchase"):
  POST /api/yarn/receipts     record a yarn receipt; stock updates automatically
  GET  /api/yarn/stock        live stock per type+colour with low-stock flag
  POST /api/yarn/purchase     raise a purchase order for a supplier (short yarn)
  GET  /api/yarn/purchase     list purchase orders
  GET  /api/yarn/suppliers    suppliers (for the receive/purchase forms)
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import require_resource
from app.models import (
    Order,
    PurchaseOrder,
    Supplier,
    YarnReceipt,
    YarnStock,
)

settings = get_settings()
router = APIRouter(prefix="/api/yarn", tags=["yarn"])


# --------------------------- schemas --------------------------- #
class ReceiptCreate(BaseModel):
    supplier_id: int | None = None
    yarn_type: str = Field(min_length=1, max_length=80)
    colour: str = Field(min_length=1, max_length=60)
    quantity_kg: float = Field(gt=0)
    unit_cost: float = Field(default=0, ge=0)
    order_id: int | None = None
    purchase_order_id: int | None = None

    @field_validator("yarn_type", "colour")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class StockOut(BaseModel):
    id: int
    yarn_type: str
    colour: str
    quantity_kg: float
    reorder_level_kg: float
    unit_cost: float
    low_stock: bool
    updated_at: datetime


class PurchaseCreate(BaseModel):
    supplier_id: int
    yarn_type: str = Field(min_length=1, max_length=80)
    colour: str = Field(min_length=1, max_length=60)
    quantity_kg: float = Field(gt=0)
    unit_cost: float = Field(default=0, ge=0)


class PurchaseOut(BaseModel):
    id: int
    po_no: str
    supplier_id: int
    supplier_name: str
    yarn_type: str
    colour: str
    quantity_kg: float
    unit_cost: float
    status: str
    created_at: datetime


class SupplierOut(BaseModel):
    id: int
    name: str


# --------------------------- helpers --------------------------- #
def _is_low(stock: YarnStock) -> bool:
    threshold = (
        float(stock.reorder_level_kg)
        if stock.reorder_level_kg and float(stock.reorder_level_kg) > 0
        else settings.default_reorder_level_kg
    )
    return float(stock.quantity_kg) <= threshold


def _stock_out(s: YarnStock) -> StockOut:
    return StockOut(
        id=s.id,
        yarn_type=s.yarn_type,
        colour=s.colour,
        quantity_kg=float(s.quantity_kg),
        reorder_level_kg=float(s.reorder_level_kg or 0),
        unit_cost=float(s.unit_cost or 0),
        low_stock=_is_low(s),
        updated_at=s.updated_at,
    )


def _next_po_no(db: Session) -> str:
    n = db.query(func.count(PurchaseOrder.id)).scalar() or 0
    return f"PO-{1001 + n}"


# --------------------------- endpoints --------------------------- #
@router.get("/stock", response_model=list[StockOut])
def list_stock(
    _=Depends(require_resource("stock")),
    db: Session = Depends(get_db),
):
    rows = db.query(YarnStock).order_by(YarnStock.yarn_type, YarnStock.colour).all()
    return [_stock_out(s) for s in rows]


@router.post("/receipts", response_model=StockOut, status_code=201)
def receive_yarn(
    body: ReceiptCreate,
    _=Depends(require_resource("yarn")),
    db: Session = Depends(get_db),
):
    if body.supplier_id is not None:
        if db.query(Supplier).filter(Supplier.id == body.supplier_id).first() is None:
            raise HTTPException(status_code=400, detail="Unknown supplier")
    if body.order_id is not None:
        if db.query(Order).filter(Order.id == body.order_id).first() is None:
            raise HTTPException(status_code=400, detail="Unknown linked order")

    # Match an existing stock row by type+colour (case-insensitive); else create.
    stock = (
        db.query(YarnStock)
        .filter(
            func.lower(YarnStock.yarn_type) == body.yarn_type.lower(),
            func.lower(YarnStock.colour) == body.colour.lower(),
        )
        .first()
    )
    if stock is None:
        stock = YarnStock(
            yarn_type=body.yarn_type,
            colour=body.colour,
            quantity_kg=0,
            reorder_level_kg=settings.default_reorder_level_kg,
            unit_cost=body.unit_cost,
        )
        db.add(stock)
        db.flush()

    # Record the receipt and increase stock in one transaction.
    receipt = YarnReceipt(
        yarn_stock_id=stock.id,
        supplier_id=body.supplier_id,
        purchase_order_id=body.purchase_order_id,
        order_id=body.order_id,
        yarn_type=body.yarn_type,
        colour=body.colour,
        quantity_kg=body.quantity_kg,
        unit_cost=body.unit_cost,
    )
    db.add(receipt)
    stock.quantity_kg = float(stock.quantity_kg) + float(body.quantity_kg)
    if body.unit_cost:
        stock.unit_cost = body.unit_cost
    stock.updated_at = datetime.utcnow()

    # If this receipt fulfils a purchase order, mark it received.
    if body.purchase_order_id:
        po = (
            db.query(PurchaseOrder)
            .filter(PurchaseOrder.id == body.purchase_order_id)
            .first()
        )
        if po and po.status == "raised":
            po.status = "received"

    db.commit()
    db.refresh(stock)
    return _stock_out(stock)


@router.post("/purchase", response_model=PurchaseOut, status_code=201)
def raise_purchase(
    body: PurchaseCreate,
    _=Depends(require_resource("purchase")),
    db: Session = Depends(get_db),
):
    supplier = db.query(Supplier).filter(Supplier.id == body.supplier_id).first()
    if supplier is None:
        raise HTTPException(status_code=400, detail="Unknown supplier")

    po = PurchaseOrder(
        supplier_id=body.supplier_id,
        po_no=_next_po_no(db),
        yarn_type=body.yarn_type,
        colour=body.colour,
        quantity_kg=body.quantity_kg,
        unit_cost=body.unit_cost,
        status="raised",
    )
    db.add(po)
    db.commit()
    db.refresh(po)
    return PurchaseOut(
        id=po.id,
        po_no=po.po_no,
        supplier_id=po.supplier_id,
        supplier_name=supplier.name,
        yarn_type=po.yarn_type,
        colour=po.colour,
        quantity_kg=float(po.quantity_kg),
        unit_cost=float(po.unit_cost),
        status=po.status,
        created_at=po.created_at,
    )


@router.get("/purchase", response_model=list[PurchaseOut])
def list_purchase(
    _=Depends(require_resource("purchase")),
    db: Session = Depends(get_db),
):
    rows = db.query(PurchaseOrder).order_by(PurchaseOrder.id.desc()).all()
    out = []
    for po in rows:
        supplier = db.query(Supplier).filter(Supplier.id == po.supplier_id).first()
        out.append(
            PurchaseOut(
                id=po.id,
                po_no=po.po_no,
                supplier_id=po.supplier_id,
                supplier_name=supplier.name if supplier else "",
                yarn_type=po.yarn_type,
                colour=po.colour,
                quantity_kg=float(po.quantity_kg),
                unit_cost=float(po.unit_cost),
                status=po.status,
                created_at=po.created_at,
            )
        )
    return out


@router.get("/suppliers", response_model=list[SupplierOut])
def list_suppliers(
    _=Depends(require_resource("yarn")),
    db: Session = Depends(get_db),
):
    rows = db.query(Supplier).order_by(Supplier.name).all()
    return [SupplierOut(id=s.id, name=s.name) for s in rows]

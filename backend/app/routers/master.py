"""Owner master data: buyers, suppliers, machines, employees.

Add + edit the reference records judges enter live. Owner only — every endpoint
guards the "master_data" resource (403 for other roles). Validation returns the
uniform error shape; a successful save fires the matching live event through the
normal SQLAlchemy commit hooks (see live.py).

  GET  /api/master/buyers       POST /api/master/buyers       PUT /api/master/buyers/{id}
  GET  /api/master/suppliers    POST /api/master/suppliers    PUT /api/master/suppliers/{id}
  GET  /api/master/machines     POST /api/master/machines     PUT /api/master/machines/{id}
  GET  /api/master/employees    POST /api/master/employees    PUT /api/master/employees/{id}
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from datetime import datetime

from sqlalchemy import func

from app.database import get_db
from app.deps import require_resource
from app.models import (
    Buyer,
    Employee,
    Machine,
    Order,
    Supplier,
    YarnReceipt,
    YarnStock,
)

router = APIRouter(prefix="/api/master", tags=["master"])

OWNER = require_resource("master_data")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MACHINE_TYPES = ("spinning", "weaving", "dyeing")


# --------------------------------------------------------------------------- #
# Shared validators
# --------------------------------------------------------------------------- #
def _name(v: str) -> str:
    v = " ".join((v or "").split())
    if len(v) < 2 or len(v) > 150:
        raise ValueError("Name must be 2 to 150 characters")
    return v


def _opt_email(v: str | None) -> str | None:
    v = (v or "").strip().lower()
    if not v:
        return None
    if not EMAIL_RE.match(v):
        raise ValueError("Enter a valid email, or leave it empty")
    return v


def _opt_str(v: str | None, maxlen: int = 255) -> str | None:
    v = (v or "").strip()
    if not v:
        return None
    if len(v) > maxlen:
        raise ValueError(f"Must be at most {maxlen} characters")
    return v


# --------------------------------------------------------------------------- #
# Buyers
# --------------------------------------------------------------------------- #
class BuyerIn(BaseModel):
    name: str
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    credit_limit: float = Field(default=0, ge=0)

    @field_validator("name")
    @classmethod
    def _vn(cls, v: str) -> str:
        return _name(v)

    @field_validator("email")
    @classmethod
    def _ve(cls, v: str | None) -> str | None:
        return _opt_email(v)


def _buyer_out(b: Buyer) -> dict:
    return {
        "id": b.id, "name": b.name, "contact_person": b.contact_person,
        "phone": b.phone, "email": b.email, "address": b.address,
        "credit_limit": float(b.credit_limit or 0),
    }


@router.get("/buyers")
def list_buyers(_=Depends(OWNER), db: Session = Depends(get_db)):
    return [_buyer_out(b) for b in db.query(Buyer).order_by(Buyer.name).all()]


@router.post("/buyers", status_code=201)
def create_buyer(body: BuyerIn, _=Depends(OWNER), db: Session = Depends(get_db)):
    if db.query(Buyer).filter(Buyer.name == body.name).first():
        raise HTTPException(status.HTTP_409_CONFLICT, f"A buyer named {body.name} already exists")
    b = Buyer(name=body.name, contact_person=_opt_str(body.contact_person, 120),
              phone=_opt_str(body.phone, 30), email=body.email,
              address=_opt_str(body.address, 500), credit_limit=body.credit_limit)
    db.add(b)
    db.commit()
    db.refresh(b)
    return _buyer_out(b)


@router.put("/buyers/{buyer_id}")
def update_buyer(buyer_id: int, body: BuyerIn, _=Depends(OWNER), db: Session = Depends(get_db)):
    b = db.query(Buyer).filter(Buyer.id == buyer_id).first()
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Buyer not found")
    clash = db.query(Buyer).filter(Buyer.name == body.name, Buyer.id != buyer_id).first()
    if clash:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A buyer named {body.name} already exists")
    b.name = body.name
    b.contact_person = _opt_str(body.contact_person, 120)
    b.phone = _opt_str(body.phone, 30)
    b.email = body.email
    b.address = _opt_str(body.address, 500)
    b.credit_limit = body.credit_limit
    db.commit()
    db.refresh(b)
    return _buyer_out(b)


# --------------------------------------------------------------------------- #
# Suppliers
# --------------------------------------------------------------------------- #
class SupplierIn(BaseModel):
    name: str
    phone: str | None = None
    email: str | None = None
    address: str | None = None

    @field_validator("name")
    @classmethod
    def _vn(cls, v: str) -> str:
        return _name(v)

    @field_validator("email")
    @classmethod
    def _ve(cls, v: str | None) -> str | None:
        return _opt_email(v)


def _supplier_out(s: Supplier) -> dict:
    return {"id": s.id, "name": s.name, "phone": s.phone, "email": s.email,
            "address": s.address}


@router.get("/suppliers")
def list_suppliers(_=Depends(OWNER), db: Session = Depends(get_db)):
    return [_supplier_out(s) for s in db.query(Supplier).order_by(Supplier.name).all()]


@router.post("/suppliers", status_code=201)
def create_supplier(body: SupplierIn, _=Depends(OWNER), db: Session = Depends(get_db)):
    if db.query(Supplier).filter(Supplier.name == body.name).first():
        raise HTTPException(status.HTTP_409_CONFLICT, f"A supplier named {body.name} already exists")
    s = Supplier(name=body.name, phone=_opt_str(body.phone, 30), email=body.email,
                 address=_opt_str(body.address, 500))
    db.add(s)
    db.commit()
    db.refresh(s)
    return _supplier_out(s)


@router.put("/suppliers/{supplier_id}")
def update_supplier(supplier_id: int, body: SupplierIn, _=Depends(OWNER), db: Session = Depends(get_db)):
    s = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")
    clash = db.query(Supplier).filter(Supplier.name == body.name, Supplier.id != supplier_id).first()
    if clash:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A supplier named {body.name} already exists")
    s.name = body.name
    s.phone = _opt_str(body.phone, 30)
    s.email = body.email
    s.address = _opt_str(body.address, 500)
    db.commit()
    db.refresh(s)
    return _supplier_out(s)


# --------------------------------------------------------------------------- #
# Machines
# --------------------------------------------------------------------------- #
class MachineIn(BaseModel):
    name: str
    type: str
    hourly_cost: float = Field(ge=0)
    power_overhead_cost: float = Field(default=0, ge=0)

    @field_validator("name")
    @classmethod
    def _vn(cls, v: str) -> str:
        return _name(v)

    @field_validator("type")
    @classmethod
    def _type_ok(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if v not in MACHINE_TYPES:
            raise ValueError(f"Type must be one of {', '.join(MACHINE_TYPES)}")
        return v


def _machine_out(m: Machine) -> dict:
    return {"id": m.id, "name": m.name, "type": m.type,
            "current_status": m.current_status,
            "hourly_cost": float(m.hourly_cost or 0),
            "power_overhead_cost": float(m.power_overhead_cost or 0)}


def _check_power(hourly: float, power: float) -> None:
    if power > hourly:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Power + overhead cost cannot exceed the full hourly cost "
            "(the rest is the operator wage).",
        )


@router.get("/machines")
def list_machines(_=Depends(OWNER), db: Session = Depends(get_db)):
    return [_machine_out(m) for m in db.query(Machine).order_by(Machine.name).all()]


@router.post("/machines", status_code=201)
def create_machine(body: MachineIn, _=Depends(OWNER), db: Session = Depends(get_db)):
    if db.query(Machine).filter(Machine.name == body.name).first():
        raise HTTPException(status.HTTP_409_CONFLICT, f"A machine named {body.name} already exists")
    _check_power(body.hourly_cost, body.power_overhead_cost)
    m = Machine(name=body.name, type=body.type, current_status="idle",
                hourly_cost=body.hourly_cost, power_overhead_cost=body.power_overhead_cost)
    db.add(m)
    db.commit()
    db.refresh(m)
    return _machine_out(m)


@router.put("/machines/{machine_id}")
def update_machine(machine_id: int, body: MachineIn, _=Depends(OWNER), db: Session = Depends(get_db)):
    m = db.query(Machine).filter(Machine.id == machine_id).first()
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Machine not found")
    clash = db.query(Machine).filter(Machine.name == body.name, Machine.id != machine_id).first()
    if clash:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A machine named {body.name} already exists")
    _check_power(body.hourly_cost, body.power_overhead_cost)
    m.name = body.name
    m.type = body.type
    m.hourly_cost = body.hourly_cost
    m.power_overhead_cost = body.power_overhead_cost
    db.commit()
    db.refresh(m)
    return _machine_out(m)


# --------------------------------------------------------------------------- #
# Employees
# --------------------------------------------------------------------------- #
class EmployeeIn(BaseModel):
    name: str
    role_on_floor: str | None = None
    daily_wage: float = Field(ge=0)
    phone: str | None = None

    @field_validator("name")
    @classmethod
    def _vn(cls, v: str) -> str:
        return _name(v)


def _employee_out(e: Employee) -> dict:
    return {"id": e.id, "name": e.name, "role_on_floor": e.role_on_floor,
            "daily_wage": float(e.daily_wage or 0), "phone": e.phone}


@router.get("/employees")
def list_employees(_=Depends(OWNER), db: Session = Depends(get_db)):
    return [_employee_out(e) for e in db.query(Employee).order_by(Employee.name).all()]


@router.post("/employees", status_code=201)
def create_employee(body: EmployeeIn, _=Depends(OWNER), db: Session = Depends(get_db)):
    e = Employee(name=body.name, role_on_floor=_opt_str(body.role_on_floor, 80),
                 daily_wage=body.daily_wage, phone=_opt_str(body.phone, 30))
    db.add(e)
    db.commit()
    db.refresh(e)
    return _employee_out(e)


@router.put("/employees/{employee_id}")
def update_employee(employee_id: int, body: EmployeeIn, _=Depends(OWNER), db: Session = Depends(get_db)):
    e = db.query(Employee).filter(Employee.id == employee_id).first()
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")
    e.name = body.name
    e.role_on_floor = _opt_str(body.role_on_floor, 80)
    e.daily_wage = body.daily_wage
    e.phone = _opt_str(body.phone, 30)
    db.commit()
    db.refresh(e)
    return _employee_out(e)


# --------------------------------------------------------------------------- #
# Yarn receipt correction (owner): fix a wrong quantity / rate / linked order.
# Stock is adjusted by the DIFFERENCE so the running stock stays correct.
# --------------------------------------------------------------------------- #
class ReceiptEdit(BaseModel):
    quantity_kg: float = Field(gt=0)
    unit_cost: float = Field(ge=0)
    order_id: int | None = None


def _receipt_out(db: Session, r: YarnReceipt) -> dict:
    order_no = None
    if r.order_id:
        o = db.query(Order).filter(Order.id == r.order_id).first()
        order_no = o.order_no if o else None
    supplier_name = None
    if r.supplier_id:
        s = db.query(Supplier).filter(Supplier.id == r.supplier_id).first()
        supplier_name = s.name if s else None
    return {
        "id": r.id, "yarn_type": r.yarn_type, "colour": r.colour,
        "quantity_kg": float(r.quantity_kg), "unit_cost": float(r.unit_cost or 0),
        "order_id": r.order_id, "order_no": order_no,
        "supplier_name": supplier_name,
        "received_at": r.received_at,
    }


@router.get("/yarn-receipts")
def list_receipts(_=Depends(OWNER), db: Session = Depends(get_db)):
    rows = db.query(YarnReceipt).order_by(YarnReceipt.id.desc()).all()
    return [_receipt_out(db, r) for r in rows]


@router.put("/yarn-receipts/{receipt_id}")
def correct_receipt(receipt_id: int, body: ReceiptEdit, _=Depends(OWNER), db: Session = Depends(get_db)):
    """Correct a wrong receipt. The stock row for this yarn is adjusted by the
    change in quantity (new − old), never going below zero."""
    r = db.query(YarnReceipt).filter(YarnReceipt.id == receipt_id).first()
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Yarn receipt not found")
    if body.order_id is not None:
        if db.query(Order).filter(Order.id == body.order_id).first() is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown linked order")

    delta = float(body.quantity_kg) - float(r.quantity_kg)
    stock = None
    if r.yarn_stock_id:
        stock = db.query(YarnStock).filter(YarnStock.id == r.yarn_stock_id).first()
    if stock is None:
        stock = (
            db.query(YarnStock)
            .filter(
                func.lower(YarnStock.yarn_type) == r.yarn_type.lower(),
                func.lower(YarnStock.colour) == r.colour.lower(),
            )
            .first()
        )
    if stock is not None:
        new_qty = float(stock.quantity_kg) + delta
        if new_qty < 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"That correction would drop {r.yarn_type} ({r.colour}) stock below zero "
                f"(current {float(stock.quantity_kg):.2f} kg). Reduce the change.",
            )
        stock.quantity_kg = new_qty
        if body.unit_cost:
            stock.unit_cost = body.unit_cost
        stock.updated_at = datetime.utcnow()

    r.quantity_kg = body.quantity_kg
    r.unit_cost = body.unit_cost
    r.order_id = body.order_id
    db.commit()
    db.refresh(r)
    return _receipt_out(db, r)

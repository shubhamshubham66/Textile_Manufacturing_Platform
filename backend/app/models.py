"""SQLAlchemy ORM models for the Textile Manufacturing System.

Portable across SQLite (dev) and PostgreSQL (demo/prod): money uses Numeric,
timestamps use DateTime, and no DB-specific types are used.

The schema was reviewed and approved as an ER diagram before creation
(Phase 2, task 5).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Users, roles, buyers
# --------------------------------------------------------------------------- #
class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    # owner | store_manager | floor_supervisor | quality_inspector | accountant | buyer
    name: Mapped[str] = mapped_column(String(50), unique=True)

    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    # Set only for buyer-portal logins; links the login to a buyer record.
    buyer_id: Mapped[int | None] = mapped_column(ForeignKey("buyers.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(180), unique=True)
    # Optional short login ID (e.g. MGR-001) for staff the owner creates; they
    # can sign in with it instead of an email. Stored upper-case.
    login_id: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    # Department a department manager runs (purchase|production|qc|store|
    # dispatch|accounts). None = the default for the user's role.
    department: Mapped[str | None] = mapped_column(String(30), nullable=True)

    role: Mapped["Role"] = relationship(back_populates="users")
    buyer: Mapped["Buyer | None"] = relationship(back_populates="users")


class Buyer(Base):
    __tablename__ = "buyers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    contact_person: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    credit_limit: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    users: Mapped[list["User"]] = relationship(back_populates="buyer")
    orders: Mapped[list["Order"]] = relationship(back_populates="buyer")


# --------------------------------------------------------------------------- #
# Orders & items
# --------------------------------------------------------------------------- #
class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("buyers.id"))
    order_no: Mapped[str] = mapped_column(String(40), unique=True)
    fabric_type: Mapped[str] = mapped_column(String(80))
    colour: Mapped[str] = mapped_column(String(60))
    quantity_meters: Mapped[float] = mapped_column(Numeric(12, 2))
    unit: Mapped[str] = mapped_column(String(20), default="meters")
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    # draft|confirmed|in_production|in_quality|ready_to_ship|dispatched|closed
    status: Mapped[str] = mapped_column(String(30), default="draft")
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    # Review by the Supermanager: reason for reject / clarification asked.
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    buyer_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    buyer: Mapped["Buyer"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")
    rolls: Mapped[list["Roll"]] = relationship(back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    yarn_stock_id: Mapped[int | None] = mapped_column(
        ForeignKey("yarn_stock.id"), nullable=True
    )
    yarn_type: Mapped[str] = mapped_column(String(80))
    colour: Mapped[str] = mapped_column(String(60))
    required_qty_kg: Mapped[float] = mapped_column(Numeric(12, 2))
    allocated_qty_kg: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    order: Mapped["Order"] = relationship(back_populates="items")


# --------------------------------------------------------------------------- #
# Yarn store, suppliers, purchase orders
# --------------------------------------------------------------------------- #
class YarnStock(Base):
    __tablename__ = "yarn_stock"

    id: Mapped[int] = mapped_column(primary_key=True)
    yarn_type: Mapped[str] = mapped_column(String(80))
    colour: Mapped[str] = mapped_column(String(60))
    quantity_kg: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    reorder_level_kg: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    unit_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    location: Mapped[str | None] = mapped_column(String(80), nullable=True)  # rack / bay in the store


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(120), nullable=True)
    yarn_types: Mapped[str | None] = mapped_column(Text, nullable=True)  # comma-separated
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    po_no: Mapped[str] = mapped_column(String(40), unique=True)
    yarn_type: Mapped[str] = mapped_column(String(80))
    colour: Mapped[str] = mapped_column(String(60))
    quantity_kg: Mapped[float] = mapped_column(Numeric(12, 2))
    unit_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    status: Mapped[str] = mapped_column(String(20), default="raised")  # raised|partial|received|cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    purchase_request_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tax_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    expected_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class YarnReceipt(Base):
    __tablename__ = "yarn_receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    yarn_stock_id: Mapped[int | None] = mapped_column(
        ForeignKey("yarn_stock.id"), nullable=True
    )
    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id"), nullable=True
    )
    purchase_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_orders.id"), nullable=True
    )
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    yarn_type: Mapped[str] = mapped_column(String(80))
    colour: Mapped[str] = mapped_column(String(60))
    quantity_kg: Mapped[float] = mapped_column(Numeric(12, 2))
    unit_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    # Receiving workflow: recorded -> validated (stock goes up) or rejected.
    # Older receipts updated stock immediately, so they default to validated.
    status: Mapped[str] = mapped_column(String(20), default="validated")
    batch_no: Mapped[str | None] = mapped_column(String(60), nullable=True)
    damaged_kg: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    discrepancy: Mapped[str | None] = mapped_column(String(80), nullable=True)  # shortage,excess,damaged
    discrepancy_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validated_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# --------------------------------------------------------------------------- #
# Machines, status logs, production
# --------------------------------------------------------------------------- #
class Machine(Base):
    __tablename__ = "machines"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    type: Mapped[str] = mapped_column(String(30))  # spinning|weaving|dyeing
    current_status: Mapped[str] = mapped_column(String(20), default="idle")  # running|idle|breakdown
    # Full machine-hour cost (power + overhead + the operator wage sitting on it).
    # Used for idle-loss: when a machine is idle the WHOLE hour is wasted.
    hourly_cost: Mapped[float] = mapped_column(Numeric(10, 2), default=0)  # INR/hr
    # Power + overhead ONLY (no operator wage). Used for cost-per-order so that
    # operator wages are not double-counted (wages come from the wages module).
    # Falls back to a share of hourly_cost when 0 (see services/reports.py).
    power_overhead_cost: Mapped[float] = mapped_column(Numeric(10, 2), default=0)  # INR/hr
    status_since: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    # Currently assigned order + stage (null when the machine is unassigned).
    current_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id"), nullable=True
    )
    current_stage: Mapped[str | None] = mapped_column(String(20), nullable=True)

    status_logs: Mapped[list["MachineStatusLog"]] = relationship(back_populates="machine")
    rolls: Mapped[list["Roll"]] = relationship(back_populates="machine")


class MachineStatusLog(Base):
    __tablename__ = "machine_status_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id"))
    logged_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20))  # running|idle|breakdown
    start_time: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    machine: Mapped["Machine"] = relationship(back_populates="status_logs")


class ProductionLog(Base):
    __tablename__ = "production_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id"))
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    stage: Mapped[str] = mapped_column(String(20))  # spinning|weaving|dyeing
    output_meters: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    log_date: Mapped[date] = mapped_column(Date, default=lambda: date.today())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


# --------------------------------------------------------------------------- #
# Rolls & quality
# --------------------------------------------------------------------------- #
class Roll(Base):
    __tablename__ = "rolls"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id"))
    roll_no: Mapped[str] = mapped_column(String(40), unique=True)
    length_meters: Mapped[float] = mapped_column(Numeric(10, 2))
    # pending|pass|rework|reject|dispatched
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    order: Mapped["Order"] = relationship(back_populates="rolls")
    machine: Mapped["Machine"] = relationship(back_populates="rolls")
    inspection: Mapped["QualityInspection | None"] = relationship(
        back_populates="roll", uselist=False
    )


class QualityInspection(Base):
    __tablename__ = "quality_inspections"

    id: Mapped[int] = mapped_column(primary_key=True)
    roll_id: Mapped[int] = mapped_column(ForeignKey("rolls.id"))
    inspector_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    result: Mapped[str] = mapped_column(String(20))  # pass|rework|reject
    # none|hole|colour_mismatch|uneven_weaving|other
    defect_type: Mapped[str] = mapped_column(String(30), default="none")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    inspected_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    roll: Mapped["Roll"] = relationship(back_populates="inspection")


# --------------------------------------------------------------------------- #
# Dispatch & invoices
# --------------------------------------------------------------------------- #
class Dispatch(Base):
    __tablename__ = "dispatches"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    buyer_id: Mapped[int] = mapped_column(ForeignKey("buyers.id"))
    dispatch_no: Mapped[str] = mapped_column(String(40), unique=True)
    total_rolls: Mapped[int] = mapped_column(default=0)
    total_meters: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    status: Mapped[str] = mapped_column(String(20), default="packed")  # packed|loaded|shipped|delivered
    dispatched_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    # Sales & Dispatch: delivery challan + logistics details. Added via
    # schema_sync on existing databases (all nullable, so old rows are fine).
    challan_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    vehicle_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    transporter: Mapped[str | None] = mapped_column(String(120), nullable=True)
    driver_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dispatched_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    items: Mapped[list["DispatchItem"]] = relationship(back_populates="dispatch")


class DispatchItem(Base):
    __tablename__ = "dispatch_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    dispatch_id: Mapped[int] = mapped_column(ForeignKey("dispatches.id"))
    # A roll may appear in only one dispatch (prevents double dispatch).
    roll_id: Mapped[int] = mapped_column(ForeignKey("rolls.id"), unique=True)
    length_meters: Mapped[float] = mapped_column(Numeric(10, 2))

    dispatch: Mapped["Dispatch"] = relationship(back_populates="items")


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    dispatch_id: Mapped[int | None] = mapped_column(
        ForeignKey("dispatches.id"), nullable=True
    )
    buyer_id: Mapped[int] = mapped_column(ForeignKey("buyers.id"))
    invoice_no: Mapped[str] = mapped_column(String(40), unique=True)
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    tax: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    status: Mapped[str] = mapped_column(String(20), default="unpaid")  # unpaid|part_paid|paid
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    direction: Mapped[str] = mapped_column(String(12))  # incoming|outgoing
    buyer_id: Mapped[int | None] = mapped_column(ForeignKey("buyers.id"), nullable=True)
    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id"), nullable=True
    )
    invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoices.id"), nullable=True
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    method: Mapped[str] = mapped_column(String(20), default="bank")  # cash|bank|upi
    paid_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    # Accounts & Finance: free-text category/note + reference for expenses and
    # non-supplier outgoings. Added via schema_sync on existing databases.
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)  # production|rent|utility|other…
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference: Mapped[str | None] = mapped_column(String(80), nullable=True)
    recorded_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Void (owner only). A voided payment is kept for the audit trail but is
    # excluded from every total (invoice paid, supplier outstanding, P&L, dues).
    voided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    void_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    voided_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )


# --------------------------------------------------------------------------- #
# Employees, attendance, wages
# --------------------------------------------------------------------------- #
class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    role_on_floor: Mapped[str | None] = mapped_column(String(80), nullable=True)
    daily_wage: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    department: Mapped[str | None] = mapped_column(String(30), nullable=True)
    manager_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    attendance: Mapped[list["Attendance"]] = relationship(back_populates="employee")
    wages: Mapped[list["Wage"]] = relationship(back_populates="employee")


class Attendance(Base):
    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    work_date: Mapped[date] = mapped_column(Date, default=lambda: date.today())
    shift: Mapped[str] = mapped_column(String(20), default="morning")  # morning|evening|night
    status: Mapped[str] = mapped_column(String(20), default="present")  # present|absent|half_day
    hours_worked: Mapped[float] = mapped_column(Numeric(5, 2), default=0)

    employee: Mapped["Employee"] = relationship(back_populates="attendance")


class Wage(Base):
    __tablename__ = "wages"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    days_present: Mapped[float] = mapped_column(Numeric(5, 1), default=0)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|paid
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    employee: Mapped["Employee"] = relationship(back_populates="wages")


# --------------------------------------------------------------------------- #
# Signup email OTP
# --------------------------------------------------------------------------- #
class EmailOtp(Base):
    """One pending signup code per email. The code itself is never stored, only
    its bcrypt hash; the row is deleted once the code is used."""

    __tablename__ = "email_otps"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    code_hash: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    attempts: Mapped[int] = mapped_column(Integer, default=0)


# --------------------------------------------------------------------------- #
# Supermanager: instructions (tasks), activity log, settings
# --------------------------------------------------------------------------- #
class Task(Base):
    """An instruction from the Supermanager to a department manager."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    department: Mapped[str] = mapped_column(String(30))
    manager_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Worker the department manager handed this task to (optional).
    worker_employee_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority: Mapped[str] = mapped_column(String(10), default="medium")  # low|medium|high|urgent
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|in_progress|completed
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    auto: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class TaskUpdate(Base):
    __tablename__ = "task_updates"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class ActivityLog(Base):
    """Append-only audit trail of important actions (written automatically)."""

    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    user_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str] = mapped_column(String(30))  # order|stock|qc|dispatch|attendance|team|worker|task|payment
    action: Mapped[str] = mapped_column(String(60))
    details: Mapped[str] = mapped_column(Text, default="")


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


# --------------------------------------------------------------------------- #
# Purchase & raw material: requests, stock movements, notifications
# --------------------------------------------------------------------------- #
class PurchaseRequest(Base):
    """A request to buy yarn. Needs Supermanager approval (unless under the
    configured auto-approve limit) before a purchase order can be raised."""

    __tablename__ = "purchase_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    pr_no: Mapped[str] = mapped_column(String(40), unique=True)
    yarn_type: Mapped[str] = mapped_column(String(80))
    colour: Mapped[str] = mapped_column(String(60))
    quantity_kg: Mapped[float] = mapped_column(Numeric(12, 2))
    required_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual|low_stock|instruction|order
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected|ordered|received
    requested_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decided_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class StockMovement(Base):
    """Every change to a yarn stock quantity (written automatically)."""

    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    yarn_stock_id: Mapped[int] = mapped_column(Integer, index=True)
    yarn_type: Mapped[str] = mapped_column(String(80))
    colour: Mapped[str] = mapped_column(String(60))
    change_kg: Mapped[float] = mapped_column(Numeric(12, 2))
    balance_kg: Mapped[float] = mapped_column(Numeric(12, 2))
    kind: Mapped[str] = mapped_column(String(20))  # receipt|issue|adjustment|correction|opening
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class Notification(Base):
    """A message to a role (or one user): approvals, shared availability…"""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    to_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    to_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kind: Mapped[str] = mapped_column(String(30))  # approval|rejection|availability|info
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_user_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

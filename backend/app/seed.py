"""Seed the database with realistic demo data for live judging.

Creates:
  - 6 roles + demo users (one per role) + buyer-portal logins
  - 5 buyers
  - 3 suppliers + purchase orders
  - Yarn stock (several types/colours, incl. one below reorder level)
  - 8 machines (spinning / weaving / dyeing) with hourly costs
  - 6 orders at different stages (draft -> closed)
  - 30 rolls spread across orders/machines with mixed quality results
  - Machine status logs incl. idle + breakdown windows (for the idle-loss USP)
  - Production logs, a dispatch + invoice + payment, employees, attendance, wages

Idempotent: running it clears existing rows first.

Usage:
    python -m app.seed

Demo passwords are documented in README under "Demo logins". They are hashed with
bcrypt before storage (no plaintext in the DB). These are throwaway demo accounts,
not real secrets.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.database import Base, SessionLocal, engine
from app import models as m
from app.security import hash_password


def _hash(pw: str) -> str:
    # Real bcrypt hashing (Phase 4). Demo passwords are listed in the README.
    return hash_password(pw)


def reset_tables() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed() -> None:
    reset_tables()
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    today = date.today()

    try:
        # ---- Roles ----
        role_names = [
            "owner",
            "store_manager",
            "floor_supervisor",
            "quality_inspector",
            "accountant",
            "buyer",
        ]
        roles = {n: m.Role(name=n) for n in role_names}
        db.add_all(roles.values())
        db.flush()

        # ---- Staff users (one per non-buyer role) ----
        staff = [
            m.User(role_id=roles["owner"].id, name="Ramesh Shah",
                   email="owner@everest.test", password_hash=_hash("owner123")),
            m.User(role_id=roles["store_manager"].id, name="Sunita Patel",
                   email="store@everest.test", password_hash=_hash("store123")),
            m.User(role_id=roles["floor_supervisor"].id, name="Arjun Mehta",
                   email="floor@everest.test", password_hash=_hash("floor123")),
            m.User(role_id=roles["quality_inspector"].id, name="Priya Nair",
                   email="quality@everest.test", password_hash=_hash("quality123")),
            m.User(role_id=roles["accountant"].id, name="Deepak Rao",
                   email="accounts@everest.test", password_hash=_hash("accounts123")),
        ]
        db.add_all(staff)

        # ---- Buyers (5) ----
        buyers = [
            m.Buyer(name="Mumbai Fashion House", contact_person="Nikhil Jain",
                    phone="+91 98200 10001", email="buy1@everest.test",
                    address="Dadar, Mumbai", credit_limit=500000),
            m.Buyer(name="Surat Silk Traders", contact_person="Hetal Desai",
                    phone="+91 98250 10002", email="buy2@everest.test",
                    address="Ring Road, Surat", credit_limit=300000),
            m.Buyer(name="Delhi Garments Co", contact_person="Rohit Khanna",
                    phone="+91 98110 10003", email="buy3@everest.test",
                    address="Karol Bagh, Delhi", credit_limit=750000),
            m.Buyer(name="Chennai Cotton Mills", contact_person="Lakshmi Iyer",
                    phone="+91 98400 10004", email="buy4@everest.test",
                    address="T Nagar, Chennai", credit_limit=250000),
            m.Buyer(name="Jaipur Textile Bazaar", contact_person="Mahesh Sharma",
                    phone="+91 98290 10005", email="buy5@everest.test",
                    address="Johari Bazaar, Jaipur", credit_limit=400000),
        ]
        db.add_all(buyers)
        db.flush()

        # One buyer-portal login for the first buyer.
        db.add(m.User(role_id=roles["buyer"].id, buyer_id=buyers[0].id,
                      name="Nikhil Jain", email="buyer@everest.test",
                      password_hash=_hash("buyer123")))

        # ---- Suppliers (3) + purchase orders ----
        suppliers = [
            m.Supplier(name="Gujarat Yarn Supply", phone="+91 90000 20001",
                       email="sup1@everest.test", address="Ahmedabad"),
            m.Supplier(name="South India Spinners", phone="+91 90000 20002",
                       email="sup2@everest.test", address="Coimbatore"),
            m.Supplier(name="Punjab Cotton Co", phone="+91 90000 20003",
                       email="sup3@everest.test", address="Ludhiana"),
        ]
        db.add_all(suppliers)
        db.flush()

        pos = [
            m.PurchaseOrder(supplier_id=suppliers[0].id, po_no="PO-1001",
                            yarn_type="Cotton 30s", colour="White",
                            quantity_kg=1000, unit_cost=180, status="received"),
            m.PurchaseOrder(supplier_id=suppliers[1].id, po_no="PO-1002",
                            yarn_type="Polyester 150D", colour="Black",
                            quantity_kg=600, unit_cost=140, status="received"),
            m.PurchaseOrder(supplier_id=suppliers[2].id, po_no="PO-1003",
                            yarn_type="Cotton 40s", colour="Blue",
                            quantity_kg=400, unit_cost=200, status="raised"),
        ]
        db.add_all(pos)
        db.flush()

        # ---- Yarn stock (one deliberately below reorder level) ----
        yarn = [
            m.YarnStock(yarn_type="Cotton 30s", colour="White", quantity_kg=820,
                        reorder_level_kg=200, unit_cost=180),
            m.YarnStock(yarn_type="Polyester 150D", colour="Black", quantity_kg=480,
                        reorder_level_kg=150, unit_cost=140),
            m.YarnStock(yarn_type="Cotton 40s", colour="Blue", quantity_kg=90,
                        reorder_level_kg=150, unit_cost=200),  # LOW STOCK
            m.YarnStock(yarn_type="Viscose 20s", colour="Red", quantity_kg=260,
                        reorder_level_kg=100, unit_cost=160),
        ]
        db.add_all(yarn)
        db.flush()

        # Yarn receipts (link one to an order later)
        db.add_all([
            m.YarnReceipt(yarn_stock_id=yarn[0].id, supplier_id=suppliers[0].id,
                          purchase_order_id=pos[0].id, yarn_type="Cotton 30s",
                          colour="White", quantity_kg=1000, unit_cost=180,
                          received_at=now - timedelta(days=10)),
            m.YarnReceipt(yarn_stock_id=yarn[1].id, supplier_id=suppliers[1].id,
                          purchase_order_id=pos[1].id, yarn_type="Polyester 150D",
                          colour="Black", quantity_kg=600, unit_cost=140,
                          received_at=now - timedelta(days=7)),
        ])

        # ---- Machines (8): spinning x3, weaving x3, dyeing x2 ----
        machines = [
            m.Machine(name="Spin-01", type="spinning", current_status="running", hourly_cost=250),
            m.Machine(name="Spin-02", type="spinning", current_status="idle", hourly_cost=250),
            m.Machine(name="Spin-03", type="spinning", current_status="breakdown", hourly_cost=250),
            m.Machine(name="Weave-01", type="weaving", current_status="running", hourly_cost=400),
            m.Machine(name="Weave-02", type="weaving", current_status="running", hourly_cost=400),
            m.Machine(name="Weave-03", type="weaving", current_status="idle", hourly_cost=400),
            m.Machine(name="Dye-01", type="dyeing", current_status="running", hourly_cost=550),
            m.Machine(name="Dye-02", type="dyeing", current_status="idle", hourly_cost=550),
        ]
        db.add_all(machines)
        db.flush()

        # ---- Machine status logs (idle + breakdown windows for idle-loss) ----
        db.add_all([
            # Spin-02 idle for 3h (closed window)
            m.MachineStatusLog(machine_id=machines[1].id, status="idle",
                               start_time=now - timedelta(hours=5),
                               end_time=now - timedelta(hours=2),
                               reason="No order assigned"),
            # Spin-02 idle ongoing (open window)
            m.MachineStatusLog(machine_id=machines[1].id, status="idle",
                               start_time=now - timedelta(hours=2),
                               end_time=None, reason="Waiting for yarn"),
            # Spin-03 breakdown ongoing
            m.MachineStatusLog(machine_id=machines[2].id, status="breakdown",
                               start_time=now - timedelta(hours=4),
                               end_time=None, reason="Motor fault"),
            # Weave-03 idle ongoing
            m.MachineStatusLog(machine_id=machines[5].id, status="idle",
                               start_time=now - timedelta(hours=1, minutes=30),
                               end_time=None, reason="Shift changeover"),
            # Dye-02 idle ongoing
            m.MachineStatusLog(machine_id=machines[7].id, status="idle",
                               start_time=now - timedelta(hours=1),
                               end_time=None, reason="Cleaning"),
            # A running log for Weave-01 (context)
            m.MachineStatusLog(machine_id=machines[3].id, status="running",
                               start_time=now - timedelta(hours=6),
                               end_time=None, reason="Order WO-003"),
        ])

        # ---- Orders (6) at different stages ----
        stages = [
            ("ORD-2001", buyers[0].id, "Cotton Shirting", "White", 2000, "closed", 95),
            ("ORD-2002", buyers[1].id, "Silk Blend", "Black", 1200, "dispatched", 140),
            ("ORD-2003", buyers[2].id, "Denim", "Blue", 3000, "in_quality", 120),
            ("ORD-2004", buyers[3].id, "Cotton Poplin", "Red", 1500, "in_production", 110),
            ("ORD-2005", buyers[4].id, "Polyester Lining", "Black", 1800, "confirmed", 80),
            ("ORD-2006", buyers[0].id, "Viscose Crepe", "Red", 900, "draft", 130),
        ]
        orders = []
        for order_no, buyer_id, fabric, colour, qty, status, price in stages:
            o = m.Order(order_no=order_no, buyer_id=buyer_id, fabric_type=fabric,
                        colour=colour, quantity_meters=qty, status=status,
                        unit_price=price, deadline=today + timedelta(days=14),
                        created_at=now - timedelta(days=12))
            orders.append(o)
        db.add_all(orders)
        db.flush()

        # Order items (yarn requirement per order)
        db.add_all([
            m.OrderItem(order_id=orders[0].id, yarn_stock_id=yarn[0].id,
                        yarn_type="Cotton 30s", colour="White",
                        required_qty_kg=400, allocated_qty_kg=400),
            m.OrderItem(order_id=orders[2].id, yarn_stock_id=yarn[2].id,
                        yarn_type="Cotton 40s", colour="Blue",
                        required_qty_kg=300, allocated_qty_kg=90),  # short -> reorder
            m.OrderItem(order_id=orders[3].id, yarn_stock_id=yarn[3].id,
                        yarn_type="Viscose 20s", colour="Red",
                        required_qty_kg=220, allocated_qty_kg=220),
        ])

        # ---- Assign current orders + stage to running machines ----
        # (so the floor view shows which order is on which machine + progress)
        machines[0].current_order_id = orders[3].id  # Spin-01 -> ORD-2004
        machines[0].current_stage = "spinning"
        machines[3].current_order_id = orders[2].id  # Weave-01 -> ORD-2003
        machines[3].current_stage = "weaving"
        machines[4].current_order_id = orders[3].id  # Weave-02 -> ORD-2004
        machines[4].current_stage = "weaving"
        machines[6].current_order_id = orders[2].id  # Dye-01 -> ORD-2003
        machines[6].current_stage = "dyeing"

        # ---- Production logs ----
        db.add_all([
            m.ProductionLog(machine_id=machines[3].id, order_id=orders[2].id,
                            stage="weaving", output_meters=600, log_date=today),
            m.ProductionLog(machine_id=machines[4].id, order_id=orders[3].id,
                            stage="weaving", output_meters=450, log_date=today),
            m.ProductionLog(machine_id=machines[6].id, order_id=orders[2].id,
                            stage="dyeing", output_meters=500, log_date=today),
            m.ProductionLog(machine_id=machines[0].id, order_id=orders[3].id,
                            stage="spinning", output_meters=380, log_date=today),
        ])

        # ---- Rolls (30) spread across orders/machines, mixed quality ----
        # Distribution: order index -> number of rolls
        plan = [
            (orders[0], machines[3], 8),   # closed order, all pass+dispatched later
            (orders[1], machines[4], 6),   # dispatched order
            (orders[2], machines[6], 9),   # in_quality: mix pending/pass/rework/reject
            (orders[3], machines[0], 7),   # in_production: mostly pending
        ]
        rolls: list[m.Roll] = []
        counter = 1
        for order, machine, n in plan:
            for _ in range(n):
                rolls.append(
                    m.Roll(order_id=order.id, machine_id=machine.id,
                           roll_no=f"R-{counter:04d}", length_meters=50,
                           status="pending")
                )
                counter += 1
        db.add_all(rolls)
        db.flush()

        # Assign quality results.
        # Order 0 (closed) rolls 0-7: all pass (will be dispatched)
        for r in rolls[0:8]:
            r.status = "pass"
        # Order 1 (dispatched) rolls 8-13: all pass + dispatched
        for r in rolls[8:14]:
            r.status = "dispatched"
        # Order 2 (in_quality) rolls 14-22: mix
        quality_mix = ["pass", "pass", "pass", "rework", "reject",
                       "pass", "pending", "pending", "pass"]
        for r, res in zip(rolls[14:23], quality_mix):
            r.status = res
        # Order 3 (in_production) rolls 23-29: pending
        for r in rolls[23:30]:
            r.status = "pending"

        # Quality inspection records for inspected rolls (order 2 window)
        inspector = staff[3]  # quality inspector
        db.flush()
        defect_for = {"rework": "uneven_weaving", "reject": "hole"}
        for r in rolls[14:23]:
            if r.status in ("pass", "rework", "reject"):
                db.add(m.QualityInspection(
                    roll_id=r.id, inspector_user_id=inspector.id,
                    result=r.status,
                    defect_type=defect_for.get(r.status, "none"),
                    notes="Auto-seeded inspection",
                    inspected_at=now - timedelta(hours=3),
                ))

        # ---- Dispatch + invoice + payment for the dispatched order (orders[1]) ----
        dispatched_rolls = rolls[8:14]
        total_m = sum(float(r.length_meters) for r in dispatched_rolls)
        dispatch = m.Dispatch(order_id=orders[1].id, buyer_id=orders[1].buyer_id,
                              dispatch_no="DSP-3001", total_rolls=len(dispatched_rolls),
                              total_meters=total_m, status="shipped",
                              dispatched_at=now - timedelta(days=2))
        db.add(dispatch)
        db.flush()
        for r in dispatched_rolls:
            db.add(m.DispatchItem(dispatch_id=dispatch.id, roll_id=r.id,
                                  length_meters=r.length_meters))

        subtotal = total_m * float(orders[1].unit_price)
        tax = round(subtotal * 0.05, 2)  # 5% demo GST
        invoice = m.Invoice(order_id=orders[1].id, dispatch_id=dispatch.id,
                            buyer_id=orders[1].buyer_id, invoice_no="INV-4001",
                            subtotal=subtotal, tax=tax, total=subtotal + tax,
                            status="part_paid", created_at=now - timedelta(days=2))
        db.add(invoice)
        db.flush()

        db.add_all([
            # Incoming buyer payment (partial)
            m.Payment(direction="incoming", buyer_id=orders[1].buyer_id,
                      invoice_id=invoice.id, amount=round((subtotal + tax) * 0.6, 2),
                      method="bank", paid_at=now - timedelta(days=1)),
            # Outgoing supplier payment
            m.Payment(direction="outgoing", supplier_id=suppliers[0].id,
                      amount=180000, method="bank", paid_at=now - timedelta(days=3)),
        ])

        # ---- Employees, attendance, wages ----
        employees = [
            m.Employee(name="Imran Shaikh", role_on_floor="Spinning operator",
                       daily_wage=550, phone="+91 90001 30001"),
            m.Employee(name="Kavita Jadhav", role_on_floor="Weaving operator",
                       daily_wage=600, phone="+91 90001 30002"),
            m.Employee(name="Suresh Yadav", role_on_floor="Dyeing operator",
                       daily_wage=650, phone="+91 90001 30003"),
            m.Employee(name="Anita Kumari", role_on_floor="Quality helper",
                       daily_wage=500, phone="+91 90001 30004"),
        ]
        db.add_all(employees)
        db.flush()

        for emp in employees:
            for d in range(5):  # last 5 days attendance
                db.add(m.Attendance(
                    employee_id=emp.id, work_date=today - timedelta(days=d),
                    shift="morning",
                    status="present" if d != 2 else "half_day",
                    hours_worked=8 if d != 2 else 4,
                ))

        for emp in employees:
            db.add(m.Wage(
                employee_id=emp.id,
                period_start=today - timedelta(days=6),
                period_end=today,
                days_present=4.5,
                amount=round(float(emp.daily_wage) * 4.5, 2),
                status="pending",
            ))

        db.commit()
        print("Seed complete.")
        _print_summary(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _print_summary(db) -> None:
    counts = {
        "roles": db.query(m.Role).count(),
        "users": db.query(m.User).count(),
        "buyers": db.query(m.Buyer).count(),
        "suppliers": db.query(m.Supplier).count(),
        "purchase_orders": db.query(m.PurchaseOrder).count(),
        "yarn_stock": db.query(m.YarnStock).count(),
        "machines": db.query(m.Machine).count(),
        "machine_status_logs": db.query(m.MachineStatusLog).count(),
        "orders": db.query(m.Order).count(),
        "rolls": db.query(m.Roll).count(),
        "quality_inspections": db.query(m.QualityInspection).count(),
        "dispatches": db.query(m.Dispatch).count(),
        "invoices": db.query(m.Invoice).count(),
        "payments": db.query(m.Payment).count(),
        "employees": db.query(m.Employee).count(),
        "attendance": db.query(m.Attendance).count(),
        "wages": db.query(m.Wage).count(),
    }
    for k, v in counts.items():
        print(f"  {k:22} {v}")


if __name__ == "__main__":
    seed()

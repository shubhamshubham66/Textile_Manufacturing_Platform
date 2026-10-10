"""Seed the database with ONE realistic month (October 2026) for Everest Textile
Mills — tuned so the owner's month-end view is believable (a small profit).

Creates:
  - 6 roles + demo users (one per role) + a buyer-portal login
  - 5 buyers
  - 3 suppliers + purchase orders (realistic rupee values)
  - Yarn stock (incl. one below reorder level) + yarn receipts LINKED to orders
    (so cost-per-order shows real yarn cost, not ₹0)
  - 8 machines with hourly_cost AND power_overhead_cost (power+overhead only,
    so operator wages are not double-counted in cost-per-order)
  - 7 orders at different stages (draft -> closed)
  - rolls across orders/machines with mixed quality results
  - machine status logs incl. idle + breakdown windows (idle-loss USP)
  - production logs, dispatches + invoices + payments, employees, attendance,
    wages — all dated inside October 2026

The month is designed to net a small PROFIT on a cash basis:
    buyer payments received − supplier bills paid − wages paid > 0

Idempotent: running it clears existing rows first.

Usage:  python -m app.seed

Demo passwords are documented in README under "Demo logins"; they are bcrypt
hashed before storage. Throwaway demo accounts, not real secrets.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.database import Base, SessionLocal, engine
from app import models as m
from app.security import hash_password

# Anchor the whole demo to October 2026 so "this month" lights up for judging.
MONTH_YEAR = 2026
MONTH = 10


def _dt(day: int, hour: int = 10) -> datetime:
    return datetime(MONTH_YEAR, MONTH, day, hour, 0, 0, tzinfo=timezone.utc)


def _d(day: int) -> date:
    return date(MONTH_YEAR, MONTH, day)


def _hash(pw: str) -> str:
    return hash_password(pw)


def reset_tables() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed() -> None:
    reset_tables()
    db = SessionLocal()

    try:
        # ---- Roles ----
        role_names = [
            "owner", "store_manager", "floor_supervisor",
            "quality_inspector", "accountant", "buyer", "manager",
            "production_manager",
        ]
        roles = {n: m.Role(name=n) for n in role_names}
        db.add_all(roles.values())
        db.flush()

        # ---- Staff users ----
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
            # Production manager: runs the floor. department="production" makes
            # it the owner of the production department (gets its instructions
            # and workers).
            m.User(role_id=roles["production_manager"].id, name="Vikram Singh",
                   email="production@everest.test", password_hash=_hash("production123"),
                   department="production"),
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

        # PO values (qty × rate):
        #   PO-1001: 1000 × 180 = 1,80,000  (Gujarat, received)
        #   PO-1002:  600 × 140 =   84,000  (South India, received)
        #   PO-1003:  400 × 200 =   80,000  (Punjab, raised — still owed in full)
        pos = [
            m.PurchaseOrder(supplier_id=suppliers[0].id, po_no="PO-1001",
                            yarn_type="Cotton 30s", colour="White",
                            quantity_kg=1000, unit_cost=180, status="received",
                            created_at=_dt(2)),
            m.PurchaseOrder(supplier_id=suppliers[1].id, po_no="PO-1002",
                            yarn_type="Polyester 150D", colour="Black",
                            quantity_kg=600, unit_cost=140, status="received",
                            created_at=_dt(4)),
            m.PurchaseOrder(supplier_id=suppliers[2].id, po_no="PO-1003",
                            yarn_type="Cotton 40s", colour="Blue",
                            quantity_kg=400, unit_cost=200, status="raised",
                            created_at=_dt(6)),
        ]
        db.add_all(pos)
        db.flush()

        # ---- Yarn stock (one below reorder level) ----
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

        # ---- Orders (7) at different stages ----
        # (order_no, buyer, fabric, colour, qty_m, status, unit_price)
        stages = [
            ("ORD-2001", buyers[0].id, "Cotton Shirting", "White", 2000, "closed", 95),
            ("ORD-2002", buyers[1].id, "Silk Blend", "Black", 1200, "dispatched", 140),
            ("ORD-2003", buyers[2].id, "Denim", "Blue", 3000, "in_quality", 120),
            ("ORD-2004", buyers[3].id, "Cotton Poplin", "Red", 1500, "in_production", 110),
            ("ORD-2005", buyers[4].id, "Polyester Lining", "Black", 1800, "confirmed", 80),
            ("ORD-2006", buyers[0].id, "Viscose Crepe", "Red", 900, "draft", 130),
            ("ORD-2007", buyers[2].id, "Cotton Twill", "Grey", 1600, "in_production", 105),
            # A cancelled order so the owner's "Cancelled" group has real data.
            ("ORD-2008", buyers[3].id, "Linen Blend", "Beige", 700, "cancelled", 150),
        ]
        orders = []
        for i, (order_no, buyer_id, fabric, colour, qty, status, price) in enumerate(stages):
            o = m.Order(order_no=order_no, buyer_id=buyer_id, fabric_type=fabric,
                        colour=colour, quantity_meters=qty, status=status,
                        unit_price=price, deadline=_d(26),
                        created_at=_dt(2 + i))
            orders.append(o)
        db.add_all(orders)
        db.flush()

        # Order items (yarn requirement per order).
        db.add_all([
            m.OrderItem(order_id=orders[0].id, yarn_stock_id=yarn[0].id,
                        yarn_type="Cotton 30s", colour="White",
                        required_qty_kg=400, allocated_qty_kg=400),
            m.OrderItem(order_id=orders[1].id, yarn_stock_id=yarn[1].id,
                        yarn_type="Polyester 150D", colour="Black",
                        required_qty_kg=240, allocated_qty_kg=240),
            m.OrderItem(order_id=orders[2].id, yarn_stock_id=yarn[2].id,
                        yarn_type="Cotton 40s", colour="Blue",
                        required_qty_kg=600, allocated_qty_kg=90),  # short -> reorder
            m.OrderItem(order_id=orders[3].id, yarn_stock_id=yarn[3].id,
                        yarn_type="Viscose 20s", colour="Red",
                        required_qty_kg=220, allocated_qty_kg=220),
        ])

        # ---- Yarn receipts LINKED to orders (fixes "Yarn ₹0") ----
        # Each receipt: quantity_kg × unit_cost, dated in October, tied to an order.
        #   ORD-2001: 400 × 180 = 72,000  (Cotton 30s White)
        #   ORD-2002: 240 × 140 = 33,600  (Polyester 150D Black)
        #   ORD-2003:  90 × 200 = 18,000  (Cotton 40s Blue — only partial in stock)
        #   ORD-2004: 220 × 160 = 35,200  (Viscose 20s Red)
        db.add_all([
            m.YarnReceipt(yarn_stock_id=yarn[0].id, supplier_id=suppliers[0].id,
                          purchase_order_id=pos[0].id, order_id=orders[0].id,
                          yarn_type="Cotton 30s", colour="White",
                          quantity_kg=400, unit_cost=180, received_at=_dt(3)),
            m.YarnReceipt(yarn_stock_id=yarn[0].id, supplier_id=suppliers[0].id,
                          purchase_order_id=pos[0].id, order_id=None,
                          yarn_type="Cotton 30s", colour="White",
                          quantity_kg=600, unit_cost=180, received_at=_dt(3)),
            m.YarnReceipt(yarn_stock_id=yarn[1].id, supplier_id=suppliers[1].id,
                          purchase_order_id=pos[1].id, order_id=orders[1].id,
                          yarn_type="Polyester 150D", colour="Black",
                          quantity_kg=240, unit_cost=140, received_at=_dt(5)),
            m.YarnReceipt(yarn_stock_id=yarn[1].id, supplier_id=suppliers[1].id,
                          purchase_order_id=pos[1].id, order_id=None,
                          yarn_type="Polyester 150D", colour="Black",
                          quantity_kg=360, unit_cost=140, received_at=_dt(5)),
            m.YarnReceipt(yarn_stock_id=yarn[2].id, supplier_id=suppliers[2].id,
                          purchase_order_id=None, order_id=orders[2].id,
                          yarn_type="Cotton 40s", colour="Blue",
                          quantity_kg=90, unit_cost=200, received_at=_dt(7)),
            m.YarnReceipt(yarn_stock_id=yarn[3].id, supplier_id=None,
                          purchase_order_id=None, order_id=orders[3].id,
                          yarn_type="Viscose 20s", colour="Red",
                          quantity_kg=220, unit_cost=160, received_at=_dt(8)),
        ])

        # ---- Machines (8): hourly_cost = full; power_overhead_cost = power+OH only
        # (≈60% of hourly_cost; the ~40% operator wage is counted via wages).
        def mk(name, mtype, status, hourly, po):
            return m.Machine(name=name, type=mtype, current_status=status,
                             hourly_cost=hourly, power_overhead_cost=po)

        machines = [
            mk("Spin-01", "spinning", "running", 250, 150),
            mk("Spin-02", "spinning", "idle", 250, 150),
            mk("Spin-03", "spinning", "breakdown", 250, 150),
            mk("Weave-01", "weaving", "running", 400, 240),
            mk("Weave-02", "weaving", "running", 400, 240),
            mk("Weave-03", "weaving", "idle", 400, 240),
            mk("Dye-01", "dyeing", "running", 550, 330),
            mk("Dye-02", "dyeing", "idle", 550, 330),
        ]
        db.add_all(machines)
        db.flush()

        # ---- Machine status logs (idle + breakdown windows for idle-loss) ----
        # Dated late in the month; mix of closed and open windows.
        base = _dt(9, 8)  # closed windows in the past, so figures never drift
        db.add_all([
            m.MachineStatusLog(machine_id=machines[1].id, status="idle",
                               start_time=base, end_time=base + timedelta(hours=3),
                               reason="No order assigned"),
            m.MachineStatusLog(machine_id=machines[1].id, status="idle",
                               start_time=base + timedelta(hours=3),
                               end_time=base + timedelta(hours=5),
                               reason="Waiting for yarn"),
            m.MachineStatusLog(machine_id=machines[2].id, status="breakdown",
                               start_time=base, end_time=base + timedelta(hours=4),
                               reason="Motor fault"),
            m.MachineStatusLog(machine_id=machines[5].id, status="idle",
                               start_time=base,
                               end_time=base + timedelta(hours=1, minutes=30),
                               reason="Shift changeover"),
            m.MachineStatusLog(machine_id=machines[7].id, status="idle",
                               start_time=base, end_time=base + timedelta(hours=1),
                               reason="Cleaning"),
            m.MachineStatusLog(machine_id=machines[3].id, status="running",
                               start_time=base, end_time=base + timedelta(hours=6),
                               reason="ORD-2003"),
            m.MachineStatusLog(machine_id=machines[6].id, status="running",
                               start_time=base, end_time=base + timedelta(hours=5),
                               reason="ORD-2003"),
            # Running windows behind every production log, so machine cost
            # (running hours x power+overhead rate) is real for each order.
            m.MachineStatusLog(machine_id=machines[3].id, status="running",
                               start_time=_dt(5, 8), end_time=_dt(5, 18), reason="ORD-2001"),
            m.MachineStatusLog(machine_id=machines[4].id, status="running",
                               start_time=_dt(6, 8), end_time=_dt(6, 16), reason="ORD-2002"),
            m.MachineStatusLog(machine_id=machines[4].id, status="running",
                               start_time=base, end_time=base + timedelta(hours=4),
                               reason="ORD-2004"),
            m.MachineStatusLog(machine_id=machines[0].id, status="running",
                               start_time=_dt(8, 9), end_time=_dt(8, 12), reason="ORD-2007"),
            m.MachineStatusLog(machine_id=machines[0].id, status="running",
                               start_time=base, end_time=base + timedelta(hours=4),
                               reason="ORD-2004"),
        ])

        # Assign current orders to running machines (floor view).
        machines[0].current_order_id = orders[3].id
        machines[0].current_stage = "spinning"
        machines[3].current_order_id = orders[2].id
        machines[3].current_stage = "weaving"
        machines[4].current_order_id = orders[3].id
        machines[4].current_stage = "weaving"
        machines[6].current_order_id = orders[2].id
        machines[6].current_stage = "dyeing"

        # ---- Production logs (all in October) ----
        db.add_all([
            m.ProductionLog(machine_id=machines[3].id, order_id=orders[2].id,
                            stage="weaving", output_meters=600, log_date=_d(10)),
            m.ProductionLog(machine_id=machines[4].id, order_id=orders[3].id,
                            stage="weaving", output_meters=450, log_date=_d(10)),
            m.ProductionLog(machine_id=machines[6].id, order_id=orders[2].id,
                            stage="dyeing", output_meters=500, log_date=_d(10)),
            m.ProductionLog(machine_id=machines[0].id, order_id=orders[3].id,
                            stage="spinning", output_meters=380, log_date=_d(10)),
            m.ProductionLog(machine_id=machines[3].id, order_id=orders[0].id,
                            stage="weaving", output_meters=2000, log_date=_d(5)),
            m.ProductionLog(machine_id=machines[4].id, order_id=orders[1].id,
                            stage="weaving", output_meters=1200, log_date=_d(6)),
            m.ProductionLog(machine_id=machines[0].id, order_id=orders[6].id,
                            stage="spinning", output_meters=300, log_date=_d(8)),
        ])

        # ---- Rolls across orders/machines, mixed quality ----
        plan = [
            (orders[0], machines[3], 8),
            (orders[1], machines[4], 6),
            (orders[2], machines[6], 9),
            (orders[3], machines[0], 7),
        ]
        rolls: list[m.Roll] = []
        counter = 1
        for order, machine, n in plan:
            for _ in range(n):
                rolls.append(
                    m.Roll(order_id=order.id, machine_id=machine.id,
                           roll_no=f"R-{counter:04d}", length_meters=50,
                           status="pending", created_at=_dt(9))
                )
                counter += 1
        db.add_all(rolls)
        db.flush()

        for r in rolls[0:8]:
            r.status = "pass"
        for r in rolls[8:14]:
            r.status = "dispatched"
        quality_mix = ["pass", "pass", "pass", "rework", "reject",
                       "pass", "pending", "pending", "pass"]
        for r, res in zip(rolls[14:23], quality_mix):
            r.status = res
        for r in rolls[23:30]:
            r.status = "pending"

        inspector = staff[3]
        db.flush()
        defect_for = {"rework": "uneven_weaving", "reject": "hole"}
        for r in rolls[14:23]:
            if r.status in ("pass", "rework", "reject"):
                db.add(m.QualityInspection(
                    roll_id=r.id, inspector_user_id=inspector.id,
                    result=r.status, defect_type=defect_for.get(r.status, "none"),
                    notes="Auto-seeded inspection", inspected_at=_dt(10, 7),
                ))

        # ---- Dispatch + invoices + payments ----
        # ORD-2002 (dispatched) -> INV-4002; ORD-2001 (closed) -> INV-4001.
        dispatched_rolls = rolls[8:14]
        total_m2 = sum(float(r.length_meters) for r in dispatched_rolls)  # 300 m
        dispatch = m.Dispatch(order_id=orders[1].id, buyer_id=orders[1].buyer_id,
                              dispatch_no="DSP-3002", total_rolls=len(dispatched_rolls),
                              total_meters=total_m2, status="shipped",
                              dispatched_at=_dt(9, 15))
        db.add(dispatch)
        db.flush()
        for r in dispatched_rolls:
            db.add(m.DispatchItem(dispatch_id=dispatch.id, roll_id=r.id,
                                  length_meters=r.length_meters))

        # INV-4002 for ORD-2002: 300 m × 140 = 42,000 + 5% tax 2,100 = 44,100.
        sub2 = total_m2 * float(orders[1].unit_price)
        tax2 = round(sub2 * 0.05, 2)
        inv2 = m.Invoice(order_id=orders[1].id, dispatch_id=dispatch.id,
                         buyer_id=orders[1].buyer_id, invoice_no="INV-4002",
                         subtotal=sub2, tax=tax2, total=sub2 + tax2,
                         status="part_paid", created_at=_dt(9, 16))
        db.add(inv2)

        # INV-4001 for ORD-2001 (closed): 2000 m × 95 = 1,90,000 + 5% = 1,99,500,
        # fully paid during the month.
        sub1 = 2000 * 95
        tax1 = round(sub1 * 0.05, 2)
        inv1 = m.Invoice(order_id=orders[0].id, dispatch_id=None,
                         buyer_id=orders[0].buyer_id, invoice_no="INV-4001",
                         subtotal=sub1, tax=tax1, total=sub1 + tax1,
                         status="paid", created_at=_dt(8))
        db.add(inv1)
        db.flush()

        # Payments (all in October). Cash-basis month net:
        #   buyer in : 1,99,500 (INV-4001 full) + 26,460 (INV-4002 60%) = 2,25,960
        #   supplier out: 1,80,000 (PO-1001) + 20,000 (part of PO-1002) = 2,00,000
        #   wages paid : 15,750 (3 of 4 wage records paid; see below)
        #   NET = 2,25,960 − 2,00,000 − 15,750 = +10,210  (small profit)
        db.add_all([
            m.Payment(direction="incoming", buyer_id=orders[0].buyer_id,
                      invoice_id=inv1.id, amount=round(sub1 + tax1, 2),
                      method="bank", paid_at=_dt(9)),
            m.Payment(direction="incoming", buyer_id=orders[1].buyer_id,
                      invoice_id=inv2.id, amount=round((sub2 + tax2) * 0.6, 2),
                      method="bank", paid_at=_dt(10, 9)),
            m.Payment(direction="outgoing", supplier_id=suppliers[0].id,
                      amount=180000, method="bank", paid_at=_dt(6)),
            m.Payment(direction="outgoing", supplier_id=suppliers[1].id,
                      amount=20000, method="bank", paid_at=_dt(7)),
        ])

        # ---- Employees, attendance, wages (October) ----
        employees = [
            m.Employee(name="Imran Shaikh", role_on_floor="Spinning operator",
                       daily_wage=550, phone="+91 90001 30001", department="production"),
            m.Employee(name="Kavita Jadhav", role_on_floor="Weaving operator",
                       daily_wage=600, phone="+91 90001 30002", department="production"),
            m.Employee(name="Suresh Yadav", role_on_floor="Dyeing operator",
                       daily_wage=650, phone="+91 90001 30003", department="production"),
            m.Employee(name="Anita Kumari", role_on_floor="Quality helper",
                       daily_wage=500, phone="+91 90001 30004", department="qc"),
        ]
        # Each worker reports to the manager of their department. Production
        # workers report to the Production manager (staff[5]); the QC helper to
        # the quality inspector (staff[3]).
        db.flush()
        for e in employees:
            e.manager_user_id = staff[5].id if e.department == "production" else staff[3].id
        db.add_all(employees)
        db.flush()

        for emp in employees:
            for day in (5, 6, 7, 8, 9):
                db.add(m.Attendance(
                    employee_id=emp.id, work_date=_d(day), shift="morning",
                    status="present" if day != 8 else "half_day",
                    hours_worked=8 if day != 8 else 4,
                ))

        # One wage record per employee for 05–09 Oct, 4.5 days each (8 Oct is a
        # half day). Three are paid on 10 Oct, Anita's is still due.
        #   Imran : 550 × 4.5 = 2,475   (paid)
        #   Kavita: 600 × 4.5 = 2,700   (paid)
        #   Suresh: 650 × 4.5 = 2,925   (paid)
        #   Anita : 500 × 4.5 = 2,250   (due)
        # Accrued 10,350; paid in October 8,100 (this is what Month net uses).
        wage_rows = []
        for emp, paid in zip(employees, (True, True, True, False)):
            amt = round(float(emp.daily_wage) * 4.5, 2)
            wage_rows.append(m.Wage(
                employee_id=emp.id, period_start=_d(5), period_end=_d(9),
                days_present=4.5, amount=amt,
                status="paid" if paid else "pending",
                paid_at=_dt(10, 9) if paid else None,
            ))
        db.add_all(wage_rows)

        # ---- Production worker tasks (Production manager → floor workers) ----
        # So the Production Manager dashboard and the Worker & Task Assignment
        # screen show real assignments from the first load.
        prod_mgr = staff[5]
        db.add_all([
            m.Task(title=f"Weaving — {orders[2].order_no}",
                   details="Run the weaving stage; target 1,200 m this shift.",
                   department="production", manager_user_id=prod_mgr.id,
                   order_id=orders[2].id, worker_employee_id=employees[1].id,
                   priority="high", deadline=_d(12), status="in_progress",
                   created_by_user_id=prod_mgr.id, auto=False,
                   created_at=_dt(10, 8), updated_at=_dt(10, 9)),
            m.Task(title=f"Dyeing — {orders[2].order_no}",
                   details="Dye the woven lot once weaving crosses 60%.",
                   department="production", manager_user_id=prod_mgr.id,
                   order_id=orders[2].id, worker_employee_id=employees[2].id,
                   priority="medium", deadline=_d(12), status="pending",
                   created_by_user_id=prod_mgr.id, auto=False,
                   created_at=_dt(10, 8), updated_at=_dt(10, 8)),
            m.Task(title=f"Spinning — {orders[3].order_no}",
                   details="Spin yarn for the new weaving run.",
                   department="production", manager_user_id=prod_mgr.id,
                   order_id=orders[3].id, worker_employee_id=employees[0].id,
                   priority="medium", deadline=_d(13), status="in_progress",
                   created_by_user_id=prod_mgr.id, auto=False,
                   created_at=_dt(10, 8), updated_at=_dt(10, 9)),
        ])

        db.commit()
        print("Seed complete (October 2026).")
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
        "yarn_receipts": db.query(m.YarnReceipt).count(),
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

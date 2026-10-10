"""Seed the database with ONE realistic month of demo data — October 2026.

Everything is dated inside Oct 2026 so the owner's month-end view is believable
and hand-checkable. Running this DROPS and recreates all tables, so any stray
records (e.g. a manually-created ORD-2007 or a bad ₹20cr payment) are removed.

Usage:
    python -m app.seed

Costing / month definitions (see docs/MONTH_END_HANDCHECK.md and PROJECT_STATE.md):
  - Yarn cost per order  = Σ(receipt.quantity_kg × receipt.unit_cost) for receipts
                           whose order_id = that order.  (receipts ARE linked here)
  - Machine hourly_cost  = power + overhead ONLY (operator wages are NOT in it, so
                           wages are never double-counted).
  - Wages cost per order = total wages allocated by the order's output-metre share.
  - Month net (cash)     = buyer payments received in month
                           − supplier/raw-material bills paid in month
                           − wages PAID in month.

Demo passwords are documented in README under "Demo logins", bcrypt-hashed.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.database import Base, SessionLocal, engine
from app import models as m
from app.security import hash_password

# The demo month. Everything is dated inside this window.
MONTH_YEAR, MONTH_NO = 2026, 10


def _dt(day: int, hour: int = 10) -> datetime:
    return datetime(MONTH_YEAR, MONTH_NO, day, hour, 0, 0, tzinfo=timezone.utc)


def _d(day: int) -> date:
    return date(MONTH_YEAR, MONTH_NO, day)


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
            "quality_inspector", "accountant", "buyer",
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

        # ---- Yarn stock ----
        yarn = [
            m.YarnStock(yarn_type="Cotton 30s", colour="White", quantity_kg=620,
                        reorder_level_kg=200, unit_cost=180),
            m.YarnStock(yarn_type="Polyester 150D", colour="Black", quantity_kg=360,
                        reorder_level_kg=150, unit_cost=140),
            m.YarnStock(yarn_type="Cotton 40s", colour="Blue", quantity_kg=90,
                        reorder_level_kg=150, unit_cost=200),  # LOW STOCK
            m.YarnStock(yarn_type="Viscose 20s", colour="Red", quantity_kg=260,
                        reorder_level_kg=100, unit_cost=160),
        ]
        db.add_all(yarn)
        db.flush()

        # ---- Orders (7) across stages — created through October ----
        # (order_no, buyer_idx, fabric, colour, qty_m, status, rate, created_day,
        #  deadline_day)
        order_specs = [
            ("ORD-2001", 0, "Cotton Shirting", "White", 2000, "closed", 95, 2, 16),
            ("ORD-2002", 1, "Silk Blend", "Black", 1200, "dispatched", 140, 4, 20),
            ("ORD-2003", 2, "Denim", "Blue", 3000, "in_quality", 120, 6, 24),
            ("ORD-2004", 3, "Cotton Poplin", "Red", 1500, "in_production", 110, 8, 26),
            ("ORD-2005", 4, "Polyester Lining", "Black", 1800, "confirmed", 80, 12, 28),
            ("ORD-2006", 0, "Viscose Crepe", "Red", 900, "in_production", 130, 14, 30),
            ("ORD-2007", 2, "Cotton Twill", "White", 2200, "dispatched", 100, 3, 18),
        ]
        orders = []
        for (no, bi, fabric, colour, qty, status, rate, cday, dday) in order_specs:
            orders.append(m.Order(
                order_no=no, buyer_id=buyers[bi].id, fabric_type=fabric,
                colour=colour, quantity_meters=qty, status=status, unit_price=rate,
                deadline=_d(dday), created_at=_dt(cday)))
        db.add_all(orders)
        db.flush()
        O = {o.order_no: o for o in orders}

        # ---- Yarn receipts LINKED TO ORDERS (fixes Yarn ₹0) ----
        # qty_kg ≈ 0.2 kg per metre of fabric. Each receipt carries its rate.
        receipts = [
            # order_no, supplier_idx, yarn_type, colour, qty_kg, rate, day
            ("ORD-2001", 0, "Cotton 30s", "White", 400, 180, 2),
            ("ORD-2002", 1, "Polyester 150D", "Black", 240, 140, 4),
            ("ORD-2003", 2, "Cotton 40s", "Blue", 600, 205, 6),
            ("ORD-2004", 0, "Cotton 30s", "Red", 300, 175, 8),
            ("ORD-2006", 2, "Viscose 20s", "Red", 180, 160, 14),
            ("ORD-2007", 0, "Cotton 30s", "White", 440, 182, 3),
        ]
        for (ono, si, yt, col, qkg, rate, day) in receipts:
            db.add(m.YarnReceipt(
                yarn_stock_id=None, supplier_id=suppliers[si].id,
                purchase_order_id=None, order_id=O[ono].id,
                yarn_type=yt, colour=col, quantity_kg=qkg, unit_cost=rate,
                received_at=_dt(day)))

        # Order items (yarn requirement per order)
        db.add_all([
            m.OrderItem(order_id=O["ORD-2001"].id, yarn_stock_id=yarn[0].id,
                        yarn_type="Cotton 30s", colour="White",
                        required_qty_kg=400, allocated_qty_kg=400),
            m.OrderItem(order_id=O["ORD-2003"].id, yarn_stock_id=yarn[2].id,
                        yarn_type="Cotton 40s", colour="Blue",
                        required_qty_kg=600, allocated_qty_kg=90),
            m.OrderItem(order_id=O["ORD-2004"].id, yarn_stock_id=yarn[3].id,
                        yarn_type="Viscose 20s", colour="Red",
                        required_qty_kg=300, allocated_qty_kg=300),
        ])

        # ---- Machines (8). hourly_cost = POWER + OVERHEAD ONLY (no wages) ----
        machines = [
            m.Machine(name="Spin-01", type="spinning", current_status="running", hourly_cost=120),
            m.Machine(name="Spin-02", type="spinning", current_status="idle", hourly_cost=120),
            m.Machine(name="Spin-03", type="spinning", current_status="breakdown", hourly_cost=120),
            m.Machine(name="Weave-01", type="weaving", current_status="running", hourly_cost=180),
            m.Machine(name="Weave-02", type="weaving", current_status="running", hourly_cost=180),
            m.Machine(name="Weave-03", type="weaving", current_status="idle", hourly_cost=180),
            m.Machine(name="Dye-01", type="dyeing", current_status="running", hourly_cost=240),
            m.Machine(name="Dye-02", type="dyeing", current_status="idle", hourly_cost=240),
        ]
        db.add_all(machines)
        db.flush()
        M = {mc.name: mc for mc in machines}

        # ---- Machine status logs (idle + breakdown windows, dated in-month) ----
        db.add_all([
            m.MachineStatusLog(machine_id=M["Spin-02"].id, status="idle",
                               start_time=_dt(28, 6), end_time=_dt(28, 9),
                               reason="No order assigned"),
            m.MachineStatusLog(machine_id=M["Spin-02"].id, status="idle",
                               start_time=_dt(28, 9), end_time=_dt(28, 11),
                               reason="Waiting for yarn"),
            m.MachineStatusLog(machine_id=M["Spin-03"].id, status="breakdown",
                               start_time=_dt(28, 8), end_time=_dt(28, 12),
                               reason="Motor fault"),
            m.MachineStatusLog(machine_id=M["Weave-03"].id, status="idle",
                               start_time=_dt(28, 10), end_time=_dt(28, 12),
                               reason="Shift changeover"),
            m.MachineStatusLog(machine_id=M["Dye-02"].id, status="idle",
                               start_time=_dt(28, 13), end_time=_dt(28, 15),
                               reason="Cleaning"),
            m.MachineStatusLog(machine_id=M["Weave-01"].id, status="running",
                               start_time=_dt(28, 6), end_time=_dt(28, 14),
                               reason="Order ORD-2003"),
        ])

        # Assign current orders to running machines
        M["Spin-01"].current_order_id = O["ORD-2004"].id
        M["Spin-01"].current_stage = "spinning"
        M["Weave-01"].current_order_id = O["ORD-2003"].id
        M["Weave-01"].current_stage = "weaving"
        M["Weave-02"].current_order_id = O["ORD-2004"].id
        M["Weave-02"].current_stage = "weaving"
        M["Dye-01"].current_order_id = O["ORD-2003"].id
        M["Dye-01"].current_stage = "dyeing"

        # ---- Production logs (metres produced per machine/order, in-month) ----
        prod = [
            ("Weave-01", "ORD-2001", "weaving", 2000, 15),
            ("Dye-01", "ORD-2002", "dyeing", 1200, 18),
            ("Weave-01", "ORD-2003", "weaving", 1800, 22),
            ("Dye-01", "ORD-2003", "dyeing", 1500, 23),
            ("Weave-02", "ORD-2004", "weaving", 700, 25),
            ("Spin-01", "ORD-2004", "spinning", 500, 25),
            ("Weave-02", "ORD-2006", "weaving", 300, 29),
            ("Weave-01", "ORD-2007", "weaving", 2200, 17),
        ]
        for (mn, ono, stage, out, day) in prod:
            db.add(m.ProductionLog(machine_id=M[mn].id, order_id=O[ono].id,
                                   stage=stage, output_meters=out, log_date=_d(day)))

        # ---- Rolls + quality for ORD-2001, 2002, 2003, 2007 ----
        def add_rolls(order_no, machine_name, n, status, start):
            out = []
            for i in range(n):
                out.append(m.Roll(order_id=O[order_no].id,
                                  machine_id=M[machine_name].id,
                                  roll_no=f"R-{start + i:04d}", length_meters=50,
                                  status=status, created_at=_dt(16)))
            db.add_all(out)
            return out

        add_rolls("ORD-2001", "Weave-01", 8, "pass", 1)
        d2002 = add_rolls("ORD-2002", "Dye-01", 6, "dispatched", 9)
        q2003 = add_rolls("ORD-2003", "Weave-01", 9, "pending", 15)
        d2007 = add_rolls("ORD-2007", "Weave-01", 10, "dispatched", 24)
        db.flush()

        mix = ["pass", "pass", "pass", "rework", "reject",
               "pass", "pending", "pending", "pass"]
        for r, res in zip(q2003, mix):
            r.status = res
        inspector = staff[3]
        defect_for = {"rework": "uneven_weaving", "reject": "hole"}
        for r in q2003:
            if r.status in ("pass", "rework", "reject"):
                db.add(m.QualityInspection(
                    roll_id=r.id, inspector_user_id=inspector.id, result=r.status,
                    defect_type=defect_for.get(r.status, "none"),
                    notes="Seeded inspection", inspected_at=_dt(23)))

        # ---- Dispatches + invoices for ORD-2002 and ORD-2007 ----
        def dispatch_order(order_no, rolls_list, dno, ino, day):
            o = O[order_no]
            total_m = sum(float(r.length_meters) for r in rolls_list)
            disp = m.Dispatch(order_id=o.id, buyer_id=o.buyer_id, dispatch_no=dno,
                              total_rolls=len(rolls_list), total_meters=total_m,
                              status="shipped", dispatched_at=_dt(day))
            db.add(disp)
            db.flush()
            for r in rolls_list:
                db.add(m.DispatchItem(dispatch_id=disp.id, roll_id=r.id,
                                      length_meters=r.length_meters))
            subtotal = total_m * float(o.unit_price)
            tax = round(subtotal * 0.05, 2)
            inv = m.Invoice(order_id=o.id, dispatch_id=disp.id, buyer_id=o.buyer_id,
                            invoice_no=ino, subtotal=subtotal, tax=tax,
                            total=round(subtotal + tax, 2), status="unpaid",
                            created_at=_dt(day))
            db.add(inv)
            db.flush()
            return inv

        inv2002 = dispatch_order("ORD-2002", d2002, "DSP-3001", "INV-4001", 20)
        inv2007 = dispatch_order("ORD-2007", d2007, "DSP-3002", "INV-4002", 18)

        # ---- Payments (realistic, in-month) ----
        # Buyer payments IN
        db.add(m.Payment(direction="incoming", buyer_id=O["ORD-2002"].buyer_id,
                         invoice_id=inv2002.id, amount=float(inv2002.total),
                         method="bank", paid_at=_dt(22)))          # fully paid
        db.add(m.Payment(direction="incoming", buyer_id=O["ORD-2007"].buyer_id,
                         invoice_id=inv2007.id,
                         amount=round(float(inv2007.total) * 0.5, 2),
                         method="upi", paid_at=_dt(21)))           # part paid
        inv2002.status = "paid"
        inv2007.status = "part_paid"

        # Supplier/raw-material bills paid OUT (sensible amounts)
        db.add_all([
            m.Payment(direction="outgoing", supplier_id=suppliers[0].id,
                      amount=72000, method="bank", paid_at=_dt(5)),
            m.Payment(direction="outgoing", supplier_id=suppliers[1].id,
                      amount=33600, method="bank", paid_at=_dt(7)),
            m.Payment(direction="outgoing", supplier_id=suppliers[0].id,
                      amount=80080, method="bank", paid_at=_dt(9)),
        ])

        # ---- Employees + attendance + wages (PAID in month) ----
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

        # Attendance for two weeks in October
        for emp in employees:
            for day in range(1, 15):
                db.add(m.Attendance(
                    employee_id=emp.id, work_date=_d(day), shift="morning",
                    status="present" if day % 7 != 0 else "half_day",
                    hours_worked=8 if day % 7 != 0 else 4))

        # Two paid wage runs (week 1 and week 2) — PAID inside the month.
        wage_runs = [
            (_d(1), _d(7), 6.0, 7),    # week1 period, paid day 7
            (_d(8), _d(14), 6.0, 15),  # week2 period, paid day 15
        ]
        for (ps, pe, days, pay_day) in wage_runs:
            for emp in employees:
                db.add(m.Wage(
                    employee_id=emp.id, period_start=ps, period_end=pe,
                    days_present=days, amount=round(float(emp.daily_wage) * days, 2),
                    status="paid", paid_at=_dt(pay_day)))

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
        "yarn_receipts": db.query(m.YarnReceipt).count(),
        "machines": db.query(m.Machine).count(),
        "orders": db.query(m.Order).count(),
        "production_logs": db.query(m.ProductionLog).count(),
        "rolls": db.query(m.Roll).count(),
        "dispatches": db.query(m.Dispatch).count(),
        "invoices": db.query(m.Invoice).count(),
        "payments": db.query(m.Payment).count(),
        "employees": db.query(m.Employee).count(),
        "wages": db.query(m.Wage).count(),
    }
    for k, v in counts.items():
        print(f"  {k:18} {v}")


if __name__ == "__main__":
    seed()

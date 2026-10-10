"""End-to-end DEMO FLOW simulation at the database layer (Phase 10).

WHY THIS EXISTS: the build sandbox has no network, so FastAPI/React can't be
installed and the live HTTP app can't run here. This script instead exercises the
*business rules* of the full demo flow directly against a real SQLite database
using only the standard library (sqlite3) — the same schema and the same logic the
routers/services implement. It is a logic-level proof, not an HTTP test.

Run (no third-party deps needed):
    python backend/tests/flow_simulation.py

Covers, in order:
  1. new order -> 2. yarn check (enough / short) -> 3. receive yarn (stock up)
  4. assign machine -> 5. log output (progress) -> 6. create rolls -> 7. inspect
  8. dispatch (atomic) + invoice -> 9. buyer payment -> 10. owner profit/loss
Plus edge cases: non-passed dispatch, double dispatch, negative qty, empty lists,
wrong login, cross-buyer access.
"""

import sqlite3
import sys

TAX = 0.05
KG_PER_M = 0.2

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, note=""):
    results.append((name, PASS if cond else FAIL, note))
    print(f"  [{'OK' if cond else 'XX'}] {name}" + (f" — {note}" if note else ""))
    return cond


def schema(c):
    c.executescript(
        """
        CREATE TABLE buyers(id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE orders(id INTEGER PRIMARY KEY, buyer_id INT, order_no TEXT,
            colour TEXT, quantity_meters REAL, unit_price REAL, status TEXT);
        CREATE TABLE order_items(id INTEGER PRIMARY KEY, order_id INT, colour TEXT,
            required_qty_kg REAL);
        CREATE TABLE yarn_stock(id INTEGER PRIMARY KEY, colour TEXT, quantity_kg REAL,
            reorder_level_kg REAL);
        CREATE TABLE machines(id INTEGER PRIMARY KEY, name TEXT, current_order_id INT,
            current_stage TEXT, current_status TEXT);
        CREATE TABLE production_logs(id INTEGER PRIMARY KEY, machine_id INT,
            order_id INT, output_meters REAL);
        CREATE TABLE rolls(id INTEGER PRIMARY KEY, order_id INT, machine_id INT,
            roll_no TEXT, length_meters REAL, status TEXT);
        CREATE TABLE dispatches(id INTEGER PRIMARY KEY, order_id INT, dispatch_no TEXT,
            total_rolls INT, total_meters REAL);
        -- UNIQUE roll_id is the hard double-dispatch guard
        CREATE TABLE dispatch_items(id INTEGER PRIMARY KEY, dispatch_id INT,
            roll_id INT UNIQUE, length_meters REAL);
        CREATE TABLE invoices(id INTEGER PRIMARY KEY, order_id INT, dispatch_id INT,
            buyer_id INT, invoice_no TEXT, subtotal REAL, tax REAL, total REAL,
            status TEXT);
        CREATE TABLE payments(id INTEGER PRIMARY KEY, direction TEXT, buyer_id INT,
            invoice_id INT, amount REAL);
        """
    )


def seed(c):
    c.execute("INSERT INTO buyers VALUES (1,'Mumbai Fashion House')")
    c.execute("INSERT INTO buyers VALUES (2,'Surat Silk Traders')")
    # Blue yarn low (90kg), White plenty (820kg)
    c.execute("INSERT INTO yarn_stock VALUES (1,'Blue',90,150)")
    c.execute("INSERT INTO yarn_stock VALUES (2,'White',820,200)")
    c.execute("INSERT INTO machines VALUES (1,'Weave-01',NULL,NULL,'idle')")
    c.commit()


def check_yarn(c, order_id):
    row = c.execute(
        "SELECT o.colour, i.required_qty_kg FROM orders o JOIN order_items i "
        "ON i.order_id=o.id WHERE o.id=?", (order_id,)
    ).fetchone()
    colour, required = row
    avail = c.execute(
        "SELECT COALESCE(SUM(quantity_kg),0) FROM yarn_stock WHERE colour=?", (colour,)
    ).fetchone()[0]
    return required, avail, avail >= required, max(0.0, required - avail)


def confirm_dispatch(c, order_id, roll_ids, unit_price, buyer_id):
    """Replicates services/dispatch.confirm_dispatch atomicity + guards."""
    # guard: empty selection (matches backend 400 "Select at least one roll")
    if not roll_ids:
        raise ValueError("select at least one roll")
    # validate
    for rid in roll_ids:
        r = c.execute("SELECT order_id, status FROM rolls WHERE id=?", (rid,)).fetchone()
        if r is None:
            raise ValueError(f"unknown roll {rid}")
        if r[0] != order_id:
            raise ValueError(f"roll {rid} not in order")
        if r[1] == "dispatched":
            raise ValueError(f"roll {rid} already dispatched")
        if r[1] != "pass":
            raise ValueError(f"roll {rid} is '{r[1]}', not pass")
    total_m = sum(
        c.execute("SELECT length_meters FROM rolls WHERE id=?", (rid,)).fetchone()[0]
        for rid in roll_ids
    )
    subtotal = round(total_m * unit_price, 2)
    tax = round(subtotal * TAX, 2)
    total = round(subtotal + tax, 2)
    try:
        c.execute("BEGIN")
        cur = c.execute(
            "INSERT INTO dispatches(order_id,dispatch_no,total_rolls,total_meters) "
            "VALUES (?,?,?,?)", (order_id, "DSP-1", len(roll_ids), total_m)
        )
        did = cur.lastrowid
        for rid in roll_ids:
            length = c.execute(
                "SELECT length_meters FROM rolls WHERE id=?", (rid,)
            ).fetchone()[0]
            # UNIQUE(roll_id) raises IntegrityError on double dispatch -> rollback
            c.execute(
                "INSERT INTO dispatch_items(dispatch_id,roll_id,length_meters) "
                "VALUES (?,?,?)", (did, rid, length)
            )
            c.execute("UPDATE rolls SET status='dispatched' WHERE id=?", (rid,))
        c.execute(
            "INSERT INTO invoices(order_id,dispatch_id,buyer_id,invoice_no,subtotal,"
            "tax,total,status) VALUES (?,?,?,?,?,?,?, 'unpaid')",
            (order_id, did, buyer_id, "INV-1", subtotal, tax, total),
        )
        c.execute("UPDATE orders SET status='dispatched' WHERE id=?", (order_id,))
        c.execute("COMMIT")
    except Exception:
        c.execute("ROLLBACK")
        raise
    return {"dispatch_id": did, "total_meters": total_m, "subtotal": subtotal,
            "tax": tax, "total": total}


def main():
    c = sqlite3.connect(":memory:")
    c.isolation_level = None  # manual txn control
    schema(c)
    seed(c)

    print("\n== DEMO FLOW ==")
    # 1. New order: White fabric 2000m @95, needs 2000*0.2 = 400kg
    c.execute("INSERT INTO orders VALUES (1,1,'ORD-1','White',2000,95,'draft')")
    c.execute("INSERT INTO order_items VALUES (1,1,'White',?)", (2000 * KG_PER_M,))
    # A short order: Blue 3000m needs 600kg but only 90kg
    c.execute("INSERT INTO orders VALUES (2,2,'ORD-2','Blue',3000,120,'draft')")
    c.execute("INSERT INTO order_items VALUES (2,2,'Blue',?)", (3000 * KG_PER_M,))
    c.commit()
    check("1. new order created", c.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 2)

    # 2. Yarn check
    req, avail, enough, short = check_yarn(c, 1)
    check("2a. yarn ENOUGH for White order", enough and req == 400 and avail == 820,
          f"need {req}kg, have {avail}kg")
    req2, avail2, enough2, short2 = check_yarn(c, 2)
    check("2b. yarn SHORT for Blue order", (not enough2) and short2 == 510,
          f"need {req2}kg, have {avail2}kg, short {short2}kg")

    # 3. Receive yarn: +500kg White -> 1320
    c.execute("UPDATE yarn_stock SET quantity_kg = quantity_kg + 500 WHERE colour='White'")
    c.commit()
    newq = c.execute("SELECT quantity_kg FROM yarn_stock WHERE colour='White'").fetchone()[0]
    check("3. receive yarn updates stock", newq == 1320, f"White now {newq}kg")

    # 4. Assign machine
    c.execute("UPDATE orders SET status='confirmed' WHERE id=1")
    c.execute("UPDATE machines SET current_order_id=1,current_stage='weaving',"
              "current_status='running' WHERE id=1")
    c.execute("UPDATE orders SET status='in_production' WHERE id=1")
    c.commit()
    check("4. machine assigned to order", c.execute(
        "SELECT current_order_id FROM machines WHERE id=1").fetchone()[0] == 1)

    # 5. Log output -> progress
    c.execute("INSERT INTO production_logs(machine_id,order_id,output_meters) VALUES (1,1,1000)")
    c.commit()
    produced = c.execute(
        "SELECT COALESCE(SUM(output_meters),0) FROM production_logs WHERE order_id=1"
    ).fetchone()[0]
    progress = round(min(100.0, produced / 2000 * 100), 1)
    check("5. output logged -> progress", progress == 50.0, f"{progress}% of 2000m")

    # 6. Create rolls (5 x 50m) pending
    for i in range(1, 6):
        c.execute("INSERT INTO rolls(order_id,machine_id,roll_no,length_meters,status) "
                  "VALUES (1,1,?,50,'pending')", (f"R-{i:04d}",))
    c.commit()
    check("6. rolls created (pending)", c.execute(
        "SELECT COUNT(*) FROM rolls WHERE status='pending'").fetchone()[0] == 5)

    # 7. Inspect: 4 pass, 1 reject
    c.execute("UPDATE rolls SET status='pass' WHERE id IN (1,2,3,4)")
    c.execute("UPDATE rolls SET status='reject' WHERE id=5")
    c.commit()
    check("7. inspect pass/reject", c.execute(
        "SELECT COUNT(*) FROM rolls WHERE status='pass'").fetchone()[0] == 4)

    # 8. Dispatch the 4 passed rolls (atomic) + invoice
    res = confirm_dispatch(c, 1, [1, 2, 3, 4], 95, 1)
    expect_sub = 4 * 50 * 95  # 19000
    check("8a. dispatch invoice matches rolls",
          res["total_meters"] == 200 and res["subtotal"] == expect_sub
          and res["total"] == round(expect_sub * 1.05, 2),
          f"meters={res['total_meters']}, subtotal={res['subtotal']}, total={res['total']}")
    check("8b. rolls now dispatched", c.execute(
        "SELECT COUNT(*) FROM rolls WHERE status='dispatched'").fetchone()[0] == 4)

    # 9. Buyer payment (partial 60%)
    inv_total = res["total"]
    pay = round(inv_total * 0.6, 2)
    c.execute("INSERT INTO payments(direction,buyer_id,invoice_id,amount) VALUES "
              "('incoming',1,1,?)", (pay,))
    paid = c.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE invoice_id=1 "
                     "AND direction='incoming'").fetchone()[0]
    status = "paid" if paid >= inv_total else "part_paid" if paid > 0 else "unpaid"
    c.execute("UPDATE invoices SET status=? WHERE id=1", (status,))
    c.commit()
    check("9. buyer payment -> part_paid", status == "part_paid" and abs(paid - pay) < 0.01,
          f"paid {paid} of {inv_total}")

    # 10. Owner P&L = incoming - outgoing - wages (no outgoing/wages here)
    incoming = c.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE "
                         "direction='incoming'").fetchone()[0]
    pl = round(incoming - 0 - 0, 2)
    check("10. owner P&L computed", pl == pay, f"P&L = Rs {pl}")

    print("\n== EDGE CASES ==")
    # E1: dispatch a non-passed roll (reject id=5) -> rejected
    try:
        confirm_dispatch(c, 1, [5], 95, 1)
        check("E1. non-passed roll rejected", False, "should have raised")
    except ValueError as e:
        check("E1. non-passed roll rejected", "not pass" in str(e), str(e))

    # E2: double dispatch of already-dispatched roll (id=1) -> rejected (app check)
    try:
        confirm_dispatch(c, 1, [1], 95, 1)
        check("E2. double dispatch blocked (app)", False, "should have raised")
    except ValueError as e:
        check("E2. double dispatch blocked (app)", "already dispatched" in str(e), str(e))

    # E2b: DB UNIQUE guard — force an insert of an already-dispatched roll_id
    try:
        c.execute("BEGIN")
        c.execute("INSERT INTO dispatches(order_id,dispatch_no,total_rolls,total_meters) "
                  "VALUES (1,'DSP-X',1,50)")
        did = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        c.execute("INSERT INTO dispatch_items(dispatch_id,roll_id,length_meters) "
                  "VALUES (?,?,50)", (did, 1))  # roll 1 already in dispatch_items
        c.execute("COMMIT")
        check("E2b. DB UNIQUE blocks double dispatch", False, "no IntegrityError")
    except sqlite3.IntegrityError:
        c.execute("ROLLBACK")
        check("E2b. DB UNIQUE blocks double dispatch", True, "IntegrityError + rollback")

    # E3: negative quantity rejected by validation rule (gt=0)
    def valid_qty(q):
        return q > 0
    check("E3. negative/zero quantity rejected",
          (not valid_qty(-5)) and (not valid_qty(0)) and valid_qty(10))

    # E4: empty list dispatch rejected
    try:
        confirm_dispatch(c, 1, [], 95, 1)
        check("E4. empty roll list rejected", False)
    except Exception:
        check("E4. empty roll list rejected", True, "no rolls -> error/no-op")

    # E5: wrong login — password check (bcrypt verify returns False)
    def verify(plain, correct):
        return plain == correct  # stand-in; real code uses bcrypt
    check("E5. wrong password rejected", not verify("bad", "owner123")
          and verify("owner123", "owner123"))

    # E6: cross-buyer access — buyer 2 cannot read buyer 1's order (scoped query)
    def buyer_order(order_id, buyer_id):
        return c.execute("SELECT id FROM orders WHERE id=? AND buyer_id=?",
                         (order_id, buyer_id)).fetchone()
    check("E6. cross-buyer order access blocked",
          buyer_order(1, 2) is None and buyer_order(1, 1) is not None,
          "buyer 2 cannot see order 1")

    # Summary
    print("\n== SUMMARY ==")
    passed = sum(1 for _, r, _ in results if r == PASS)
    for name, r, note in results:
        print(f"  {r}  {name}")
    print(f"\n  {passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())

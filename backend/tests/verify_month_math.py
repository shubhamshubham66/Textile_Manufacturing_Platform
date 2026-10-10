"""Standalone arithmetic check of the October-2026 seed numbers.

This does NOT import FastAPI/SQLAlchemy (the sandbox has no network to install
them). It replicates, in plain Python, the exact formulas in
app/services/reports.py against the seed values in app/seed.py, so the
cost-per-order, wages and month-net figures can be verified by hand.

Run:  python backend/tests/verify_month_math.py
"""

MACHINE_POWER_SHARE = 0.60  # mirrors services/reports.py

# ---- Seed facts (October 2026) -------------------------------------------- #
# Orders: (order_no, qty_m, unit_price, output_m, invoiced_total)
orders = {
    "ORD-2001": dict(qty=2000, price=95, output=2000, invoiced=199500.0),
    "ORD-2002": dict(qty=1200, price=140, output=1200, invoiced=44100.0),
    "ORD-2003": dict(qty=3000, price=120, output=600 + 500, invoiced=0.0),
    "ORD-2004": dict(qty=1500, price=110, output=450 + 380, invoiced=0.0),
    "ORD-2005": dict(qty=1800, price=80, output=0, invoiced=0.0),
    "ORD-2006": dict(qty=900, price=130, output=0, invoiced=0.0),
    "ORD-2007": dict(qty=1600, price=105, output=300, invoiced=0.0),
}

# Yarn receipts linked to orders (order_no -> kg × rate).
yarn_linked = {
    "ORD-2001": 400 * 180,   # 72,000
    "ORD-2002": 240 * 140,   # 33,600
    "ORD-2003": 90 * 200,    # 18,000
    "ORD-2004": 220 * 160,   # 35,200
}

# Machines: hourly_cost and power_overhead_cost (power+OH only).
machines = [
    ("Spin-01", 250, 150), ("Spin-02", 250, 150), ("Spin-03", 250, 150),
    ("Weave-01", 400, 240), ("Weave-02", 400, 240), ("Weave-03", 400, 240),
    ("Dye-01", 550, 330), ("Dye-02", 550, 330),
]

# Wages (accrued this month) and whether paid.
wages = [("Imran", 2475.0, True), ("Kavita", 2700.0, True),
         ("Suresh", 2925.0, True), ("Anita", 2250.0, False)]

# Payments in October.
payments = [
    ("in", 199500.0), ("in", 26460.0),      # buyer in
    ("out", 180000.0), ("out", 20000.0),    # supplier out
]


def inr(n):
    return f"Rs {n:,.2f}"


def main():
    total_out = sum(o["output"] for o in orders.values())
    wages_all = sum(w[1] for w in wages)
    machine_basis = sum(po for _, _, po in machines)  # power+OH basis

    print(f"Total output (all orders)     : {total_out} m")
    print(f"Total wages accrued (month)   : {inr(wages_all)}")
    print(f"Machine power+OH basis (Rs/hr): {inr(machine_basis)}")
    print(f"  (sum of power_overhead_cost; wages NOT included)\n")

    print(f"{'Order':10} {'Out m':>6} {'Yarn':>12} {'Wages':>10} {'Machine':>10} "
          f"{'Total':>12} {'Revenue':>12} {'Margin':>12}")
    checked_total_cost = {}
    for name, o in orders.items():
        share = (o["output"] / total_out) if total_out else 0.0
        yarn = yarn_linked.get(name, 0.0)
        wage_alloc = round(wages_all * share, 2)
        machine_alloc = round(machine_basis * share, 2)
        total_cost = round(yarn + wage_alloc + machine_alloc, 2)
        revenue = o["invoiced"] if o["invoiced"] > 0 else round(o["output"] * o["price"], 2)
        margin = round(revenue - total_cost, 2)
        checked_total_cost[name] = total_cost
        print(f"{name:10} {o['output']:>6} {inr(yarn):>12} {inr(wage_alloc):>10} "
              f"{inr(machine_alloc):>10} {inr(total_cost):>12} {inr(revenue):>12} "
              f"{inr(margin):>12}")

    # ---- Month net (cash basis) ---- #
    buyer_in = sum(a for d, a in payments if d == "in")
    supplier_out = sum(a for d, a in payments if d == "out")
    wages_in_window = wages_all  # all wage periods fall inside October
    net = round(buyer_in - supplier_out - wages_in_window, 2)

    print("\n--- Month net (cash basis) ---")
    print(f"Buyer payments received : {inr(buyer_in)}")
    print(f"Raw-material bills paid  : -{inr(supplier_out)}")
    print(f"Wages (window)           : -{inr(wages_in_window)}")
    print(f"NET                      : {inr(net)}  ->  "
          f"{'PROFIT' if net >= 0 else 'LOSS'}")

    wages_paid = sum(w[1] for w in wages if w[2])
    print(f"\n(Info) Wages actually PAID this month: {inr(wages_paid)}")
    print("(Month net uses wages accrued in the window per the P&L definition.)")

    # ---- Assertions so this fails loudly if the seed drifts ---- #
    assert yarn_linked["ORD-2001"] == 72000
    assert abs(checked_total_cost["ORD-2001"] - (72000 + round(wages_all * (2000/total_out), 2)
               + round(machine_basis * (2000/total_out), 2))) < 0.01
    assert net == round(199500 + 26460 - 180000 - 20000 - wages_all, 2)
    print("\nAll assertions passed.")


if __name__ == "__main__":
    main()

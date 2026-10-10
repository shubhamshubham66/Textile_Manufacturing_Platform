"""Standalone arithmetic check of the October-2026 seed numbers.

Plain Python, no FastAPI/SQLAlchemy: it re-does by hand the formulas in
app/services/reports.py on the seed values in app/seed.py, so the cost-per-order,
machine, wages and month-net figures can be checked without a server. The same
numbers are asserted against the real API in tests/test_owner_reports.py.

Run:  python backend/tests/verify_month_math.py
"""

# ---- Seed facts (October 2026) -------------------------------------------- #
orders = {  # output metres made in October, invoiced in October
    "ORD-2001": dict(output=2000, invoiced=199500.0),
    "ORD-2002": dict(output=1200, invoiced=44100.0),
    "ORD-2003": dict(output=600 + 500, invoiced=0.0, price=120),
    "ORD-2004": dict(output=450 + 380, invoiced=0.0, price=110),
    "ORD-2007": dict(output=300, invoiced=0.0, price=105),
}
yarn_linked = {"ORD-2001": 400 * 180, "ORD-2002": 240 * 140}  # kg × ₹/kg, received in October

# Machine running hours in October × power+overhead ₹/hr, and metres per order.
machine = {
    "Weave-01": dict(hours=10 + 6, rate=240, made={"ORD-2001": 2000, "ORD-2003": 600}),
    "Weave-02": dict(hours=8 + 4, rate=240, made={"ORD-2002": 1200, "ORD-2004": 450}),
}

wages = [("Imran", 2475.0, True), ("Kavita", 2700.0, True), ("Suresh", 2925.0, True), ("Anita", 2250.0, False)]
buyer_in = 199500.0 + 26460.0
supplier_out = 180000.0 + 20000.0


def inr(v):
    return f"₹{v:,.2f}"


def main():
    total_out = sum(o["output"] for o in orders.values())  # 5,430
    wages_accrued = sum(w[1] for w in wages)  # 10,350
    wages_paid = sum(w[1] for w in wages if w[2])  # 8,100

    # Wages split by metres; the paise left over from rounding goes to the biggest share.
    parts = {k: round(wages_accrued * o["output"] / total_out, 2) for k, o in orders.items()}
    big = max(parts, key=parts.get)
    parts[big] = round(parts[big] + round(wages_accrued - sum(parts.values()), 2), 2)

    for order_no in ("ORD-2001", "ORD-2002"):
        yarn = yarn_linked[order_no]
        wage = parts[order_no]
        mach = 0.0
        for mc in machine.values():
            if order_no in mc["made"]:
                mach += mc["hours"] * mc["rate"] * mc["made"][order_no] / sum(mc["made"].values())
        mach = round(mach, 2)
        total = round(yarn + wage + mach, 2)
        rev = orders[order_no]["invoiced"]
        print(f"{order_no}: yarn {inr(yarn)} + wages {inr(wage)} + machine {inr(mach)} = {inr(total)};"
              f" revenue {inr(rev)}; margin {inr(round(rev - total, 2))}")

    net = round(buyer_in - supplier_out - wages_paid, 2)
    print(f"Month net = {inr(buyer_in)} − {inr(supplier_out)} − {inr(wages_paid)} = {inr(net)}")
    print(f"Wages due (not in cash net): {inr(wages_accrued - wages_paid)}")
    print(f"Wages split adds up: {inr(sum(parts.values()))} == {inr(wages_accrued)}")
    assert net == 17860.00
    assert round(sum(parts.values()), 2) == wages_accrued


if __name__ == "__main__":
    main()

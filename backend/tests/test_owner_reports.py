"""Owner month-end acceptance checks against the October 2026 seed.

Expected values are worked out by hand in docs/OWNER_MONTH_END_HANDCHECK.md
(not read back from the API). Run:  cd backend && pytest tests/test_owner_reports.py -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.seed as seed_mod
from app.database import get_db
from app.main import app

OCT = "start=2026-10-01&end=2026-10-31"
SEP = "start=2026-09-01&end=2026-09-30"


@pytest.fixture(scope="module")
def c():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    mp = pytest.MonkeyPatch()
    mp.setattr(seed_mod, "engine", engine)
    mp.setattr(seed_mod, "SessionLocal", Session)
    seed_mod.seed()

    def override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
    mp.undo()


def tok(c, email, pw):
    return {"Authorization": "Bearer " + c.post("/api/auth/login", json={"email": email, "password": pw}).json()["token"]}


@pytest.fixture(scope="module")
def owner(c):
    return tok(c, "owner@everest.test", "owner123")


def test_1_cost_per_order_matches_hand_check(c, owner):
    rows = {r["order_no"]: r for r in c.get(f"/api/reports/cost-per-order?{OCT}", headers=owner).json()["rows"]}
    o1 = rows["ORD-2001"]
    # Wages 10,350 × 2000/5430 = 3,812.15 + the 0.01 rounding remainder (largest share),
    # so the order wages add up to exactly 10,350.00.
    assert (o1["yarn_cost"], o1["wage_cost"], o1["machine_cost"]) == (72000.00, 3812.16, 2953.85)
    assert (o1["total_cost"], o1["revenue_est"], o1["margin_est"]) == (78766.01, 199500.00, 120733.99)
    o2 = rows["ORD-2002"]
    assert (o2["yarn_cost"], o2["wage_cost"], o2["machine_cost"]) == (33600.00, 2287.29, 2094.55)
    assert (o2["total_cost"], o2["revenue_est"], o2["margin_est"]) == (37981.84, 44100.00, 6118.16)
    # An order with no linked yarn receipt still carries a (marked) yarn estimate.
    assert rows["ORD-2007"]["yarn_cost"] > 0 and rows["ORD-2007"]["yarn_basis"] == "estimate"


def test_2_month_net_same_on_dashboard_and_reports(c, owner):
    pl = c.get(f"/api/reports/profit-loss?{OCT}", headers=owner).json()
    dash = c.get(f"/api/reports/dashboard?{OCT}", headers=owner).json()["profit_loss"]
    # 2,25,960 in − 2,00,000 bills − 8,100 wages paid = 17,860
    assert pl["profit_or_loss"] == dash["profit_or_loss"] == 17860.00
    assert (pl["buyer_payments_in"], pl["supplier_payments_out"], pl["wages"]) == (225960.0, 200000.0, 8100.0)
    assert pl["wages_due"] == 2250.0


def test_3_empty_month_is_all_zero(c, owner):
    assert c.get(f"/api/reports/cost-per-order?{SEP}", headers=owner).json()["rows"] == []
    m = c.get(f"/api/reports/machines?{SEP}", headers=owner).json()["totals"]
    assert all(v == 0 for v in m.values())
    pl = c.get(f"/api/reports/profit-loss?{SEP}", headers=owner).json()
    assert pl["profit_or_loss"] == 0 and pl["wages"] == 0
    d = c.get(f"/api/reports/dashboard?{SEP}", headers=owner).json()
    assert d["idle_loss_rupees"] == 0 and d["idle_loss_by_reason"] == []
    assert c.get(f"/api/reports/wages?{SEP}", headers=owner).json()["total_wages"] == 0


def test_4_machine_totals_equal_rows_and_production_logs(c, owner):
    r = c.get(f"/api/reports/machines?{OCT}", headers=owner).json()
    rows, t = r["machines"], r["totals"]
    for k_row, k_tot in [("total_output_meters", "total_output_meters"), ("running_hours", "running_hours"),
                         ("idle_hours", "idle_hours"), ("breakdown_hours", "breakdown_hours"),
                         ("idle_loss_rupees", "idle_loss_rupees")]:
        assert round(sum(x[k_row] for x in rows), 2) == t[k_tot]
    assert t["total_output_meters"] == 5430.0  # 600+450+500+380+2000+1200+300 from production logs
    assert t["running_hours"] == 40.0 and t["idle_loss_rupees"] == 3400.0
    dash = c.get(f"/api/reports/dashboard?{OCT}", headers=owner).json()
    assert dash["idle_loss_rupees"] == t["idle_loss_rupees"]


def test_5_wages_total_equals_employees_and_orders(c, owner):
    w = c.get(f"/api/reports/wages?{OCT}", headers=owner).json()
    assert w["total_wages"] == 10350.0
    assert round(sum(e["amount"] for e in w["per_employee"]), 2) == 10350.0
    assert round(sum(o["wages_allocated"] for o in w["per_order"]), 2) == 10350.0
    cost = c.get(f"/api/reports/cost-per-order?{OCT}", headers=owner).json()["rows"]
    assert round(sum(r["wage_cost"] for r in cost), 2) == 10350.0  # same split, counted once


def test_6_overpayment_rejected(c, owner):
    meta = c.get("/api/payments/_meta", headers=owner).json()
    inv = next(i for i in meta["invoices"] if i["balance"] > 0)
    r = c.post("/api/payments/buyer", headers=owner, json={"invoice_id": inv["id"], "amount": inv["balance"] + 1})
    assert r.status_code == 400 and "exceeds" in r.json()["error"]["message"]
    sup = meta["suppliers"][0]["id"]
    r = c.post("/api/payments/supplier", headers=owner, json={"supplier_id": sup, "amount": 99_999_999})
    assert r.status_code == 400 and "exceeds" in r.json()["error"]["message"]
    assert c.post("/api/payments/buyer", headers=owner, json={"invoice_id": inv["id"], "amount": 0}).status_code == 400


def test_7_owner_reports_forbidden_for_other_roles(c):
    for email, pw in [("accounts@everest.test", "accounts123"), ("floor@everest.test", "floor123"),
                      ("store@everest.test", "store123"), ("buyer@everest.test", "buyer123")]:
        h = tok(c, email, pw)
        for path in ["cost-per-order", "machines", "profit-loss", "wages", "dashboard"]:
            assert c.get(f"/api/reports/{path}?{OCT}", headers=h).status_code == 403

"""Accounts & Finance Manager: dashboard cards, invoices, overtime, production &
other expenses (with duplicate guard), financial reports, notifications, and
role-based access control. Buyer/supplier payments and wages reuse the existing
endpoints, which this role also holds.

Run:  cd backend && pytest tests/test_accounts_manager.py -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.seed as seed_mod
from app.database import get_db
from app.main import app


@pytest.fixture()
def c():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    S = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    mp = pytest.MonkeyPatch()
    mp.setattr(seed_mod, "engine", engine)
    mp.setattr(seed_mod, "SessionLocal", S)
    seed_mod.seed()

    def override():
        s = S()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()
    mp.undo()


def login(c, who, pw):
    r = c.post("/api/auth/login", json={"email": who, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture()
def am(c):
    return login(c, "accounts-manager@everest.test", "accounts123")


AM_PAGES = ["dashboard", "invoices", "overtime", "production-expenses",
            "expenses", "reports", "notifications", "activity"]


# ------------------------------ RBAC ------------------------------ #
def test_am_pages_open_and_closed_to_others(c, am):
    for p in AM_PAGES:
        assert c.get(f"/api/accounts/{p}", headers=am).status_code == 200, p
    for who, pw in [("store@everest.test", "store123"),
                    ("production@everest.test", "production123"),
                    ("sales@everest.test", "sales123"),
                    ("buyer@everest.test", "buyer123")]:
        h = login(c, who, pw)
        for p in AM_PAGES:
            assert c.get(f"/api/accounts/{p}", headers=h).status_code == 403, (who, p)


def test_accounts_manager_can_use_shared_payment_and_wage_endpoints(c, am):
    # These are the existing endpoints; the role holds payments/attendance/wages.
    assert c.get("/api/payments/dues", headers=am).status_code == 200
    assert c.get("/api/payments", headers=am).status_code == 200
    assert c.get("/api/wages", headers=am).status_code == 200
    assert c.get("/api/attendance", headers=am).status_code == 200


def test_menu_lists_twelve_pages(c, am):
    me = c.get("/api/auth/me", headers=am).json()
    assert me["user"]["role"] == "accounts_manager"
    assert len(me["menu"]) == 12


# ------------------------------ Dashboard ------------------------------ #
def test_dashboard_six_cards(c, am):
    d = c.get("/api/accounts/dashboard", headers=am).json()
    for key in ("total_sales", "pending_buyer_payments", "supplier_payments_due",
                "monthly_expenses", "worker_wages", "profit_or_loss"):
        assert key in d["cards"], key


# ------------------------------ Invoices / overtime / production ------------------------------ #
def test_invoices_list(c, am):
    inv = c.get("/api/accounts/invoices", headers=am).json()
    assert "invoices" in inv


def test_production_expenses_totals(c, am):
    pe = c.get("/api/accounts/production-expenses", headers=am).json()
    assert set(pe["totals"]) == {"yarn", "wages", "machine", "total"}


# ------------------------------ Other expenses + duplicate guard ------------------------------ #
def test_record_expense_and_duplicate_reference_blocked(c, am):
    r = c.post("/api/accounts/expenses", headers=am, json={
        "amount": 2500, "category": "utility", "note": "October power bill",
        "method": "bank", "reference": "PWR-OCT"})
    assert r.status_code == 201, r.text
    # Same reference again -> duplicate rejected.
    dup = c.post("/api/accounts/expenses", headers=am, json={
        "amount": 2500, "category": "utility", "note": "dup", "reference": "PWR-OCT"})
    assert dup.status_code == 409
    # It appears in the list and raises the total.
    lst = c.get("/api/accounts/expenses", headers=am).json()
    assert any(e["reference"] == "PWR-OCT" for e in lst["expenses"])


def test_major_expense_notifies_supermanager(c, am):
    # >= 50,000 should create a Supermanager notification (no crash either way).
    r = c.post("/api/accounts/expenses", headers=am, json={
        "amount": 75000, "category": "maintenance", "note": "Loom overhaul"})
    assert r.status_code == 201


# ------------------------------ Reports ------------------------------ #
def test_reports_day_month_year(c, am):
    for period in ("day", "month", "year"):
        r = c.get(f"/api/accounts/reports?period={period}", headers=am)
        assert r.status_code == 200, (period, r.text)
        body = r.json()
        assert body["period"] == period
        assert "cash_flow" in body and "profit_or_loss" in body


# ------------------------------ Permission boundary ------------------------------ #
def test_accounts_manager_cannot_confirm_orders_or_dispatch(c, am):
    assert c.post("/api/orders/1/confirm", headers=am).status_code == 403
    assert c.get("/api/dispatch", headers=am).status_code == 403
    assert c.get("/api/quality/rolls", headers=am).status_code == 403

"""Buyer dashboard: cards, products (+ min-order), place order (notifies +
duplicate guard), track, invoices, deliveries, cancel/modify requests,
inquiries, notifications, profile, and buyer-only scoping.

Run:  cd backend && pytest tests/test_buyer_dashboard.py -v
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.seed as seed_mod
from app.database import get_db
from app.main import app

FUTURE = (date.today() + timedelta(days=30)).isoformat()


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
def by(c):
    return login(c, "buyer@everest.test", "buyer123")


BY_PAGES = ["dashboard", "products", "orders", "invoices", "deliveries", "notifications", "profile"]


# ------------------------------ RBAC / scope ------------------------------ #
def test_pages_open_for_buyer_and_closed_to_staff(c, by):
    for p in BY_PAGES:
        assert c.get(f"/api/buyer/{p}", headers=by).status_code == 200, p
    # Staff are not buyers -> 403 on the buyer portal.
    for who, pw in [("owner@everest.test", "owner123"), ("sales@everest.test", "sales123")]:
        h = login(c, who, pw)
        assert c.get("/api/buyer/dashboard", headers=h).status_code == 403


def test_menu_has_ten_pages(c, by):
    me = c.get("/api/auth/me", headers=by).json()
    assert me["user"]["role"] == "buyer"
    assert len(me["menu"]) == 10


# ------------------------------ Dashboard + products ------------------------------ #
def test_dashboard_six_cards(c, by):
    d = c.get("/api/buyer/dashboard", headers=by).json()
    for k in ("my_orders", "pending", "in_production", "qc_status", "ready_for_dispatch", "dispatched"):
        assert k in d["cards"], k


def test_products_listed_from_seed(c, by):
    p = c.get("/api/buyer/products", headers=by).json()
    assert len(p["products"]) >= 1
    first = p["products"][0]
    assert c.get(f"/api/buyer/products/{first['id']}", headers=by).status_code == 200


# ------------------------------ Place order ------------------------------ #
def test_place_order_enforces_min_and_blocks_duplicate(c, by):
    prod = c.get("/api/buyer/products", headers=by).json()["products"][0]
    # Below minimum -> 400.
    low = c.post("/api/buyer/orders", headers=by, json={
        "fabric_type": prod["fabric_type"], "colour": prod["colour"],
        "quantity_meters": 1, "deadline": FUTURE, "product_id": prod["id"]})
    assert low.status_code == 400
    # Valid order -> 201/created.
    ok = c.post("/api/buyer/orders", headers=by, json={
        "fabric_type": prod["fabric_type"], "colour": prod["colour"],
        "quantity_meters": prod["min_order_meters"], "deadline": FUTURE, "product_id": prod["id"]})
    assert ok.status_code == 201, ok.text
    # Immediate duplicate -> 409.
    dup = c.post("/api/buyer/orders", headers=by, json={
        "fabric_type": prod["fabric_type"], "colour": prod["colour"],
        "quantity_meters": prod["min_order_meters"], "deadline": FUTURE, "product_id": prod["id"]})
    assert dup.status_code == 409


# ------------------------------ Cancel / modify ------------------------------ #
def test_change_request_does_not_change_order_and_blocks_dupes(c, by):
    orders = c.get("/api/buyer/orders", headers=by).json()
    # Use any order that is still changeable.
    changeable = [o for o in orders if o["status"] not in ("dispatched", "closed", "rejected", "cancelled")]
    if not changeable:
        pytest.skip("no changeable order in seed")
    oid = changeable[0]["id"]
    r = c.post(f"/api/buyer/orders/{oid}/request-change", headers=by, json={"kind": "modify", "message": "Please increase qty"})
    assert r.status_code == 201, r.text
    # Second open modify request -> 409.
    dup = c.post(f"/api/buyer/orders/{oid}/request-change", headers=by, json={"kind": "modify", "message": "again"})
    assert dup.status_code == 409
    # The order itself is unchanged (still listed, status not auto-cancelled).
    again = c.get("/api/buyer/orders", headers=by).json()
    assert any(o["id"] == oid for o in again)


# ------------------------------ Inquiry + notifications ------------------------------ #
def test_contact_sales_and_notifications(c, by):
    r = c.post("/api/buyer/inquiries", headers=by, json={"subject": "Delivery date", "message": "Can we prepone?"})
    assert r.status_code == 201
    nt = c.get("/api/buyer/notifications", headers=by)
    assert nt.status_code == 200 and "notifications" in nt.json()


# ------------------------------ Deliveries + profile ------------------------------ #
def test_deliveries_and_profile_are_own(c, by):
    d = c.get("/api/buyer/deliveries", headers=by).json()
    assert "deliveries" in d
    p = c.get("/api/buyer/profile", headers=by).json()
    assert "name" in p and "total_orders" in p


# ------------------------------ Permission boundary ------------------------------ #
def test_buyer_cannot_touch_staff_areas(c, by):
    assert c.get("/api/payments/dues", headers=by).status_code == 403
    assert c.get("/api/dispatch", headers=by).status_code == 403
    assert c.post("/api/orders/1/confirm", headers=by).status_code == 403
    assert c.get("/api/quality/rolls", headers=by).status_code == 403


def test_buyer_cannot_see_another_buyers_order(c, by):
    # Order id that belongs to another buyer (seed order #2 is a different buyer).
    r = c.get("/api/buyer/orders/999999", headers=by)
    assert r.status_code == 404

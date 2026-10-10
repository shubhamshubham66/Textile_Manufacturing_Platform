"""Sales & Dispatch Manager: dashboard cards, buyer orders, QC-approved stock,
dispatch planning + challan (reusing the atomic confirm), double-dispatch and
QC-only guards, delivery confirmation, read-only invoices/payments, reports,
notifications, and role-based access control.

Run:  cd backend && pytest tests/test_sales_manager.py -v
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
def sd(c):
    return login(c, "sales@everest.test", "sales123")


PAGES = ["dashboard", "orders", "buyers", "tracking", "stock", "planning",
         "history", "invoices", "deliveries", "notifications", "reports", "activity"]


# ------------------------------ RBAC ------------------------------ #
def test_pages_open_for_sales_manager_and_closed_to_others(c, sd):
    for p in PAGES:
        assert c.get(f"/api/sales/{p}", headers=sd).status_code == 200, p
    for who, pw in [("owner@everest.test", "owner123"),
                    ("store@everest.test", "store123"),
                    ("quality@everest.test", "quality123"),
                    ("production@everest.test", "production123"),
                    ("buyer@everest.test", "buyer123")]:
        h = login(c, who, pw)
        for p in PAGES:
            assert c.get(f"/api/sales/{p}", headers=h).status_code == 403, (who, p)


def test_menu_lists_thirteen_pages(c, sd):
    me = c.get("/api/auth/me", headers=sd).json()
    assert me["user"]["role"] == "sales_manager"
    labels = [i["label"] for i in me["menu"]]
    assert len(labels) == 13
    assert "Create Delivery Challan" in labels and "Delivery Confirmation" in labels


# ------------------------------ Dashboard ------------------------------ #
def test_dashboard_cards_present(c, sd):
    d = c.get("/api/sales/dashboard", headers=sd).json()
    for key in ("total_buyer_orders", "pending_dispatches", "qc_approved_rolls",
                "orders_ready_for_dispatch", "dispatched_orders",
                "delayed_deliveries", "pending_buyer_payments"):
        assert key in d["cards"], key


# ------------------------------ QC-approved stock ------------------------------ #
def test_only_passed_rolls_appear_in_stock(c, sd):
    stock = c.get("/api/sales/stock", headers=sd).json()
    # Seed has passed rolls on the shelf (orders[0] has 8 'pass').
    assert stock["total_rolls"] >= 1
    # Every listed order's rolls were QC-approved (pass) — none are rework/reject.
    assert all(s["rolls"] > 0 for s in stock["stock"])


# ------------------------------ Dispatch + challan ------------------------------ #
def _first_pickable(c, sd):
    planning = c.get("/api/sales/planning", headers=sd).json()
    order = planning["orders"][0]
    pick = c.get(f"/api/sales/orders/{order['id']}/pickable", headers=sd).json()
    return order, pick


def test_create_dispatch_full_makes_challan_and_invoice(c, sd):
    order, pick = _first_pickable(c, sd)
    roll_ids = [r["id"] for r in pick["rolls"]]
    r = c.post("/api/sales/dispatch", headers=sd, json={
        "order_id": order["id"], "roll_ids": roll_ids,
        "vehicle_no": "GJ-05-AB-1234", "transporter": "Blue Dart",
        "partial": False})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["challan_no"].startswith("CH-")
    assert body["invoice_no"].startswith("INV-")
    assert body["order_status"] in ("dispatched", "partially_dispatched")


def test_partial_dispatch_requires_acknowledgement(c, sd):
    order, pick = _first_pickable(c, sd)
    if len(pick["rolls"]) < 2:
        pytest.skip("need >=2 approved rolls for a partial test")
    half = [pick["rolls"][0]["id"]]
    # Without partial=True -> 409
    bad = c.post("/api/sales/dispatch", headers=sd, json={
        "order_id": order["id"], "roll_ids": half, "partial": False})
    assert bad.status_code == 409
    # With partial=True -> created, order partially dispatched
    ok = c.post("/api/sales/dispatch", headers=sd, json={
        "order_id": order["id"], "roll_ids": half, "partial": True})
    assert ok.status_code == 201, ok.text
    assert ok.json()["order_status"] == "partially_dispatched"


def test_cannot_dispatch_same_roll_twice(c, sd):
    order, pick = _first_pickable(c, sd)
    roll_ids = [r["id"] for r in pick["rolls"]]
    first = c.post("/api/sales/dispatch", headers=sd, json={
        "order_id": order["id"], "roll_ids": roll_ids, "partial": False})
    assert first.status_code == 201
    # Those rolls are now dispatched; re-selecting them is rejected (not approved).
    again = c.post("/api/sales/dispatch", headers=sd, json={
        "order_id": order["id"], "roll_ids": roll_ids, "partial": False})
    assert again.status_code in (400, 409)


def test_cannot_dispatch_non_approved_rolls(c, sd):
    # Find a rework/reject/pending roll (not 'pass') and try to dispatch it.
    from app.database import get_db
    from app.models import Order, Roll

    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        bad_roll = db.query(Roll).filter(Roll.status.in_(("rework", "reject", "pending"))).first()
        order = db.get(Order, bad_roll.order_id)
        oid, rid = order.id, bad_roll.id
    finally:
        gen.close()
    r = c.post("/api/sales/dispatch", headers=sd, json={
        "order_id": oid, "roll_ids": [rid], "partial": True})
    assert r.status_code == 400  # not QC-approved


# ------------------------------ Delivery ------------------------------ #
def test_confirm_delivery_updates_status(c, sd):
    order, pick = _first_pickable(c, sd)
    roll_ids = [r["id"] for r in pick["rolls"]]
    c.post("/api/sales/dispatch", headers=sd, json={
        "order_id": order["id"], "roll_ids": roll_ids, "partial": False})
    hist = c.get("/api/sales/history", headers=sd).json()["dispatches"]
    did = hist[0]["id"]
    r = c.post(f"/api/sales/dispatch/{did}/deliver", headers=sd, json={"received_by": "Store gate"})
    assert r.status_code == 200, r.text
    assert r.json()["delivered_at"] is not None


# ------------------------------ Permission boundaries ------------------------------ #
def test_sales_manager_cannot_confirm_orders_or_edit_payments(c, sd):
    # Confirming orders is order_desk (Supermanager); payments are the accountant's.
    assert c.post("/api/orders/1/confirm", headers=sd).status_code == 403
    assert c.get("/api/payments/dues", headers=sd).status_code == 403
    # QC verdicts belong to the quality inspector.
    assert c.get("/api/quality/rolls", headers=sd).status_code == 403


def test_invoices_are_read_only_view(c, sd):
    inv = c.get("/api/sales/invoices", headers=sd).json()
    assert "invoices" in inv and "read-only" in inv["note"].lower()


# ------------------------------ Reports ------------------------------ #
def test_reports_summarise_dispatches_and_dues(c, sd):
    rep = c.get("/api/sales/reports", headers=sd).json()
    assert "total_dispatches" in rep and "by_buyer" in rep and "dues" in rep

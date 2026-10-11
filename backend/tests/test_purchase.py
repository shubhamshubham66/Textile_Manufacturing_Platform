"""Purchase & raw material desk (store manager): request → Supermanager
approval → PO → receipt recorded → validated → stock, plus RBAC.

Run:  cd backend && pytest tests/test_purchase.py -v
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

SOON = (date.today() + timedelta(days=7)).isoformat()


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
def store(c):
    return login(c, "store@everest.test", "store123")


@pytest.fixture()
def sm(c):
    owner = login(c, "owner@everest.test", "owner123")
    c.post("/api/team/managers", headers=owner, json={
        "name": "Rishab Yadav", "login_id": "MGR-001", "password": "manager123", "confirm_password": "manager123"})
    return login(c, "MGR-001", "manager123")


def stock_of(c, h, yarn, colour):
    rows = c.get("/api/purchase/inventory", headers=h).json()["rows"]
    return next(r for r in rows if r["yarn_type"] == yarn and r["colour"] == colour)


PAGES = ["overview", "suppliers", "inventory", "requests", "orders", "receipts", "low-stock",
         "requirements", "reports", "notifications", "movements"]


def test_pages_open_for_store_and_are_closed_to_others(c, store):
    for p in PAGES:
        assert c.get(f"/api/purchase/{p}", headers=store).status_code == 200, p
    for who, pw in [("quality@everest.test", "quality123"), ("buyer@everest.test", "buyer123"),
                    ("accounts@everest.test", "accounts123")]:
        h = login(c, who, pw)
        for p in PAGES:
            assert c.get(f"/api/purchase/{p}", headers=h).status_code == 403, (who, p)


def test_overview_cards_are_real(c, store):
    d = c.get("/api/purchase/overview", headers=store).json()["cards"]
    assert d["suppliers"] == 3 and d["purchase_orders"] == 3
    assert d["stock_kg"] == 1650.0 and d["low_stock"] == 1


def test_full_flow_request_approval_po_partial_receipt_validation(c, store, sm):
    before = stock_of(c, store, "Cotton 40s", "Blue")["quantity_kg"]

    # Low-stock alert suggests a quantity; create a request from it.
    low = c.get("/api/purchase/low-stock", headers=store).json()["rows"]
    blue = next(r for r in low if r["colour"] == "Blue")
    assert blue["required_kg"] > 0 and blue["on_order_kg"] > 0  # seed PO-1003 is already on its way
    r = c.post("/api/purchase/requests", headers=store, json={
        "yarn_type": "Cotton 40s", "colour": "Blue", "quantity_kg": 200, "required_date": SOON,
        "source": "low_stock", "reason": "Below minimum"})
    assert r.status_code == 201 and r.json()["status"] == "pending"
    rid = r.json()["id"]

    # No PO without approval.
    sup = c.get("/api/purchase/orders", headers=store).json()["suppliers"][0]["id"]
    po_body = {"purchase_request_id": rid, "supplier_id": sup, "quantity_kg": 200, "unit_cost": 175,
               "tax_percent": 5, "expected_date": SOON}
    assert c.post("/api/purchase/orders", headers=store, json=po_body).status_code == 409
    # The old direct-PO endpoint cannot bypass it either.
    assert c.post("/api/yarn/purchase", headers=store, json={
        "supplier_id": sup, "yarn_type": "Cotton 40s", "colour": "Blue", "quantity_kg": 10}).status_code == 409
    # The store manager cannot approve their own request.
    assert c.post(f"/api/super/purchase-requests/{rid}/approve", headers=store, json={}).status_code == 403

    # Supermanager sees it waiting and approves.
    assert rid in [p["id"] for p in c.get("/api/super/purchase-requests", headers=sm).json()["pending"]]
    assert any(a["kind"] == "purchase_approvals" for a in c.get("/api/super/alerts", headers=sm).json()["alerts"])
    assert c.post(f"/api/super/purchase-requests/{rid}/approve", headers=sm, json={"note": "OK"}).status_code == 200
    notes = c.get("/api/purchase/notifications", headers=store).json()["items"]
    assert any("approved" in n["title"] for n in notes)

    # PO: more than +10% of the approved quantity is refused.
    assert c.post("/api/purchase/orders", headers=store, json={**po_body, "quantity_kg": 260}).status_code == 400
    po = c.post("/api/purchase/orders", headers=store, json=po_body)
    assert po.status_code == 201, po.text
    po = po.json()
    assert po["total"] == 200 * 175 * 1.05 and po["status"] == "raised"

    # Receipt 1: 120 kg with 5 kg damaged -> flagged shortage + damaged; stock unchanged.
    rc = c.post("/api/purchase/receipts", headers=store, json={
        "purchase_order_id": po["id"], "yarn_type": "Cotton 40s", "colour": "Blue", "quantity_kg": 120,
        "damaged_kg": 5, "batch_no": "B-77", "received_date": date.today().isoformat()})
    assert rc.status_code == 201, rc.text
    rc = rc.json()
    assert rc["status"] == "recorded" and "shortage" in rc["discrepancy"] and "damaged" in rc["discrepancy"]
    assert stock_of(c, store, "Cotton 40s", "Blue")["quantity_kg"] == before

    # Validate -> stock + 115, PO partial, movement written.
    v = c.post(f"/api/purchase/receipts/{rc['id']}/validate", headers=store, json={"accept": True})
    assert v.status_code == 200 and v.json()["status"] == "validated"
    assert stock_of(c, store, "Cotton 40s", "Blue")["quantity_kg"] == before + 115
    pos = {p["id"]: p for p in c.get("/api/purchase/orders", headers=store).json()["orders"]}
    assert pos[po["id"]]["status"] == "partial" and pos[po["id"]]["received_kg"] == 115
    mv = c.get("/api/purchase/movements", headers=store).json()[0]
    assert mv["kind"] == "receipt" and mv["change_kg"] == 115 and po["po_no"] in mv["reference"]
    assert c.post(f"/api/purchase/receipts/{rc['id']}/validate", headers=store, json={"accept": True}).status_code == 409

    # Receipt 2: the rest -> PO received, request received.
    rc2 = c.post("/api/purchase/receipts", headers=store, json={
        "purchase_order_id": po["id"], "yarn_type": "Cotton 40s", "colour": "Blue", "quantity_kg": 85,
        "batch_no": "B-78", "received_date": date.today().isoformat()}).json()
    assert rc2["discrepancy"] is None
    c.post(f"/api/purchase/receipts/{rc2['id']}/validate", headers=store, json={"accept": True})
    pos = {p["id"]: p for p in c.get("/api/purchase/orders", headers=store).json()["orders"]}
    assert pos[po["id"]]["status"] == "received"
    reqs = {x["id"]: x for x in c.get("/api/purchase/requests", headers=store).json()["requests"]}
    assert reqs[rid]["status"] == "received"


def test_rejected_delivery_never_enters_stock_and_needs_reason(c, store):
    before = stock_of(c, store, "Cotton 30s", "White")["quantity_kg"]
    rc = c.post("/api/purchase/receipts", headers=store, json={
        "yarn_type": "Cotton 30s", "colour": "White", "quantity_kg": 50, "batch_no": "X-1",
        "received_date": date.today().isoformat()}).json()
    assert c.post(f"/api/purchase/receipts/{rc['id']}/validate", headers=store, json={"accept": False}).status_code == 400
    r = c.post(f"/api/purchase/receipts/{rc['id']}/validate", headers=store, json={"accept": False, "note": "Wet bags"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    assert stock_of(c, store, "Cotton 30s", "White")["quantity_kg"] == before
    assert c.post("/api/purchase/receipts", headers=store, json={
        "yarn_type": "Cotton 30s", "colour": "White", "quantity_kg": 5, "damaged_kg": 9, "batch_no": "X-2",
        "received_date": date.today().isoformat()}).status_code == 400


def test_rejected_request_and_auto_approve_setting(c, store, sm):
    rid = c.post("/api/purchase/requests", headers=store, json={
        "yarn_type": "Viscose 20s", "colour": "Red", "quantity_kg": 40}).json()["id"]
    assert c.post(f"/api/super/purchase-requests/{rid}/reject", headers=sm, json={}).status_code == 400
    r = c.post(f"/api/super/purchase-requests/{rid}/reject", headers=sm, json={"note": "Enough red in stock"})
    assert r.json()["status"] == "rejected"
    c.put("/api/super/settings", headers=sm, json={"purchase_auto_approve_kg": 100})
    r = c.post("/api/purchase/requests", headers=store, json={"yarn_type": "Viscose 20s", "colour": "Red", "quantity_kg": 60})
    assert r.json()["status"] == "approved"
    r = c.post("/api/purchase/requests", headers=store, json={"yarn_type": "Viscose 20s", "colour": "Red", "quantity_kg": 160})
    assert r.json()["status"] == "pending"


def test_suppliers_add_edit_deactivate_and_history(c, store):
    r = c.post("/api/purchase/suppliers", headers=store, json={
        "name": "Erode Yarn Mills", "contact_person": "K. Murugan", "phone": "+91 98430 11223",
        "email": "sales@erode.test", "address": "Erode, TN", "yarn_types": "Cotton 30s, Cotton 40s"})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    assert c.post("/api/purchase/suppliers", headers=store, json={"name": "erode yarn mills"}).status_code == 409
    assert c.post("/api/purchase/suppliers", headers=store, json={"name": "Bad", "email": "nope"}).status_code == 400
    c.post(f"/api/purchase/suppliers/{sid}/active", headers=store, json={"active": False})
    sups = c.get("/api/purchase/orders", headers=store).json()["suppliers"]
    assert sid not in [s["id"] for s in sups]  # inactive suppliers cannot get new POs
    assert c.get("/api/purchase/suppliers/1/history", headers=store).json()["purchase_orders"]


def test_inventory_location_threshold_and_requirements_share(c, store, sm):
    s = stock_of(c, store, "Cotton 30s", "White")
    r = c.put(f"/api/purchase/inventory/{s['id']}", headers=store, json={"location": "Rack A-2", "reorder_level_kg": 900})
    assert r.status_code == 200 and r.json()["location"] == "Rack A-2" and r.json()["low"] is True
    req = c.get("/api/purchase/requirements", headers=store).json()
    assert req["rows"] and "basis" in req
    r = c.post("/api/purchase/requirements/share", headers=store, json={"note": "Blue arriving Monday"})
    assert r.status_code == 200 and "Supermanager" in r.json()["sent_to"]


def test_instruction_from_supermanager_shows_for_store_and_links_request(c, store, sm):
    t = c.post("/api/super/tasks", headers=sm, json={
        "title": "Buy 100 kg Black polyester", "department": "purchase", "priority": "high"}).json()
    lst = c.get("/api/purchase/requests", headers=store).json()["instructions"]
    assert t["id"] in [i["id"] for i in lst]
    c.post("/api/purchase/requests", headers=store, json={
        "yarn_type": "Polyester 150D", "colour": "Black", "quantity_kg": 100, "source": "instruction", "task_id": t["id"]})
    tasks = {x["id"]: x for x in c.get("/api/super/tasks", headers=sm).json()["tasks"]}
    assert tasks[t["id"]]["status"] == "in_progress"

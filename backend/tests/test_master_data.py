"""Owner master data: buyers/suppliers/machines/employees add+edit, order
edit/cancel before production, yarn receipt correction, and RBAC (403).

Run:  cd backend && pytest tests/test_master_data.py -v
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
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
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
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
    mp.undo()


def tok(c, email, pw):
    return {"Authorization": "Bearer " + c.post("/api/auth/login", json={"email": email, "password": pw}).json()["token"]}


def owner(c):
    return tok(c, "owner@everest.test", "owner123")


# ------------------------- master CRUD ------------------------- #
def test_add_and_edit_buyer(c):
    h = owner(c)
    before = len(c.get("/api/master/buyers", headers=h).json())
    r = c.post("/api/master/buyers", headers=h, json={"name": "New Buyer Co", "credit_limit": 50000})
    assert r.status_code == 201
    bid = r.json()["id"]
    assert len(c.get("/api/master/buyers", headers=h).json()) == before + 1
    # duplicate name -> 409
    assert c.post("/api/master/buyers", headers=h, json={"name": "New Buyer Co"}).status_code == 409
    # edit
    r2 = c.put(f"/api/master/buyers/{bid}", headers=h, json={"name": "New Buyer Co", "credit_limit": 75000})
    assert r2.status_code == 200 and r2.json()["credit_limit"] == 75000.0


def test_add_supplier_and_employee(c):
    h = owner(c)
    assert c.post("/api/master/suppliers", headers=h, json={"name": "Fresh Supplier"}).status_code == 201
    r = c.post("/api/master/employees", headers=h, json={"name": "Asha Devi", "daily_wage": 520})
    assert r.status_code == 201 and r.json()["daily_wage"] == 520.0


def test_machine_power_cannot_exceed_hourly(c):
    h = owner(c)
    bad = c.post("/api/master/machines", headers=h, json={"name": "Loom-X", "type": "weaving", "hourly_cost": 400, "power_overhead_cost": 500})
    assert bad.status_code == 400 and "exceed" in bad.json()["error"]["message"].lower()
    good = c.post("/api/master/machines", headers=h, json={"name": "Loom-X", "type": "weaving", "hourly_cost": 400, "power_overhead_cost": 240})
    assert good.status_code == 201
    # bad type rejected
    assert c.post("/api/master/machines", headers=h, json={"name": "Loom-Y", "type": "knitting", "hourly_cost": 1}).status_code in (400, 422)


def test_master_forbidden_for_non_owner(c):
    for email, pw in [("accounts@everest.test", "accounts123"), ("store@everest.test", "store123"),
                      ("floor@everest.test", "floor123"), ("buyer@everest.test", "buyer123")]:
        h = tok(c, email, pw)
        for path in ["buyers", "suppliers", "machines", "employees", "yarn-receipts"]:
            assert c.get(f"/api/master/{path}", headers=h).status_code == 403
        assert c.post("/api/master/buyers", headers=h, json={"name": "X Co"}).status_code == 403


# ------------------------- order edit / cancel ------------------------- #
# Orders are written by the Manager; the owner only views them.
def manager(c):
    h = owner(c)
    c.post("/api/team/managers", headers=h, json={
        "name": "Ravi Kumar", "login_id": "MGR-001",
        "password": "manager123", "confirm_password": "manager123",
    })
    r = c.post("/api/auth/login", json={"email": "MGR-001", "password": "manager123"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _order_id(c, h, order_no):
    return next(o["id"] for o in c.get("/api/orders", headers=h).json() if o["order_no"] == order_no)


def test_edit_order_before_production(c):
    h = manager(c)
    # ORD-2006 is a draft in the seed.
    oid = _order_id(c, h, "ORD-2006")
    o = next(o for o in c.get("/api/orders", headers=h).json() if o["id"] == oid)
    r = c.put(f"/api/orders/{oid}", headers=h, json={
        "buyer_id": o["buyer_id"], "fabric_type": "Viscose Crepe", "colour": "Teal",
        "quantity_meters": 950, "unit_price": 135, "deadline": "2026-10-28",
    })
    assert r.status_code == 200
    assert r.json()["colour"] == "Teal" and r.json()["quantity_meters"] == 950.0


def test_cannot_edit_or_cancel_in_production(c):
    h = manager(c)
    # ORD-2003 is in_quality (past production) in the seed.
    oid = _order_id(c, h, "ORD-2003")
    o = next(o for o in c.get("/api/orders", headers=h).json() if o["id"] == oid)
    r = c.put(f"/api/orders/{oid}", headers=h, json={
        "buyer_id": o["buyer_id"], "fabric_type": o["fabric_type"], "colour": o["colour"],
        "quantity_meters": o["quantity_meters"], "unit_price": o["unit_price"], "deadline": o["deadline"],
    })
    assert r.status_code == 409
    assert c.post(f"/api/orders/{oid}/cancel", headers=h).status_code == 409


def test_cancel_draft_order(c):
    h = manager(c)
    oid = _order_id(c, h, "ORD-2006")
    assert c.post(f"/api/orders/{oid}/cancel", headers=h).status_code == 200
    o = next(o for o in c.get("/api/orders", headers=h).json() if o["id"] == oid)
    assert o["status"] == "cancelled"


# ------------------------- yarn receipt correction ------------------------- #
def test_correct_receipt_adjusts_stock(c):
    h = owner(c)
    receipts = c.get("/api/master/yarn-receipts", headers=h).json()
    # The seed links a 400 kg Cotton 30s White receipt to ORD-2001.
    rc = next(r for r in receipts if r["yarn_type"] == "Cotton 30s" and r["quantity_kg"] == 400.0)
    # Stock before.
    stock = c.get("/api/yarn/stock", headers=tok(c, "store@everest.test", "store123")).json()
    before = next(s for s in stock if s["yarn_type"] == "Cotton 30s" and s["colour"] == "White")["quantity_kg"]
    # Correct 400 -> 300 (−100 kg).
    r = c.put(f"/api/master/yarn-receipts/{rc['id']}", headers=h, json={"quantity_kg": 300, "unit_cost": 180, "order_id": None})
    assert r.status_code == 200 and r.json()["quantity_kg"] == 300.0
    stock2 = c.get("/api/yarn/stock", headers=tok(c, "store@everest.test", "store123")).json()
    after = next(s for s in stock2 if s["yarn_type"] == "Cotton 30s" and s["colour"] == "White")["quantity_kg"]
    assert round(before - after, 2) == 100.0


def test_receipt_correction_increase_adds_to_stock(c):
    h = owner(c)
    store = tok(c, "store@everest.test", "store123")
    receipts = c.get("/api/master/yarn-receipts", headers=h).json()
    rc = next(r for r in receipts if r["yarn_type"] == "Cotton 40s" and r["quantity_kg"] == 90.0)
    before = next(s for s in c.get("/api/yarn/stock", headers=store).json()
                  if s["yarn_type"] == "Cotton 40s" and s["colour"] == "Blue")["quantity_kg"]
    # Correct 90 -> 150 (+60 kg).
    r = c.put(f"/api/master/yarn-receipts/{rc['id']}", headers=h, json={"quantity_kg": 150, "unit_cost": 200, "order_id": None})
    assert r.status_code == 200
    after = next(s for s in c.get("/api/yarn/stock", headers=store).json()
                 if s["yarn_type"] == "Cotton 40s" and s["colour"] == "Blue")["quantity_kg"]
    assert round(after - before, 2) == 60.0

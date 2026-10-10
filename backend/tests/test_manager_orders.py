"""Manager writes orders; owner only reads them.

Run:  cd backend && pytest tests/test_manager_orders.py -v
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


def make_manager(c, owner_h):
    r = c.post("/api/team/managers", headers=owner_h, json={
        "name": "Ravi Kumar", "login_id": "MGR-001",
        "password": "manager123", "confirm_password": "manager123",
    })
    assert r.status_code == 201, r.text
    return login(c, "MGR-001", "manager123")


def test_manager_creates_checks_and_confirms_order_owner_sees_it(c):
    owner = login(c, "owner@everest.test", "owner123")
    mgr = make_manager(c, owner)

    buyers = c.get("/api/orders/_meta/buyers", headers=mgr).json()
    r = c.post("/api/orders", headers=mgr, json={
        "buyer_id": buyers[0]["id"], "fabric_type": "Cotton Poplin", "colour": "White",
        "quantity_meters": 100, "unit_price": 120, "deadline": "2026-10-30",
    })
    assert r.status_code == 201, r.text
    oid, order_no = r.json()["id"], r.json()["order_no"]

    assert c.get(f"/api/orders/{oid}/check-yarn", headers=mgr).status_code == 200
    r = c.post(f"/api/orders/{oid}/confirm", headers=mgr)
    assert r.status_code in (200, 409), r.text  # 409 only if yarn is short

    # The owner sees the new order on the read-only list.
    assert order_no in [o["order_no"] for o in c.get("/api/orders", headers=owner).json()]


def test_owner_cannot_write_orders(c):
    owner = login(c, "owner@everest.test", "owner123")
    orders = c.get("/api/orders", headers=owner).json()
    oid = orders[0]["id"]
    body = {"buyer_id": orders[0]["buyer_id"], "fabric_type": "X", "colour": "Y",
            "quantity_meters": 10, "unit_price": 1, "deadline": "2026-10-30"}
    assert c.post("/api/orders", headers=owner, json=body).status_code == 403
    assert c.post(f"/api/orders/{oid}/confirm", headers=owner).status_code == 403
    assert c.put(f"/api/orders/{oid}", headers=owner, json=body).status_code == 403
    assert c.post(f"/api/orders/{oid}/cancel", headers=owner).status_code == 403


def test_other_roles_cannot_touch_orders(c):
    store = login(c, "store@everest.test", "store123")
    assert c.get("/api/orders", headers=store).status_code == 403

"""Explicit test: a buyer can NEVER see another buyer's data (Phase 9, task 5).

Runs against a throwaway in-memory SQLite DB with two buyers. Requires the backend
dependencies installed (fastapi, sqlalchemy, passlib, python-jose). On a networked
host:

    cd backend && source .venv/bin/activate
    pip install pytest
    pytest tests/test_buyer_isolation.py -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app import models as m
from app.security import hash_password


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    db = TestingSession()
    # Roles
    buyer_role = m.Role(name="buyer")
    db.add(buyer_role)
    db.flush()
    # Two buyers, each with a login and an order + invoice
    b1 = m.Buyer(name="Buyer One")
    b2 = m.Buyer(name="Buyer Two")
    db.add_all([b1, b2])
    db.flush()
    db.add_all([
        m.User(role_id=buyer_role.id, buyer_id=b1.id, name="One",
               email="one@test", password_hash=hash_password("pw1")),
        m.User(role_id=buyer_role.id, buyer_id=b2.id, name="Two",
               email="two@test", password_hash=hash_password("pw2")),
    ])
    o1 = m.Order(buyer_id=b1.id, order_no="ORD-1", fabric_type="Cotton",
                 colour="White", quantity_meters=100, unit_price=50, status="confirmed")
    o2 = m.Order(buyer_id=b2.id, order_no="ORD-2", fabric_type="Silk",
                 colour="Black", quantity_meters=200, unit_price=90, status="in_quality")
    db.add_all([o1, o2])
    db.flush()
    db.add_all([
        m.Invoice(order_id=o1.id, buyer_id=b1.id, invoice_no="INV-1",
                  subtotal=5000, tax=250, total=5250),
        m.Invoice(order_id=o2.id, buyer_id=b2.id, invoice_no="INV-2",
                  subtotal=18000, tax=900, total=18900),
    ])
    db.commit()
    o1_id, o2_id = o1.id, o2.id
    db.close()

    def _override():
        s = TestingSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    c = TestClient(app)
    c._o1, c._o2 = o1_id, o2_id  # stash ids for the test
    yield c
    app.dependency_overrides.clear()


def _login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_buyer_sees_only_own_orders(client):
    t1 = _login(client, "one@test", "pw1")
    h1 = {"Authorization": f"Bearer {t1}"}
    orders = client.get("/api/buyer/orders", headers=h1).json()
    assert [o["order_no"] for o in orders] == ["ORD-1"]


def test_buyer_sees_only_own_invoices(client):
    t2 = _login(client, "two@test", "pw2")
    h2 = {"Authorization": f"Bearer {t2}"}
    invoices = client.get("/api/buyer/invoices", headers=h2).json()
    assert [i["invoice_no"] for i in invoices] == ["INV-2"]


def test_buyer_cannot_track_other_buyers_order(client):
    t1 = _login(client, "one@test", "pw1")
    h1 = {"Authorization": f"Bearer {t1}"}
    # Buyer One tries to read Buyer Two's order -> 404 (no existence leak)
    r = client.get(f"/api/buyer/orders/{client._o2}", headers=h1)
    assert r.status_code == 404
    # And can read their own
    r_own = client.get(f"/api/buyer/orders/{client._o1}", headers=h1)
    assert r_own.status_code == 200
    assert r_own.json()["order_no"] == "ORD-1"


def test_buyer_cannot_download_other_buyers_invoice(client):
    t1 = _login(client, "one@test", "pw1")
    h1 = {"Authorization": f"Bearer {t1}"}
    # Buyer Two's invoice id is 2 -> 404 for Buyer One
    r = client.get("/api/buyer/invoices/2/pdf", headers=h1)
    assert r.status_code == 404

"""Buyer payment flow: order confirm → invoice raised → buyer 'Pay now' →
accounts confirms → payment-gated dispatch.

Covers:
  - Confirming an order raises an unpaid invoice for the buyer.
  - Buyer 'Pay now' records a payment against their own invoice.
  - Dispatch is BLOCKED (402) while the invoice is not fully paid.
  - Once the invoice is 'paid', dispatch is allowed.
  - A buyer cannot pay someone else's invoice (404).

Run:  cd backend && pytest tests/test_buyer_payment_flow.py -v
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


def owner(c):
    return login(c, "owner@everest.test", "owner123")


def _supermanager(c):
    """Create + log in a Supermanager (same pattern as test_supermanager)."""
    own = owner(c)
    c.post("/api/team/managers", headers=own, json={
        "name": "Rishab Yadav", "login_id": "MGR-001",
        "password": "manager123", "confirm_password": "manager123"})
    return login(c, "MGR-001", "manager123")


def test_confirm_raises_invoice_then_buyer_pays(c):
    buyer_h = login(c, "buyer@everest.test", "buyer123")
    sm = _supermanager(c)

    # Buyer requests a new order.
    r = c.post("/api/buyer/orders", headers=buyer_h, json={
        "fabric_type": "Cotton Poplin", "colour": "Teal", "quantity_meters": 100,
        "deadline": "2026-12-31", "note": "pay-flow test"})
    assert r.status_code == 201, r.text
    oid = r.json()["id"]

    # Before confirmation there is no invoice for this new order.
    pre = c.get("/api/buyer/invoices", headers=buyer_h).json()
    assert all(i["order_no"] != r.json()["order_no"] for i in pre)

    # Supermanager confirms with a unit price -> invoice is raised (unpaid).
    conf = c.post(f"/api/orders/{oid}/confirm", headers=sm, json={"unit_price": 90})
    assert conf.status_code == 200, conf.text

    invoices = c.get("/api/buyer/invoices", headers=buyer_h).json()
    inv = next(i for i in invoices if i["order_no"] == conf.json()["order_no"])
    assert inv["status"] == "unpaid" and inv["payable"] and inv["balance"] > 0

    # Buyer 'Pay now' pays the full balance.
    pay = c.post(f"/api/buyer/invoices/{inv['id']}/pay", headers=buyer_h, json={"method": "bank"})
    assert pay.status_code == 200, pay.text
    assert pay.json()["status"] == "paid" and pay.json()["balance"] == 0.0

    # Paying an already-paid invoice is refused.
    again = c.post(f"/api/buyer/invoices/{inv['id']}/pay", headers=buyer_h, json={"method": "bank"})
    assert again.status_code == 409


def test_dispatch_blocked_until_invoice_paid(c):
    """ORD-2003 is seeded dispatch-ready with a PAID invoice. If we void its
    payment (owner), dispatch must be blocked with 402; after paying again it
    is allowed."""
    sd = login(c, "sales@everest.test", "sales123")
    own = owner(c)

    # Pick the first dispatchable order + its approved rolls.
    planning = c.get("/api/sales/planning", headers=sd).json()
    assert planning["orders"], "expected at least one dispatchable order in the seed"
    order = planning["orders"][0]
    pick = c.get(f"/api/sales/orders/{order['id']}/pickable", headers=sd).json()
    roll_ids = [r["id"] for r in pick["rolls"]]
    assert roll_ids, "expected approved rolls to dispatch"

    # Find this order's invoice via the accounts meta, and void its payment so
    # the invoice is no longer fully paid.
    meta = c.get("/api/payments/_meta", headers=own).json()
    inv = next((i for i in meta["invoices"] if i["order_no"] == order["order_no"]), None)
    assert inv is not None, "the dispatchable order should have an invoice"
    assert inv["status"] == "paid"

    pays = c.get("/api/payments", headers=own).json()
    pay = next(p for p in pays if p["invoice_id"] == inv["id"] and not p["voided"])
    assert c.post(f"/api/payments/{pay['id']}/void", headers=own,
                  json={"reason": "test: unpay to check gate"}).status_code == 200

    # Now dispatch must be blocked: payment not complete.
    blocked = c.post("/api/sales/dispatch", headers=sd, json={
        "order_id": order["id"], "roll_ids": roll_ids, "partial": False})
    assert blocked.status_code == 402, blocked.text

    # Re-pay via accounts, then dispatch succeeds.
    bal = round(inv["total"], 2)
    r = c.post("/api/payments/buyer", headers=own,
               json={"invoice_id": inv["id"], "amount": bal, "method": "bank"})
    assert r.status_code == 200 and r.json()["invoice_status"] == "paid"

    ok = c.post("/api/sales/dispatch", headers=sd, json={
        "order_id": order["id"], "roll_ids": roll_ids, "partial": False})
    assert ok.status_code == 201, ok.text


def test_buyer_cannot_pay_others_invoice(c):
    buyer_h = login(c, "buyer@everest.test", "buyer123")
    own = owner(c)
    # An invoice that does NOT belong to the logged-in buyer.
    meta = c.get("/api/payments/_meta", headers=own).json()
    mine = {i["id"] for i in c.get("/api/buyer/invoices", headers=buyer_h).json()}
    others = [i for i in meta["invoices"] if i["id"] not in mine]
    if not others:
        pytest.skip("no other-buyer invoice in this fixture")
    r = c.post(f"/api/buyer/invoices/{others[0]['id']}/pay", headers=buyer_h, json={"method": "bank"})
    assert r.status_code == 404

"""Void payment (owner only) — acceptance checks against the October 2026 seed.

Covers:
  - voiding a large supplier payment restores profit_or_loss and dues
  - Dashboard card == Reports P&L after the void
  - voiding twice -> 409
  - accountant / floor / buyer -> 403
  - voiding a buyer payment flips the invoice status back

Run:  cd backend && pytest tests/test_void_payment.py -v
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


@pytest.fixture()
def c():
    # Function scope: each test voids data, so start from a fresh seeded DB.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
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
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    return {"Authorization": "Bearer " + r.json()["token"]}


def owner(c):
    return tok(c, "owner@everest.test", "owner123")


def _find(c, h, direction, amount):
    rows = c.get("/api/payments", headers=h).json()
    return next(p for p in rows if p["direction"] == direction and p["amount"] == amount)


def test_void_large_supplier_payment_restores_net_and_dues(c):
    h = owner(c)
    # Baseline (hand-check): net 17,860; supplier out 2,00,000; Punjab PO-1003
    # (₹80,000) is the only open supplier due.
    pl0 = c.get(f"/api/reports/profit-loss?{OCT}", headers=h).json()
    assert pl0["profit_or_loss"] == 17860.00
    dues0 = c.get("/api/payments/dues", headers=h).json()
    # Gujarat 1,80,000 bill fully paid; South India 84,000 − 20,000 = 64,000 owed;
    # Punjab 80,000 open -> 1,44,000 payable.
    assert dues0["total_payable"] == 144000.00

    pay = _find(c, h, "outgoing", 180000.0)  # the large Gujarat payment
    r = c.post(f"/api/payments/{pay['id']}/void", headers=h, json={"reason": "test junk entry"})
    assert r.status_code == 200 and r.json()["voided"] is True

    # Supplier out drops by 1,80,000 -> net rises to 1,97,860.
    pl1 = c.get(f"/api/reports/profit-loss?{OCT}", headers=h).json()
    assert pl1["supplier_payments_out"] == 20000.00
    assert pl1["profit_or_loss"] == 197860.00

    # Dashboard card uses the SAME number as Reports P&L.
    dash = c.get(f"/api/reports/dashboard?{OCT}", headers=h).json()["profit_loss"]
    assert dash["profit_or_loss"] == pl1["profit_or_loss"] == 197860.00

    # Voiding the Gujarat payment restores its 1,80,000 bill: 1,44,000 + 1,80,000
    # = 3,24,000 payable.
    dues1 = c.get("/api/payments/dues", headers=h).json()
    assert dues1["total_payable"] == 324000.00

    # The voided payment is still listed, flagged.
    voided = next(p for p in c.get("/api/payments", headers=h).json() if p["id"] == pay["id"])
    assert voided["voided"] is True
    assert voided["void_reason"] == "test junk entry"
    assert voided["voided_by"] == "Ramesh Shah"


def test_void_twice_is_409(c):
    h = owner(c)
    pay = _find(c, h, "outgoing", 180000.0)
    assert c.post(f"/api/payments/{pay['id']}/void", headers=h, json={"reason": "first void"}).status_code == 200
    r = c.post(f"/api/payments/{pay['id']}/void", headers=h, json={"reason": "second void"})
    assert r.status_code == 409


def test_void_reason_too_short_is_422(c):
    h = owner(c)
    pay = _find(c, h, "outgoing", 180000.0)
    assert c.post(f"/api/payments/{pay['id']}/void", headers=h, json={"reason": "x"}).status_code == 422


def test_void_forbidden_for_non_owner(c):
    owner_h = owner(c)
    pay = _find(c, owner_h, "outgoing", 180000.0)
    for email, pw in [
        ("accounts@everest.test", "accounts123"),
        ("quality@everest.test", "quality123"),
        ("buyer@everest.test", "buyer123"),
    ]:
        h = tok(c, email, pw)
        r = c.post(f"/api/payments/{pay['id']}/void", headers=h, json={"reason": "should fail"})
        assert r.status_code == 403, f"{email} expected 403, got {r.status_code}"
    # Still not voided.
    pay2 = _find(c, owner_h, "outgoing", 180000.0)
    assert pay2["voided"] is False


def test_void_buyer_payment_flips_invoice_status(c):
    h = owner(c)
    # INV-4001 is fully paid by a 1,99,500 buyer payment in the seed.
    meta0 = c.get("/api/payments/_meta", headers=h).json()
    inv0 = next(i for i in meta0["invoices"] if i["invoice_no"] == "INV-4001")
    assert inv0["status"] == "paid" and inv0["balance"] == 0.0

    pay = _find(c, h, "incoming", 199500.0)
    r = c.post(f"/api/payments/{pay['id']}/void", headers=h, json={"reason": "wrong invoice"})
    assert r.status_code == 200
    assert r.json()["invoice_status"] == "unpaid"

    # Meta/dues reflect the reversal: invoice is unpaid again and receivable rises.
    meta1 = c.get("/api/payments/_meta", headers=h).json()
    inv1 = next(i for i in meta1["invoices"] if i["invoice_no"] == "INV-4001")
    assert inv1["status"] == "unpaid" and inv1["paid"] == 0.0
    assert inv1["balance"] == inv1["total"]

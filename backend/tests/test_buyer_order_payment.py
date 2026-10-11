"""Buyer pays a confirmed order; accounts confirms; delivery waits for payment.

Run:  cd backend && pytest tests/test_buyer_order_payment.py -v
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


def _payable_order(c, by):
    orders = c.get("/api/buyer/orders", headers=by).json()
    for o in orders:
        if o["payment"]["can_pay"]:
            return o
    pytest.skip("seed has no payable order for the buyer")


def test_buyer_pays_and_accounts_confirms(c):
    by = login(c, "buyer@everest.test", "buyer123")
    am = login(c, "accounts-manager@everest.test", "accounts123")
    o = _payable_order(c, by)
    pay = o["payment"]

    # Reference is required for bank / UPI.
    r = c.post(f"/api/buyer/orders/{o['id']}/payments", headers=by, json={"amount": 10, "method": "upi"})
    assert r.status_code == 400
    # Cannot pay more than is left.
    r = c.post(f"/api/buyer/orders/{o['id']}/payments", headers=by,
               json={"amount": pay["payable"] + 100, "method": "upi", "reference": "UTR1"})
    assert r.status_code == 400

    r = c.post(f"/api/buyer/orders/{o['id']}/payments", headers=by,
               json={"amount": pay["payable"], "method": "upi", "reference": "UTR123"})
    assert r.status_code == 201, r.text
    assert r.json()["payment"]["pending"] == pytest.approx(pay["pending"] + pay["payable"])
    # A second submit has nothing left to pay (all awaiting confirmation).
    again = c.post(f"/api/buyer/orders/{o['id']}/payments", headers=by,
                   json={"amount": 1, "method": "upi", "reference": "UTR124"})
    assert again.status_code == 409

    # Accounts sees it, plus a notification.
    pend = c.get("/api/payments/requests", headers=am).json()
    req = next(x for x in pend if x["order_id"] == o["id"])
    notes = c.get("/api/accounts/notifications", headers=am).json()["notifications"]
    assert any(o["order_no"] in n["title"] for n in notes)

    ok = c.post(f"/api/payments/requests/{req['id']}/confirm", headers=am)
    assert ok.status_code == 200, ok.text
    assert c.post(f"/api/payments/requests/{req['id']}/confirm", headers=am).status_code == 409

    after = next(x for x in c.get("/api/buyer/orders", headers=by).json() if x["id"] == o["id"])
    assert after["payment"]["status"] == "paid"
    assert after["payment"]["can_pay"] is False
    # Buyer is told.
    bn = c.get("/api/buyer/notifications", headers=by).json()["notifications"]
    assert any("Payment confirmed" in n["title"] for n in bn)


def test_reject_frees_the_amount(c):
    by = login(c, "buyer@everest.test", "buyer123")
    am = login(c, "accounts-manager@everest.test", "accounts123")
    o = _payable_order(c, by)
    r = c.post(f"/api/buyer/orders/{o['id']}/payments", headers=by,
               json={"amount": 100, "method": "bank", "reference": "NEFT9"})
    rid = r.json()["request"]["id"]
    rej = c.post(f"/api/payments/requests/{rid}/reject", headers=am, json={"reason": "not in bank"})
    assert rej.status_code == 200
    after = next(x for x in c.get("/api/buyer/orders", headers=by).json() if x["id"] == o["id"])
    assert after["payment"]["pending"] == pytest.approx(o["payment"]["pending"])


def test_only_staff_with_payments_can_confirm(c):
    by = login(c, "buyer@everest.test", "buyer123")
    sd = login(c, "sales@everest.test", "sales123")
    assert c.get("/api/payments/requests", headers=sd).status_code == 403
    assert c.get("/api/payments/requests", headers=by).status_code == 403

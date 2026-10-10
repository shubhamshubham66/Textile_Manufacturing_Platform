"""Payment idempotency: a double-clicked / retried payment must be recorded
only ONCE.

Covers:
  - Same Idempotency-Key on a buyer payment -> one Payment, replay flagged.
  - A different key -> a genuinely new payment is recorded.
  - Same key on a supplier payment -> one Payment.
  - No key -> behaves exactly as before (back-compatible).

Run:  cd backend && pytest tests/test_payment_idempotency.py -v
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


def _payment_count(c, h, direction):
    rows = c.get("/api/payments", headers=h).json()
    return sum(1 for p in rows if p["direction"] == direction and not p["voided"])


def _open_invoice(c, h):
    meta = c.get("/api/payments/_meta", headers=h).json()
    return next(i for i in meta["invoices"] if i["balance"] > 0)


def test_buyer_payment_with_same_key_records_once(c):
    h = owner(c)
    inv = _open_invoice(c, h)
    before = _payment_count(c, h, "incoming")
    body = {"invoice_id": inv["id"], "amount": 1000, "method": "bank"}
    hk = {**h, "Idempotency-Key": "dup-key-123"}

    r1 = c.post("/api/payments/buyer", headers=hk, json=body)
    assert r1.status_code == 200
    assert not r1.json().get("idempotent_replay")

    # Same key again (the double-click / retry) -> no second payment.
    r2 = c.post("/api/payments/buyer", headers=hk, json=body)
    assert r2.status_code == 200
    assert r2.json().get("idempotent_replay") is True

    after = _payment_count(c, h, "incoming")
    assert after == before + 1, "a replayed payment must not create a duplicate"


def test_buyer_payment_with_new_key_records_again(c):
    h = owner(c)
    inv = _open_invoice(c, h)
    before = _payment_count(c, h, "incoming")
    body = {"invoice_id": inv["id"], "amount": 1000, "method": "bank"}

    c.post("/api/payments/buyer", headers={**h, "Idempotency-Key": "k1"}, json=body)
    # A genuinely new payment (new key) is recorded.
    r = c.post("/api/payments/buyer", headers={**h, "Idempotency-Key": "k2"}, json=body)
    assert r.status_code == 200 and not r.json().get("idempotent_replay")
    assert _payment_count(c, h, "incoming") == before + 2


def test_supplier_payment_with_same_key_records_once(c):
    h = owner(c)
    before = _payment_count(c, h, "outgoing")
    meta = c.get("/api/payments/_meta", headers=h).json()
    sup = meta["suppliers"][0]["id"]
    body = {"supplier_id": sup, "amount": 500, "method": "bank"}
    hk = {**h, "Idempotency-Key": "sup-dup-1"}

    assert c.post("/api/payments/supplier", headers=hk, json=body).status_code == 200
    r2 = c.post("/api/payments/supplier", headers=hk, json=body)
    assert r2.status_code == 200 and r2.json().get("idempotent_replay") is True
    assert _payment_count(c, h, "outgoing") == before + 1


def test_payment_without_key_still_works(c):
    h = owner(c)
    inv = _open_invoice(c, h)
    before = _payment_count(c, h, "incoming")
    r = c.post(
        "/api/payments/buyer",
        headers=h,
        json={"invoice_id": inv["id"], "amount": 1000, "method": "bank"},
    )
    assert r.status_code == 200 and "idempotent_replay" not in r.json()
    assert _payment_count(c, h, "incoming") == before + 1

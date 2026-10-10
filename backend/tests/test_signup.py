"""Signup with email OTP: send code -> verify -> create account -> log in.

Email sending is replaced with a stub that captures the code, so no real email
goes out. Run:  cd backend && pytest tests/test_signup.py -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as m
from app.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.routers import signup as signup_router

ROLES = ["owner", "store_manager", "floor_supervisor", "quality_inspector", "accountant", "buyer"]


@pytest.fixture()
def env(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    db = Session()
    db.add_all([m.Role(name=r) for r in ROLES])
    db.commit()

    def override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override

    sent = {}
    monkeypatch.setattr(signup_router, "email_configured", lambda: True)
    monkeypatch.setattr(signup_router, "send_signup_otp", lambda to, code, minutes: sent.__setitem__(to, code))
    settings = get_settings()
    monkeypatch.setattr(settings, "otp_resend_seconds", 0)

    yield TestClient(app), sent, Session
    app.dependency_overrides.clear()


def _signup(c, sent, email="new@mill.in", role="store_manager", name="Ravi Kumar", pw="Mill2026a"):
    assert c.post("/api/auth/signup/send-otp", json={"email": email}).status_code == 200
    r = c.post("/api/auth/signup/verify-otp", json={"email": email, "otp": sent[email]})
    assert r.status_code == 200, r.text
    token = r.json()["email_token"]
    return c.post("/api/auth/signup", json={
        "name": name, "email": email, "role": role,
        "password": pw, "confirm_password": pw, "email_token": token,
    })


def test_full_signup_then_login(env):
    c, sent, _ = env
    r = _signup(c, sent)
    assert r.status_code == 201, r.text
    login = c.post("/api/auth/login", json={"email": "new@mill.in", "password": "Mill2026a"})
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "store_manager"


def test_buyer_signup_gets_own_buyer_record(env):
    c, sent, Session = env
    assert _signup(c, sent, email="buyer@shop.in", role="buyer", name="Asha Traders").status_code == 201
    db = Session()
    u = db.query(m.User).filter_by(email="buyer@shop.in").one()
    assert u.buyer_id is not None and u.buyer.name == "Asha Traders"


def test_wrong_code_counts_attempts_then_locks(env):
    c, sent, _ = env
    c.post("/api/auth/signup/send-otp", json={"email": "x@mill.in"})
    wrong = "000000" if sent["x@mill.in"] != "000000" else "111111"
    for _ in range(5):
        assert c.post("/api/auth/signup/verify-otp", json={"email": "x@mill.in", "otp": wrong}).status_code in (400, 429)
    # Even the right code is refused once locked.
    r = c.post("/api/auth/signup/verify-otp", json={"email": "x@mill.in", "otp": sent["x@mill.in"]})
    assert r.status_code == 429


def test_code_is_single_use(env):
    c, sent, _ = env
    c.post("/api/auth/signup/send-otp", json={"email": "y@mill.in"})
    code = sent["y@mill.in"]
    assert c.post("/api/auth/signup/verify-otp", json={"email": "y@mill.in", "otp": code}).status_code == 200
    assert c.post("/api/auth/signup/verify-otp", json={"email": "y@mill.in", "otp": code}).status_code == 400


def test_token_for_other_email_is_refused(env):
    c, sent, _ = env
    c.post("/api/auth/signup/send-otp", json={"email": "a@mill.in"})
    token = c.post("/api/auth/signup/verify-otp", json={"email": "a@mill.in", "otp": sent["a@mill.in"]}).json()["email_token"]
    r = c.post("/api/auth/signup", json={
        "name": "Bad", "email": "b@mill.in", "role": "owner",
        "password": "Mill2026a", "confirm_password": "Mill2026a", "email_token": token,
    })
    assert r.status_code == 400


def test_email_token_cannot_be_used_to_log_in(env):
    c, sent, _ = env
    c.post("/api/auth/signup/send-otp", json={"email": "t@mill.in"})
    token = c.post("/api/auth/signup/verify-otp", json={"email": "t@mill.in", "otp": sent["t@mill.in"]}).json()["email_token"]
    assert c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_rules(env):
    c, sent, _ = env
    assert _signup(c, sent, email="p@mill.in", pw="short1").status_code == 400          # weak password
    assert _signup(c, sent, email="r@mill.in", role="superuser").status_code == 400     # unknown role
    assert _signup(c, sent, email="d@mill.in").status_code == 201
    assert c.post("/api/auth/signup/send-otp", json={"email": "d@mill.in"}).status_code == 409  # already exists
    assert c.post("/api/auth/signup/send-otp", json={"email": "not-an-email"}).status_code == 400


def test_mismatched_passwords(env):
    c, sent, _ = env
    c.post("/api/auth/signup/send-otp", json={"email": "q@mill.in"})
    token = c.post("/api/auth/signup/verify-otp", json={"email": "q@mill.in", "otp": sent["q@mill.in"]}).json()["email_token"]
    r = c.post("/api/auth/signup", json={
        "name": "Qadir", "email": "q@mill.in", "role": "accountant",
        "password": "Mill2026a", "confirm_password": "Mill2026b", "email_token": token,
    })
    assert r.status_code == 400 and "match" in r.json()["error"]["message"]

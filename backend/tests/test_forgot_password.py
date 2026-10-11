"""Buyer forgot-password: email OTP -> new password. Staff can't use it."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.seed as seed_mod
from app.config import get_settings
from app.database import get_db
from app.main import app


@pytest.fixture()
def c(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    S = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(seed_mod, "engine", engine)
    monkeypatch.setattr(seed_mod, "SessionLocal", S)
    seed_mod.seed()
    s = get_settings()
    monkeypatch.setattr(s, "signup_dev_otp", True)
    monkeypatch.setattr(s, "brevo_api_key", "")

    def override():
        db = S()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_buyer_resets_password(c):
    r = c.post("/api/auth/forgot/send-otp", json={"email": "buyer@everest.test"})
    assert r.status_code == 200, r.text
    code = r.json()["dev_otp"]
    bad = c.post("/api/auth/forgot/reset", json={"email": "buyer@everest.test", "otp": "000000" if code != "000000" else "111111",
                                                 "password": "newpass123", "confirm_password": "newpass123"})
    assert bad.status_code == 400
    ok = c.post("/api/auth/forgot/reset", json={"email": "buyer@everest.test", "otp": code,
                                                "password": "newpass123", "confirm_password": "newpass123"})
    assert ok.status_code == 200, ok.text
    assert c.post("/api/auth/login", json={"email": "buyer@everest.test", "password": "buyer123"}).status_code == 401
    assert c.post("/api/auth/login", json={"email": "buyer@everest.test", "password": "newpass123"}).status_code == 200
    # Code is single use.
    again = c.post("/api/auth/forgot/reset", json={"email": "buyer@everest.test", "otp": code,
                                                   "password": "other1234", "confirm_password": "other1234"})
    assert again.status_code == 400


def test_staff_and_unknown_emails_get_no_code(c):
    for e in ["owner@everest.test", "nobody@example.com"]:
        r = c.post("/api/auth/forgot/send-otp", json={"email": e})
        assert r.status_code == 200 and "dev_otp" not in r.json()

"""Owner login from env, owner creates a manager, manager logs in with the ID.

Run:  cd backend && pytest tests/test_team.py -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as m
from app.bootstrap import ensure_owner_account, ensure_roles
from app.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.security import hash_password


@pytest.fixture()
def env(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    db = Session()
    db.add_all([m.Role(name=n) for n in ["owner", "store_manager", "buyer"]])  # "manager" missing on purpose
    db.commit()
    s = get_settings()
    monkeypatch.setattr(s, "owner_email", "Shubh.Owner@Gmail.com")
    monkeypatch.setattr(s, "owner_password", "Owner2026a")
    monkeypatch.setattr(s, "owner_name", "Shubham Singh")
    ensure_roles(db)
    assert ensure_owner_account(db) == "created"

    def override():
        x = Session()
        try:
            yield x
        finally:
            x.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app), Session
    app.dependency_overrides.clear()


def login(c, who, pw):
    return c.post("/api/auth/login", json={"email": who, "password": pw})


def test_owner_from_env_logs_in_to_owner_menu(env):
    c, _ = env
    r = login(c, "shubh.owner@gmail.com", "Owner2026a")
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["role"] == "owner" and body["user"]["name"] == "Shubham Singh"
    assert any(i["path"] == "/app/team" for i in body["menu"])
    assert login(c, "shubh.owner@gmail.com", "wrong-pass1").status_code == 401


def test_owner_account_password_follows_env(env, monkeypatch):
    _, Session = env
    db = Session()
    assert ensure_owner_account(db) == "unchanged"
    monkeypatch.setattr(get_settings(), "owner_password", "NewPass2026")
    assert ensure_owner_account(db) == "updated"
    u = db.query(m.User).filter_by(email="shubh.owner@gmail.com").one()
    from app.security import verify_password
    assert verify_password("NewPass2026", u.password_hash)


def test_owner_creates_manager_who_logs_in_with_id(env):
    c, _ = env
    tok = login(c, "shubh.owner@gmail.com", "Owner2026a").json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert c.get("/api/team/managers", headers=h).json()["next_login_id"] == "MGR-001"
    r = c.post("/api/team/managers", headers=h, json={
        "name": "Ravi Kumar", "login_id": "mgr-001", "password": "Mgr2026abc", "confirm_password": "Mgr2026abc"})
    assert r.status_code == 201, r.text
    assert r.json()["login_id"] == "MGR-001" and r.json()["email"] is None
    lst = c.get("/api/team/managers", headers=h).json()
    assert [x["login_id"] for x in lst["managers"]] == ["MGR-001"] and lst["next_login_id"] == "MGR-002"

    r = login(c, "mgr-001", "Mgr2026abc")  # ID is case-insensitive
    assert r.status_code == 200 and r.json()["user"]["role"] == "manager"
    assert r.json()["menu"][0]["path"] == "/app/order-desk"


def test_rules(env):
    c, Session = env
    tok = login(c, "shubh.owner@gmail.com", "Owner2026a").json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    ok = {"name": "Ravi", "login_id": "MGR-001", "password": "Mgr2026abc", "confirm_password": "Mgr2026abc"}
    assert c.post("/api/team/managers", headers=h, json=ok).status_code == 201
    assert c.post("/api/team/managers", headers=h, json=ok).status_code == 409                       # ID taken
    assert c.post("/api/team/managers", headers=h, json={**ok, "login_id": "M 1"}).status_code == 400  # bad ID
    assert c.post("/api/team/managers", headers=h, json={**ok, "login_id": "MGR-002", "confirm_password": "x"}).status_code == 400
    assert c.post("/api/team/managers", headers=h, json={**ok, "login_id": "MGR-003", "password": "short", "confirm_password": "short"}).status_code == 400

    # A non-owner can't create managers.
    db = Session()
    buyer_role = db.query(m.Role).filter_by(name="buyer").one()
    db.add(m.User(name="B", email="b@x.in", password_hash=hash_password("Buyer2026a"), role=buyer_role))
    db.commit()
    bt = login(c, "b@x.in", "Buyer2026a").json()["token"]
    assert c.post("/api/team/managers", headers={"Authorization": f"Bearer {bt}"}, json={**ok, "login_id": "MGR-009"}).status_code == 403
    assert c.post("/api/team/managers", json={**ok, "login_id": "MGR-010"}).status_code == 401

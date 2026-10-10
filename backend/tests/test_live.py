"""Live updates: saved changes become events, filtered per role/buyer.

Run:  cd backend && pytest tests/test_live.py -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import live
from app import models as m
from app.database import Base, get_db
from app.main import app
from app.security import create_access_token, hash_password, read_live_ticket


@pytest.fixture()
def env(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    db = Session()
    roles = {n: m.Role(name=n) for n in ["owner", "store_manager", "production_manager", "quality_inspector", "accountant", "buyer"]}
    db.add_all(roles.values())
    b1, b2 = m.Buyer(name="Asha Traders"), m.Buyer(name="Other Co")
    db.add_all([b1, b2])
    db.flush()
    owner = m.User(role=roles["owner"], name="Owner", email="o@t", password_hash=hash_password("x"))
    db.add(owner)
    db.add_all([
        m.Machine(name="Spin-03", type="spinning", current_status="running", hourly_cost=400),
        m.YarnStock(yarn_type="Cotton 40s", colour="Blue", quantity_kg=150, reorder_level_kg=100),
        m.Order(buyer_id=b1.id, order_no="ORD-1", fabric_type="Cotton", colour="Blue", quantity_meters=100, status="confirmed"),
    ])
    db.commit()

    published = []
    monkeypatch.setattr(live.bus, "publish", lambda evs: published.extend(evs))

    def override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    yield Session, published, (b1.id, b2.id), owner.id
    app.dependency_overrides.clear()


def test_machine_breakdown_notifies_owner_and_floor_only(env):
    Session, published, _, _ = env
    db = Session()
    db.query(m.Machine).filter_by(name="Spin-03").one().current_status = "breakdown"
    db.commit()
    ev = [e for e in published if e.topic == "machines"][0]
    assert ev.for_user("owner", None)["message"] == "Spin-03 broke down"
    assert ev.for_user("owner", None)["notify"] is True and ev.level == "alert"
    assert ev.for_user("production_manager", None) is not None
    assert ev.for_user("accountant", None) is None
    assert ev.for_user("buyer", 1) is None


def test_order_stage_reaches_its_buyer_only(env):
    Session, published, (b1, b2), _ = env
    db = Session()
    db.query(m.Order).filter_by(order_no="ORD-1").one().status = "in_quality"
    db.commit()
    ev = [e for e in published if e.topic == "orders"][0]
    assert ev.for_user("owner", None)["message"] == "ORD-1 moved to In quality check"
    assert ev.for_user("buyer", b1)["message"] == "Your order ORD-1 is now In quality check"
    assert ev.for_user("buyer", b2) is None


def test_low_stock_fires_once_when_crossing_the_line(env):
    Session, published, _, _ = env
    db = Session()
    y = db.query(m.YarnStock).one()
    y.quantity_kg = 90  # 150 -> 90, below 100
    db.commit()
    y.quantity_kg = 80  # already below: refresh only, no new alert
    db.commit()
    yarn = [e for e in published if e.topic == "yarn"]
    assert yarn[0].notify and "Low stock: Cotton 40s (Blue)" in yarn[0].message
    assert not yarn[1].notify
    assert yarn[0].for_user("store_manager", None) and yarn[0].for_user("accountant", None) is None


def test_rolled_back_change_sends_nothing(env):
    Session, published, _, _ = env
    db = Session()
    db.query(m.Machine).one().current_status = "idle"
    db.flush()
    db.rollback()
    assert published == []


def test_payment_in_tells_owner_and_that_buyer(env):
    Session, published, (b1, b2), _ = env
    db = Session()
    db.add(m.Payment(direction="incoming", buyer_id=b1, amount=26460))
    db.commit()
    ev = [e for e in published if e.topic == "payments"][0]
    assert ev.for_user("accountant", None)["message"] == "₹26,460 received from Asha Traders"
    assert ev.for_user("buyer", b1)["message"] == "Payment of ₹26,460 recorded"
    assert ev.for_user("buyer", b2) is None


def test_ticket_and_alerts_endpoints(env):
    Session, _, _, owner_id = env
    c = TestClient(app)
    h = {"Authorization": f"Bearer {create_access_token(owner_id, {'role': 'owner'})}"}
    t = c.post("/api/live/ticket", headers=h).json()["ticket"]
    assert read_live_ticket(t) == owner_id
    # The ticket is not a login token.
    assert c.get("/api/auth/me", headers={"Authorization": f"Bearer {t}"}).status_code == 401
    assert c.get("/api/live/stream?ticket=bad").status_code == 401
    db = Session()
    db.query(m.Machine).one().current_status = "breakdown"
    db.commit()
    msgs = [a["message"] for a in c.get("/api/live/alerts", headers=h).json()["alerts"]]
    assert "Spin-03 is broken down" in msgs

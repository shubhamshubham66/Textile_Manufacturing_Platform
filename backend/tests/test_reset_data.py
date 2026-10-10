"""RESET_DATA=empty|demo — wipe keeps roles + env owner; demo reloads the seed.

Run:  cd backend && pytest tests/test_reset_data.py -v
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.seed as seed_mod
from app import models as m


@pytest.fixture()
def Session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    S = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    mp = pytest.MonkeyPatch()
    mp.setattr(seed_mod, "engine", engine)
    mp.setattr(seed_mod, "SessionLocal", S)
    seed_mod.seed()  # October 2026 data
    yield S
    mp.undo()


def _counts(db):
    return {
        "roles": db.query(m.Role).count(),
        "users": db.query(m.User).count(),
        "orders": db.query(m.Order).count(),
        "payments": db.query(m.Payment).count(),
        "machines": db.query(m.Machine).count(),
    }


def test_wipe_removes_business_data_but_keeps_roles(Session):
    from app.reset import wipe_business_data

    db = Session()
    before = _counts(db)
    assert before["orders"] > 0 and before["payments"] > 0 and before["users"] > 0

    deleted = wipe_business_data(db)
    after = _counts(db)

    # Roles survive; everything the business created is gone.
    assert after["roles"] == before["roles"] and after["roles"] > 0
    assert after["users"] == 0
    assert after["orders"] == 0
    assert after["payments"] == 0
    assert after["machines"] == 0
    # The report is non-empty and names the tables that lost rows.
    assert deleted["orders"] == before["orders"]
    assert deleted["payments"] == before["payments"]
    assert "roles" not in deleted
    db.close()


def test_wipe_is_idempotent(Session):
    from app.reset import wipe_business_data

    db = Session()
    wipe_business_data(db)
    second = wipe_business_data(db)  # nothing left to delete
    assert second == {}
    db.close()


def test_demo_reload_restores_the_seed(Session):
    """RESET_DATA=demo path: wipe then re-seed yields the known October figures."""
    from app.reset import wipe_business_data

    db = Session()
    wipe_business_data(db)
    assert db.query(m.Order).count() == 0
    db.close()

    seed_mod.seed()  # the 'demo' branch calls exactly this
    db = Session()
    assert db.query(m.Order).count() == 7  # 7 orders in the clean seed
    assert db.query(m.Payment).filter(m.Payment.direction == "incoming").count() == 2
    db.close()

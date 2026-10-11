"""Owner "closing the books" read-only endpoints: order history + groups,
order slip, raw-material bills, buyer payments, and the band↔section-G tie-out.

Run:  cd backend && pytest tests/test_owner_closing.py -v
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
SEP = "start=2026-09-01&end=2026-09-30"


@pytest.fixture()
def c():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
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
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
    mp.undo()


def tok(c, email, pw):
    return {"Authorization": "Bearer " + c.post("/api/auth/login", json={"email": email, "password": pw}).json()["token"]}


def owner(c):
    return tok(c, "owner@everest.test", "owner123")


def test_order_history_groups_and_counts(c):
    h = owner(c)
    data = c.get(f"/api/reports/orders?{OCT}", headers=h).json()
    counts = data["counts"]
    # 8 seeded orders: closed+dispatched=completed(2), in_quality+2×in_production
    # = ongoing(3), confirmed(1), draft=awaiting(1), cancelled(1).
    assert counts["all"] == 8
    assert counts["completed"] == 2
    assert counts["ongoing"] == 3
    assert counts["confirmed"] == 1
    assert counts["awaiting"] == 1
    assert counts["cancelled"] == 1
    # Every row carries progress, late flag and a cost figure.
    row = next(r for r in data["rows"] if r["order_no"] == "ORD-2001")
    assert "progress_percent" in row and "late" in row and row["total_cost"] > 0


def test_order_slip_matches_cost(c):
    h = owner(c)
    oid = next(r["id"] for r in c.get(f"/api/reports/orders?{OCT}", headers=h).json()["rows"]
               if r["order_no"] == "ORD-2001")
    slip = c.get(f"/api/reports/orders/{oid}/slip?{OCT}", headers=h).json()
    # Slip cost mirrors the cost-per-order row for ORD-2001 (hand-check: yarn 72,000).
    assert slip["cost"]["yarn"] == 72000.00
    cost_row = next(r for r in c.get(f"/api/reports/cost-per-order?{OCT}", headers=h).json()["rows"]
                    if r["order_no"] == "ORD-2001")
    assert slip["cost"]["total"] == cost_row["total_cost"]
    assert slip["cost"]["margin_est"] == cost_row["margin_est"]


def test_band_equals_section_g(c):
    h = owner(c)
    pl = c.get(f"/api/reports/profit-loss?{OCT}", headers=h).json()
    bills = c.get(f"/api/reports/bills?{OCT}", headers=h).json()
    buyer = c.get(f"/api/reports/buyer-payments?{OCT}", headers=h).json()
    wages = c.get(f"/api/reports/wages?{OCT}", headers=h).json()
    # The three section-G totals equal the Month summary band exactly.
    assert buyer["total_received"] == pl["buyer_payments_in"] == 225960.00
    assert bills["total_paid"] == pl["supplier_payments_out"] == 200000.00
    assert wages["paid_in_month"] == pl["wages"] == 8100.00
    assert pl["profit_or_loss"] == 17860.00 and pl["is_profit"] is True


def test_empty_month_is_zeros_not_errors(c):
    h = owner(c)
    orders = c.get(f"/api/reports/orders?{SEP}", headers=h).json()
    # Order history is a running record, so rows still exist, but month costs are 0.
    assert all(r["total_cost"] == 0 for r in orders["rows"])
    bills = c.get(f"/api/reports/bills?{SEP}", headers=h).json()
    assert bills["total_paid"] == 0
    buyer = c.get(f"/api/reports/buyer-payments?{SEP}", headers=h).json()
    assert buyer["total_received"] == 0


def test_slip_pdf_is_pdf(c):
    h = owner(c)
    oid = next(r["id"] for r in c.get(f"/api/reports/orders?{OCT}", headers=h).json()["rows"]
               if r["order_no"] == "ORD-2001")
    r = c.get(f"/api/reports/orders/{oid}/slip/pdf?{OCT}", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_closing_endpoints_forbidden_for_non_owner(c):
    for email, pw in [("accounts@everest.test", "accounts123"), ("store@everest.test", "store123"),
                      ("quality@everest.test", "quality123"), ("buyer@everest.test", "buyer123")]:
        h = tok(c, email, pw)
        for path in ["orders", "bills", "buyer-payments"]:
            assert c.get(f"/api/reports/{path}?{OCT}", headers=h).status_code == 403
        assert c.get("/api/reports/orders/1/slip?" + OCT, headers=h).status_code == 403

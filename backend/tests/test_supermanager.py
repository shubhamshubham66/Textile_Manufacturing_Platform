"""Supermanager control panel: order review workflow, department managers,
workers, instructions, monitors, alerts, activity log, settings and RBAC.

Run:  cd backend && pytest tests/test_supermanager.py -v
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.seed as seed_mod
from app.database import get_db
from app.main import app

FUTURE = (date.today() + timedelta(days=30)).isoformat()


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


@pytest.fixture()
def sm(c):
    owner = login(c, "owner@everest.test", "owner123")
    r = c.post("/api/team/managers", headers=owner, json={
        "name": "Rishab Yadav", "login_id": "MGR-001",
        "password": "manager123", "confirm_password": "manager123"})
    assert r.status_code == 201, r.text
    return login(c, "MGR-001", "manager123")


# ------------------------------ RBAC ------------------------------ #
PAGES = ["overview", "managers", "workers", "tasks", "production", "inventory", "quality",
         "dispatch", "attendance", "accounts", "alerts", "activity", "settings"]


def test_every_page_works_for_supermanager_and_is_closed_to_others(c, sm):
    for p in PAGES:
        assert c.get(f"/api/super/{p}", headers=sm).status_code == 200, p
    for who, pw in [("owner@everest.test", "owner123"), ("store@everest.test", "store123"),
                    ("buyer@everest.test", "buyer123")]:
        h = login(c, who, pw)
        for p in PAGES:
            assert c.get(f"/api/super/{p}", headers=h).status_code == 403, (who, p)


def test_overview_cards_come_from_data(c, sm):
    d = c.get("/api/super/overview", headers=sm).json()
    cards = d["cards"]
    assert cards["department_managers"] == 4  # store, floor, quality, accounts in the seed
    assert cards["workers"] == 4
    statuses = {o["status"] for o in c.get("/api/orders", headers=sm).json()}
    assert cards["confirmed_orders"] == sum(1 for o in c.get("/api/orders", headers=sm).json() if o["status"] == "confirmed")
    assert {r["status"] for r in d["order_progress"]} <= statuses
    assert len(d["departments"]) == 6


# ------------------------- order workflow ------------------------- #
def test_buyer_request_review_clarify_resubmit_confirm(c, sm):
    buyer = login(c, "buyer@everest.test", "buyer123")
    r = c.post("/api/buyer/orders", headers=buyer, json={
        "fabric_type": "Cotton Poplin", "colour": "White", "quantity_meters": 200, "deadline": FUTURE,
        "note": "Need soft finish"})
    assert r.status_code == 201, r.text
    oid = r.json()["id"]
    assert r.json()["status"] == "pending_review"

    # It shows as a pending approval and an alert for the Supermanager.
    ov = c.get("/api/super/overview", headers=sm).json()
    assert oid in [o["id"] for o in ov["pending_approvals"]]
    assert any(a["kind"] == "new_orders" for a in c.get("/api/super/alerts", headers=sm).json()["alerts"])

    rv = c.get(f"/api/orders/{oid}/review", headers=sm).json()
    assert "rate (₹/metre)" in rv["missing"] and rv["can_decide"] is True
    assert "capacity" in rv and "yarn" in rv

    # Not confirmed while the rate is missing.
    assert c.post(f"/api/orders/{oid}/confirm", headers=sm).status_code == 400

    # Ask the buyer a question; the buyer sees it and resubmits.
    assert c.post(f"/api/orders/{oid}/clarify", headers=sm, json={"reason": "x"}).status_code == 400
    r = c.post(f"/api/orders/{oid}/clarify", headers=sm, json={"reason": "Which GSM do you need?"})
    assert r.status_code == 200 and r.json()["status"] == "clarification"
    mine = {o["id"]: o for o in c.get("/api/buyer/orders", headers=buyer).json()}
    assert mine[oid]["review_note"] == "Which GSM do you need?"
    r = c.put(f"/api/buyer/orders/{oid}", headers=buyer, json={
        "fabric_type": "Cotton Poplin", "colour": "White", "quantity_meters": 250, "deadline": FUTURE,
        "note": "120 GSM"})
    assert r.status_code == 200 and r.json()["status"] == "pending_review"

    # Confirm with the rate -> each department gets its instruction.
    r = c.post(f"/api/orders/{oid}/confirm", headers=sm, json={"unit_price": 110})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "confirmed" and r.json()["unit_price"] == 110
    tasks = [t for t in c.get("/api/super/tasks", headers=sm).json()["tasks"] if t["order_id"] == oid]
    depts = {t["department"] for t in tasks}
    assert {"store", "production", "qc", "dispatch"} <= depts
    assert all(t["auto"] for t in tasks)

    acts = c.get("/api/super/activity", headers=sm, params={"category": "order"}).json()["rows"]
    assert any("confirmed" in a["details"] and a["user"] == "Rishab Yadav" for a in acts)


def test_reject_needs_reason_and_owner_cannot_review(c, sm):
    buyer = login(c, "buyer@everest.test", "buyer123")
    oid = c.post("/api/buyer/orders", headers=buyer, json={
        "fabric_type": "Silk", "colour": "Gold", "quantity_meters": 50, "deadline": FUTURE}).json()["id"]
    owner = login(c, "owner@everest.test", "owner123")
    assert c.post(f"/api/orders/{oid}/reject", headers=owner, json={"reason": "No capacity"}).status_code == 403
    assert c.post(f"/api/orders/{oid}/reject", headers=sm, json={}).status_code == 400
    r = c.post(f"/api/orders/{oid}/reject", headers=sm, json={"reason": "We do not weave silk"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    assert c.post(f"/api/orders/{oid}/confirm", headers=sm, json={"unit_price": 100}).status_code == 409
    mine = {o["id"]: o for o in c.get("/api/buyer/orders", headers=buyer).json()}
    assert mine[oid]["review_label"] == "Not accepted"


def test_buyer_cannot_request_past_deadline(c):
    buyer = login(c, "buyer@everest.test", "buyer123")
    r = c.post("/api/buyer/orders", headers=buyer, json={
        "fabric_type": "Denim", "colour": "Blue", "quantity_meters": 10,
        "deadline": date.today().isoformat()})
    assert r.status_code == 400


# ------------------------- department managers ------------------------- #
def test_manage_department_managers(c, sm):
    r = c.post("/api/super/managers", headers=sm, json={
        "name": "Priya Nair", "email": "priya@everest.test", "department": "purchase",
        "password": "purchase12", "confirm_password": "purchase12"})
    assert r.status_code == 201, r.text
    m = r.json()
    assert m["department"] == "purchase" and m["role"] == "store_manager"
    assert "password" not in m and "password_hash" not in m
    uid = m["id"]

    # Edit: move to QC -> role follows the department.
    r = c.put(f"/api/super/managers/{uid}", headers=sm, json={
        "name": "Priya Nair", "email": "priya@everest.test", "department": "qc"})
    assert r.status_code == 200 and r.json()["role"] == "quality_inspector"

    # Reset password, then deactivate -> cannot sign in.
    assert c.post(f"/api/super/managers/{uid}/reset-password", headers=sm,
                  json={"password": "short", "confirm_password": "short"}).status_code == 400
    r = c.post(f"/api/super/managers/{uid}/reset-password", headers=sm,
               json={"password": "newpass123", "confirm_password": "newpass123"})
    assert r.status_code == 200 and "password" not in r.text.replace('"reset"', "")
    login(c, "priya@everest.test", "newpass123")
    c.post(f"/api/super/managers/{uid}/active", headers=sm, json={"active": False})
    assert c.post("/api/auth/login", json={"email": "priya@everest.test", "password": "newpass123"}).status_code != 200

    # The owner account is not a department manager.
    assert c.post("/api/super/managers/1/active", headers=sm, json={"active": False}).status_code == 404


# ------------------------- workers ------------------------- #
def test_workers_add_edit_filter_deactivate(c, sm):
    lst = c.get("/api/super/workers", headers=sm).json()
    floor_mgr = next(m for m in lst["managers"] if m["department"] == "production")
    r = c.post("/api/super/workers", headers=sm, json={
        "name": "Sunil Patil", "role_on_floor": "Loom operator", "daily_wage": 620,
        "department": "production", "manager_user_id": floor_mgr["id"]})
    assert r.status_code == 201, r.text
    wid = r.json()["id"]
    assert r.json()["manager"]["id"] == floor_mgr["id"]
    found = c.get("/api/super/workers", headers=sm, params={"department": "production", "q": "sunil"}).json()["workers"]
    assert [w["id"] for w in found] == [wid]
    assert c.post("/api/super/workers", headers=sm, json={
        "name": "X Y", "daily_wage": 1, "department": "nowhere"}).status_code == 400
    c.post(f"/api/super/workers/{wid}/active", headers=sm, json={"active": False})
    assert c.get("/api/super/workers", headers=sm, params={"status": "inactive"}).json()["workers"][0]["id"] == wid


# ------------------------- instructions ------------------------- #
def test_assign_instruction_manager_updates_progress(c, sm):
    meta = c.get("/api/super/tasks", headers=sm).json()
    floor_mgr = next(m for m in meta["managers"] if m["department"] == "production")
    store_mgr = next(m for m in meta["managers"] if m["department"] == "store")
    # Manager must run the chosen department.
    assert c.post("/api/super/tasks", headers=sm, json={
        "title": "Service loom 2", "department": "production", "manager_user_id": store_mgr["id"],
        "priority": "high"}).status_code == 400
    r = c.post("/api/super/tasks", headers=sm, json={
        "title": "Service loom 2", "details": "Oil and check belts", "department": "production",
        "manager_user_id": floor_mgr["id"], "priority": "urgent",
        "deadline": (date.today() - timedelta(days=1)).isoformat()})
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    assert r.json()["shown_status"] == "delayed"  # past deadline and not done

    floor = login(c, "floor@everest.test", "floor123")
    mine = c.get("/api/tasks/mine", headers=floor).json()
    assert tid in [t["id"] for t in mine["tasks"]]
    store = login(c, "store@everest.test", "store123")
    assert c.post(f"/api/tasks/{tid}/progress", headers=store, json={"status": "completed"}).status_code == 404
    r = c.post(f"/api/tasks/{tid}/progress", headers=floor, json={"status": "completed", "note": "Done, belts replaced"})
    assert r.status_code == 200 and r.json()["shown_status"] == "completed"
    ups = c.get(f"/api/super/tasks/{tid}/updates", headers=sm).json()
    assert ups[0]["note"] == "Done, belts replaced"


# ------------------------- attendance + activity ------------------------- #
def test_attendance_exception_is_recorded_with_reason(c, sm):
    att = c.get("/api/super/attendance", headers=sm).json()
    emp = att["rows"][0]["employee_id"]
    assert c.post("/api/super/attendance/exception", headers=sm, json={
        "employee_id": emp, "work_date": date.today().isoformat(), "status": "present", "reason": ""}).status_code == 400
    r = c.post("/api/super/attendance/exception", headers=sm, json={
        "employee_id": emp, "work_date": date.today().isoformat(), "status": "present",
        "reason": "Was at the dye house, register missed"})
    assert r.status_code == 200
    rows = c.get("/api/super/activity", headers=sm, params={"category": "attendance"}).json()["rows"]
    assert any("register missed" in a["details"] for a in rows)
    assert c.get("/api/super/attendance", headers=sm).json()["totals"]["present"] >= 1


# ------------------------- settings + search ------------------------- #
def test_settings_and_alert_preferences(c, sm):
    r = c.put("/api/super/settings", headers=sm, json={"capacity_m_per_machine_day": 650,
                                                       "alerts": {"qc_pending": False}})
    assert r.status_code == 200
    assert r.json()["capacity_m_per_machine_day"] == 650 and r.json()["alerts"]["qc_pending"] is False
    assert not any(a["kind"] == "qc_pending" for a in c.get("/api/super/alerts", headers=sm).json()["alerts"])
    assert c.put("/api/super/settings", headers=sm, json={"capacity_m_per_machine_day": -1}).status_code == 400


def test_search_finds_orders_and_workers(c, sm):
    d = c.get("/api/super/search", headers=sm, params={"q": "ORD-2001"}).json()
    assert d["orders"][0]["label"] == "ORD-2001"
    assert c.get("/api/super/search", headers=sm, params={"q": "Kavita"}).json()["workers"]

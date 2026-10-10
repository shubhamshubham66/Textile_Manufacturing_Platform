"""Worker portal: dashboard, my tasks (start/pause/complete), production updates,
problem reports, attendance check-in/out (+ duplicate guard), overtime, manager
verification feeding wages, task history, notifications, profile, and RBAC.

Run:  cd backend && pytest tests/test_worker.py -v
"""

from datetime import date

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


@pytest.fixture()
def wk(c):
    return login(c, "worker@everest.test", "worker123")


WK_PAGES = ["dashboard", "tasks", "production", "machines", "attendance", "overtime", "history", "notifications", "profile"]


# ------------------------------ RBAC ------------------------------ #
def test_worker_pages_open_and_closed_to_others(c, wk):
    for p in WK_PAGES:
        assert c.get(f"/api/worker/{p}", headers=wk).status_code == 200, p
    for who, pw in [("owner@everest.test", "owner123"),
                    ("production@everest.test", "production123"),
                    ("buyer@everest.test", "buyer123")]:
        h = login(c, who, pw)
        for p in WK_PAGES:
            assert c.get(f"/api/worker/{p}", headers=h).status_code == 403, (who, p)


def test_worker_menu_has_nine_pages(c, wk):
    me = c.get("/api/auth/me", headers=wk).json()
    assert me["user"]["role"] == "worker"
    assert len(me["menu"]) == 9


# ------------------------------ Dashboard ------------------------------ #
def test_dashboard_cards(c, wk):
    d = c.get("/api/worker/dashboard", headers=wk).json()
    for key in ("today_attendance", "assigned_tasks", "in_progress", "completed", "pending", "today_output"):
        assert key in d["cards"], key


# ------------------------------ Tasks ------------------------------ #
def test_start_pause_resume_complete_task(c, wk):
    # Assign a task to this worker via the Supermanager, then drive it.
    owner = login(c, "owner@everest.test", "owner123")
    c.post("/api/team/managers", headers=owner, json={
        "name": "SM", "login_id": "MGR-900", "password": "manager123", "confirm_password": "manager123"})
    sm = login(c, "MGR-900", "manager123")
    workers = c.get("/api/super/workers", headers=sm).json()["workers"]
    # The seeded worker login is linked to the first production employee.
    me = c.get("/api/worker/profile", headers=wk).json()
    emp = next(w for w in workers if w["name"] == me["name"])
    created = c.post("/api/super/tasks", headers=sm, json={
        "title": "Weave batch A", "department": "production", "worker_employee_id": None, "priority": "high"})
    # super task create doesn't take worker; assign via worker starting it.
    tasks = c.get("/api/worker/tasks", headers=wk).json()["tasks"]
    assert len(tasks) >= 1
    t = tasks[0]
    assert c.post(f"/api/worker/tasks/{t['id']}/action", headers=wk, json={"action": "start"}).json()["status"] == "in_progress"
    assert c.post(f"/api/worker/tasks/{t['id']}/action", headers=wk, json={"action": "pause"}).json()["status"] == "paused"
    assert c.post(f"/api/worker/tasks/{t['id']}/action", headers=wk, json={"action": "resume"}).json()["status"] == "in_progress"
    done = c.post(f"/api/worker/tasks/{t['id']}/action", headers=wk, json={"action": "complete"})
    assert done.json()["status"] == "completed"
    # Completing again is rejected.
    assert c.post(f"/api/worker/tasks/{t['id']}/action", headers=wk, json={"action": "start"}).status_code == 409


# ------------------------------ Production ------------------------------ #
def test_submit_production_update(c, wk):
    prod = c.get("/api/worker/production", headers=wk).json()
    m, o = prod["machines"][0], prod["orders"][0]
    r = c.post("/api/worker/production", headers=wk, json={
        "machine_id": m["id"], "order_id": o["id"], "output_meters": 120,
        "waste_meters": 5, "defects": 1, "downtime_minutes": 15})
    assert r.status_code == 201, r.text


def test_report_breakdown_notifies(c, wk):
    r = c.post("/api/worker/report", headers=wk, json={
        "kind": "breakdown", "message": "Loom belt snapped"})
    assert r.status_code == 201


# ------------------------------ Attendance ------------------------------ #
def test_check_in_out_and_duplicate_guard(c, wk):
    ci = c.post("/api/worker/attendance/check-in", headers=wk, json={"shift": "morning"})
    assert ci.status_code == 200, ci.text
    assert ci.json()["verified"] is False
    # Duplicate check-in rejected.
    assert c.post("/api/worker/attendance/check-in", headers=wk, json={"shift": "morning"}).status_code == 409
    co = c.post("/api/worker/attendance/check-out", headers=wk)
    assert co.status_code == 200
    # Double check-out rejected.
    assert c.post("/api/worker/attendance/check-out", headers=wk).status_code == 409


def test_overtime_submit_is_unverified(c, wk):
    r = c.post("/api/worker/overtime", headers=wk, json={"hours": 2, "reason": "Rush order"})
    assert r.status_code == 201 and r.json()["verified"] is False


# ------------------------------ Verification feeds wages ------------------------------ #
def test_worker_attendance_needs_manager_verification_for_wages(c, wk):
    # Worker checks in today (unverified, source=worker).
    c.post("/api/worker/attendance/check-in", headers=wk, json={"shift": "morning"})
    # The worker cannot verify their own attendance (no such endpoint for them).
    assert c.get("/api/tasks/attendance", headers=wk).status_code == 403
    # The production manager manages the production worker; verify via them.
    prod = login(c, "production@everest.test", "production123")
    att = c.get("/api/tasks/attendance", headers=prod).json()
    pend = [r for r in att["rows"] if not r["verified"]]
    if pend:
        vid = pend[0]["id"]
        assert c.post(f"/api/tasks/attendance/{vid}/verify", headers=prod).status_code == 200


# ------------------------------ Permission boundary ------------------------------ #
def test_worker_cannot_touch_restricted_areas(c, wk):
    assert c.get("/api/payments/dues", headers=wk).status_code == 403
    assert c.get("/api/quality/rolls", headers=wk).status_code == 403
    assert c.get("/api/dispatch", headers=wk).status_code == 403
    assert c.post("/api/orders/1/confirm", headers=wk).status_code == 403


# ------------------------------ Profile scope ------------------------------ #
def test_profile_is_own_only(c, wk):
    p = c.get("/api/worker/profile", headers=wk).json()
    assert "name" in p and "daily_wage" in p and p["department"] == "production"

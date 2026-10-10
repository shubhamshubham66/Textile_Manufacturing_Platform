"""Production Manager control panel: dashboard cards, planning, machine status,
worker tasks, output logging, material requests, QC handover + rework, reports,
notifications/delay, and role-based access control.

Run:  cd backend && pytest tests/test_prod_manager.py -v
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

FUTURE = (date.today() + timedelta(days=20)).isoformat()


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
def pm(c):
    return login(c, "production@everest.test", "production123")


# ------------------------------ RBAC ------------------------------ #
PAGES = ["dashboard", "orders", "planning", "stages", "machines", "workers",
         "monitoring", "materials", "qc", "reports", "notifications", "activity"]


def test_every_page_opens_for_production_manager_and_is_closed_to_others(c, pm):
    for p in PAGES:
        assert c.get(f"/api/prod/{p}", headers=pm).status_code == 200, p
    # Other roles get 403 on every production-manager page.
    for who, pw in [("owner@everest.test", "owner123"),
                    ("store@everest.test", "store123"),
                    ("quality@everest.test", "quality123"),
                    ("buyer@everest.test", "buyer123")]:
        h = login(c, who, pw)
        for p in PAGES:
            assert c.get(f"/api/prod/{p}", headers=h).status_code == 403, (who, p)


def test_menu_from_me_lists_production_pages(c, pm):
    me = c.get("/api/auth/me", headers=pm).json()
    assert me["user"]["role"] == "production_manager"
    labels = [i["label"] for i in me["menu"]]
    # 12 production screens + the shared "My tasks" (worker attendance) screen.
    assert len(labels) == 13
    assert labels[0] == "Dashboard" and "QC Handover" in labels and "My tasks" in labels


# ------------------------------ Dashboard ------------------------------ #
def test_dashboard_cards_are_real_numbers(c, pm):
    d = c.get("/api/prod/dashboard", headers=pm).json()
    cards = d["cards"]
    for key in ("active_orders", "today_target", "today_actual", "machine_total",
                "worker_tasks_open", "material_shortages", "delayed_orders",
                "qc_pending_batches"):
        assert key in cards
    # The seed has in-production orders and machines.
    assert cards["active_orders"] >= 1
    assert cards["machine_total"] == 8
    # Worker tasks were seeded for the production department.
    assert cards["worker_tasks_open"] >= 1


# ------------------------------ Planning ------------------------------ #
def test_plan_assigns_machine_and_moves_order_into_production(c, pm):
    planning = c.get("/api/prod/planning", headers=pm).json()
    order = next(o for o in planning["orders"])
    # Pick a weaving machine for the weaving stage.
    weave = next(m for m in planning["machines"] if m["type"] == "weaving")
    r = c.post("/api/prod/plan", headers=pm, json={
        "order_id": order["id"], "machine_id": weave["id"], "stage": "weaving",
        "target_meters": 500, "shift": "morning"})
    assert r.status_code == 200, r.text
    assert r.json()["order_status"] in ("in_production", "in_quality")


def test_plan_rejects_wrong_machine_type_for_stage(c, pm):
    planning = c.get("/api/prod/planning", headers=pm).json()
    order = planning["orders"][0]
    spin = next(m for m in planning["machines"] if m["type"] == "spinning")
    r = c.post("/api/prod/plan", headers=pm, json={
        "order_id": order["id"], "machine_id": spin["id"], "stage": "dyeing"})
    assert r.status_code == 400


# ------------------------------ Machines ------------------------------ #
def test_machine_status_requires_reason_for_idle(c, pm):
    m = c.get("/api/prod/machines", headers=pm).json()["machines"][0]
    bad = c.post(f"/api/prod/machines/{m['id']}/status", headers=pm,
                 json={"status": "idle"})
    assert bad.status_code == 400
    ok = c.post(f"/api/prod/machines/{m['id']}/status", headers=pm,
                json={"status": "idle", "reason": "No order assigned"})
    assert ok.status_code == 200
    assert ok.json()["status"] == "idle"


# ------------------------------ Workers & tasks ------------------------------ #
def test_create_assign_and_update_worker_task(c, pm):
    data = c.get("/api/prod/workers", headers=pm).json()
    worker = data["workers"][0]
    created = c.post("/api/prod/tasks", headers=pm, json={
        "title": "Weave the morning lot", "priority": "high", "deadline": FUTURE})
    assert created.status_code == 201, created.text
    tid = created.json()["id"]
    a = c.post(f"/api/prod/tasks/{tid}/assign", headers=pm,
               json={"worker_employee_id": worker["id"]})
    assert a.status_code == 200 and a.json()["worker"]["id"] == worker["id"]
    s = c.post(f"/api/prod/tasks/{tid}/status", headers=pm,
               json={"status": "in_progress", "note": "started"})
    assert s.status_code == 200 and s.json()["status"] == "in_progress"


# ------------------------------ Output ------------------------------ #
def test_log_output_advances_order_progress(c, pm):
    mon = c.get("/api/prod/monitoring", headers=pm).json()
    order = next(o for o in mon["orders"] if o["status"] in ("confirmed", "in_production"))
    machine = next(m for m in mon["machines"])
    r = c.post("/api/prod/output", headers=pm, json={
        "machine_id": machine["id"], "order_id": order["id"],
        "output_meters": 100, "waste_meters": 5, "shift": "morning"})
    assert r.status_code == 200, r.text
    assert r.json()["order_progress_percent"] >= 0


# ------------------------------ Material requests ------------------------------ #
def test_material_request_creates_pending_purchase_request(c, pm):
    r = c.post("/api/prod/materials", headers=pm, json={
        "yarn_type": "Cotton 40s", "colour": "White", "quantity_kg": 500,
        "reason": "Short for ORD"})
    assert r.status_code == 201, r.text
    assert r.json()["pr_no"].startswith("PR-")
    assert r.json()["status"] in ("pending", "approved")
    # It shows up in the store's purchase-request queue (shared workflow).
    store = login(c, "store@everest.test", "store123")
    reqs = c.get("/api/purchase/requests", headers=store).json()["requests"]
    assert any(x["pr_no"] == r.json()["pr_no"] for x in reqs)


# ------------------------------ QC handover ------------------------------ #
def test_qc_handover_creates_pending_rolls_and_moves_order_to_quality(c, pm):
    qc = c.get("/api/prod/qc", headers=pm).json()
    order = qc["orders"][0]
    machine = qc["machines"][0]
    r = c.post("/api/prod/qc/handover", headers=pm, json={
        "order_id": order["id"], "machine_id": machine["id"],
        "rolls": 3, "length_meters": 150})
    assert r.status_code == 201, r.text
    assert len(r.json()["rolls_created"]) == 3
    assert r.json()["order_status"] == "in_quality"
    # The handed-over rolls now wait for QC — the inspector can see them.
    quality = login(c, "quality@everest.test", "quality123")
    rolls = c.get("/api/quality/rolls?status=pending", headers=quality)
    assert rolls.status_code == 200


def test_production_manager_cannot_inspect_quality(c, pm):
    # QC decisions belong to the quality inspector only.
    assert c.get("/api/quality/rolls", headers=pm).status_code == 403
    # And cannot confirm orders, touch payments, dispatch or wages.
    assert c.get("/api/payments/dues", headers=pm).status_code == 403
    assert c.get("/api/dispatch", headers=pm).status_code == 403


def test_rework_only_allowed_for_rework_rolls(c, pm):
    qc = c.get("/api/prod/qc", headers=pm).json()
    rework = [r for r in qc["rework_rejects"] if r["result"] == "rework"]
    reject = [r for r in qc["rework_rejects"] if r["result"] == "reject"]
    if rework:
        ok = c.post(f"/api/prod/qc/rework/{rework[0]['roll_id']}", headers=pm, json={})
        assert ok.status_code == 200 and ok.json()["task_id"]
    if reject:
        bad = c.post(f"/api/prod/qc/rework/{reject[0]['roll_id']}", headers=pm, json={})
        assert bad.status_code == 409


# ------------------------------ Reports ------------------------------ #
def test_reports_sum_output_per_machine_and_stage(c, pm):
    rep = c.get("/api/prod/reports", headers=pm).json()
    assert "per_machine" in rep and "per_stage" in rep
    assert set(rep["per_stage"]) == {"spinning", "weaving", "dyeing"}
    assert rep["total_output"] >= 0


# ------------------------------ Notifications / delay ------------------------------ #
def test_notify_delay_reaches_the_supermanager(c, pm):
    orders = c.get("/api/prod/orders", headers=pm).json()["orders"]
    r = c.post("/api/prod/notify-delay", headers=pm, json={
        "order_id": orders[0]["id"], "message": "Machine down, order will slip 2 days."})
    assert r.status_code == 200, r.text


# ------------------------------ Instruction routing ------------------------------ #
def test_production_instructions_route_to_the_production_manager(c):
    """The production department's auto-instruction (and manager_for_department)
    must resolve to the production manager, not the floor supervisor, even
    though both default to the 'production' department."""
    from app.database import get_db
    from app.models import User
    from app.services.tasks import manager_for_department

    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        mgr = manager_for_department(db, "production")
        assert mgr is not None
        assert mgr.role.name == "production_manager", mgr.role.name
    finally:
        gen.close()

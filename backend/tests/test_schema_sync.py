"""A database made before a model gained a column gets that column on startup
(the cause of the HTTP 500s on owner reports after machines.power_overhead_cost
was added). Run:  cd backend && pytest tests/test_schema_sync.py -v
"""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401 - registers tables
from app.database import Base
from app.schema_sync import add_missing_columns


def test_adds_missing_column_with_default_and_keeps_rows():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    # An "old" machines table without power_overhead_cost, holding one row.
    with engine.begin() as c:
        c.execute(text(
            "CREATE TABLE machines (id INTEGER PRIMARY KEY, name VARCHAR(60), machine_type VARCHAR(30), "
            "status VARCHAR(20), hourly_cost NUMERIC(10,2))"
        ))
        c.execute(text("INSERT INTO machines (id, name, machine_type, status, hourly_cost) VALUES (1, 'Spin-01', 'spinning', 'running', 250)"))
    Base.metadata.create_all(bind=engine)  # makes the other tables, leaves machines alone

    added = add_missing_columns(engine, Base.metadata)

    assert "machines.power_overhead_cost" in added
    cols = {c["name"] for c in inspect(engine).get_columns("machines")}
    assert "power_overhead_cost" in cols
    with engine.connect() as c:
        row = c.execute(text("SELECT name, power_overhead_cost FROM machines")).one()
    assert row[0] == "Spin-01" and float(row[1]) == 0.0


def test_nothing_to_add_on_a_fresh_database():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    assert add_missing_columns(engine, Base.metadata) == []

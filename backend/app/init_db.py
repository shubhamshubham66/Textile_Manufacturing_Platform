"""Create all tables from the ORM models.

Usage:
    python -m app.init_db

For a hackathon this is simpler than running Alembic. The schema works on both
SQLite (dev default) and PostgreSQL. If you later need migrations, Alembic can be
layered on top of these same models.
"""

from app.database import Base, engine
from app import models  # noqa: F401 - import registers all models on Base.metadata


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    print(f"Tables created on {engine.dialect.name}: {len(Base.metadata.tables)} tables")


if __name__ == "__main__":
    init_db()

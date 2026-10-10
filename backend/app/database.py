"""Database engine, session factory and declarative base.

Works with both SQLite (dev default) and PostgreSQL (demo/prod) by reading
DATABASE_URL from settings. SQLite needs a special connect arg for threads.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()

DATABASE_URL = settings.sqlalchemy_database_url

# SQLite requires check_same_thread=False when used with a web server.
# PostgreSQL: pin the session to UTC. Columns are `timestamp without time zone`
# and the app writes UTC datetimes; without this, a server running in local time
# (e.g. IST) silently shifts every timestamp and breaks idle-loss hours.
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
elif DATABASE_URL.startswith("postgresql"):
    connect_args = {"options": "-c timezone=utc"}
else:
    connect_args = {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def get_db():
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

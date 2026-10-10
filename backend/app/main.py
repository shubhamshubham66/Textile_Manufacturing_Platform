"""FastAPI application entrypoint.

Phase 2 provides a health-check endpoint. Feature routers (orders, yarn,
production, quality, dispatch, payments, wages, reports) and the chatbot router
(owned by the mini developer under backend/chatbot/) are added in later phases.
"""

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.database import engine

settings = get_settings()

app = FastAPI(title=settings.app_name, version=settings.app_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    """Liveness + DB connectivity check.

    Returns status "ok" when the DB responds, "degraded" otherwise. The frontend
    polls this to show backend/database connectivity.
    """
    db_ok = False
    db_error = None
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:  # noqa: BLE001 - report any DB failure to the client
        db_error = str(exc)

    return {
        "status": "ok" if db_ok else "degraded",
        "service": settings.app_name,
        "version": settings.app_version,
        "database": {
            "connected": db_ok,
            "dialect": engine.dialect.name,
            "error": db_error,
        },
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/")
def root():
    return {"message": settings.app_name, "docs": "/docs", "health": "/api/health"}

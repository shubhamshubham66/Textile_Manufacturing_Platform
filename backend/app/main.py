"""FastAPI application entrypoint.

Health check, all feature routers, and the chatbot proxy router (owned by the
mini developer under backend/chatbot/).
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text

from app.config import get_settings
from app.database import engine
from app.routers import auth as auth_router
from app.routers import buyer as buyer_router
from app.routers import dispatch as dispatch_router
from app.routers import orders as orders_router
from app.routers import payments as payments_router
from app.routers import production as production_router
from app.routers import quality as quality_router
from app.routers import reports as reports_router
from app.routers import signup as signup_router
from app.routers import live as live_router
from app.routers import team as team_router
from app.routers import wages as wages_router
from app.routers import yarn as yarn_router
from chatbot.router import router as chatbot_router

settings = get_settings()
log = logging.getLogger("uvicorn.error")


def prepare_database() -> None:
    """Create tables and, if there are no users yet, load the demo data.

    Runs on every start but never touches a database that already has users,
    so real data is safe. Lets a fresh Render + PostgreSQL deploy come up ready
    for judging without needing a shell to run init_db / seed by hand.
    """
    from app import models  # noqa: F401 - registers all tables on Base.metadata
    from app.database import Base, SessionLocal

    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
        # create_all never alters existing tables; add any new model columns.
        from app.schema_sync import add_missing_columns

        add_missing_columns(engine, Base.metadata)

    # One-time RESET_DATA=empty|demo (destructive, logged). When it runs it also
    # handles any reseeding itself, so skip the empty-DB seed below to avoid
    # double-seeding (and to honour an intentional 'empty' wipe).
    reset_requested = (settings.reset_data or "").strip().lower() in ("empty", "demo")
    if reset_requested:
        from app.reset import run_reset_if_requested

        run_reset_if_requested()

    if settings.seed_if_empty and not reset_requested:
        db = SessionLocal()
        try:
            empty = db.query(models.User).first() is None
        finally:
            db.close()
        if empty:
            from app.seed import seed

            log.info("Database is empty: loading demo data")
            seed()

    # New roles (e.g. manager) and the real owner login from OWNER_EMAIL /
    # OWNER_PASSWORD. Both are no-ops when there is nothing to do.
    from app.bootstrap import ensure_owner_account, ensure_roles

    db = SessionLocal()
    try:
        ensure_roles(db)
        ensure_owner_account(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    import asyncio

    from app.live import bus  # registers the session hooks for live updates

    bus.bind_loop(asyncio.get_running_loop())
    try:
        prepare_database()
    except Exception:  # noqa: BLE001 - keep the API up; /api/health reports DB state
        log.exception("Database preparation failed")
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router.router)
app.include_router(signup_router.router)
app.include_router(live_router.router)
app.include_router(team_router.router)
app.include_router(orders_router.router)
app.include_router(yarn_router.router)
app.include_router(production_router.router)
app.include_router(quality_router.router)
app.include_router(dispatch_router.router)
app.include_router(payments_router.router)
app.include_router(wages_router.router)
app.include_router(reports_router.router)
app.include_router(buyer_router.router)
app.include_router(chatbot_router)  # AI assistant proxy (backend/chatbot/)


# ---- Uniform error shape (matches API_CONTRACT.md) ----
_STATUS_CODE = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    429: "TOO_MANY_REQUESTS",
    502: "UPSTREAM_ERROR",
    503: "UNAVAILABLE",
}


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    code = _STATUS_CODE.get(exc.status_code, "ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": str(exc.detail)}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    msg = first.get("msg", "Invalid request")
    loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": f"{loc}: {msg}" if loc else msg,
            }
        },
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

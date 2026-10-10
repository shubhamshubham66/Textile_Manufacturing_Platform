"""FastAPI application entrypoint.

Phase 2 provides a health-check endpoint. Feature routers (orders, yarn,
production, quality, dispatch, payments, wages, reports) and the chatbot router
(owned by the mini developer under backend/chatbot/) are added in later phases.
"""

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
from app.routers import dispatch as dispatch_router
from app.routers import orders as orders_router
from app.routers import production as production_router
from app.routers import quality as quality_router
from app.routers import yarn as yarn_router

settings = get_settings()

app = FastAPI(title=settings.app_name, version=settings.app_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router.router)
app.include_router(orders_router.router)
app.include_router(yarn_router.router)
app.include_router(production_router.router)
app.include_router(quality_router.router)
app.include_router(dispatch_router.router)


# ---- Uniform error shape (matches API_CONTRACT.md) ----
_STATUS_CODE = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
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

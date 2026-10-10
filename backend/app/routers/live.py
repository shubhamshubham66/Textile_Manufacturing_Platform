"""Live updates over Server-Sent Events.

- POST /api/live/ticket   (logged in) -> one-minute ticket for the stream
- GET  /api/live/stream?ticket=...    -> text/event-stream of this user's events
- GET  /api/live/alerts   (logged in) -> what needs attention right now, so the
                                         bell isn't empty when the page opens

Events are filtered per user (role; buyers only see their own orders). A
heartbeat goes out every 15 s so proxies keep the connection open; if it drops,
the browser takes a new ticket, reconnects and refreshes its data.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import rbac
from app.config import get_settings
from app.database import SessionLocal, get_db
from app.deps import get_current_user
from app.live import bus
from app.models import Machine, Roll, User, YarnStock
from app.security import create_live_ticket, read_live_ticket

router = APIRouter(prefix="/api/live", tags=["live"])

HEARTBEAT_SECONDS = 15


@router.post("/ticket")
def ticket(user: User = Depends(get_current_user)):
    return {"ticket": create_live_ticket(user.id), "expires_in": 60}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/stream")
async def stream(request: Request, ticket: str):
    uid = read_live_ticket(ticket)
    if uid is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Live ticket expired. Reconnecting.")
    db = SessionLocal()
    try:
        user = db.get(User, uid)
        if user is None or not user.is_active:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
        role, buyer_id = user.role.name, user.buyer_id
    finally:
        db.close()

    bus.bind_loop(asyncio.get_running_loop())
    queue = bus.subscribe()

    async def gen():
        try:
            yield "retry: 3000\n\n"
            yield _sse("hello", {"role": role})
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                data = ev.for_user(role, buyer_id)
                if data is not None:
                    yield _sse("change", data)
        finally:
            bus.unsubscribe(queue)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/alerts")
def alerts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Current things worth a look, for this role. Same shape as live events."""
    role = user.role.name
    out: list[dict] = []
    if role in (rbac.ROLE_OWNER, rbac.ROLE_FLOOR_SUPERVISOR):
        for mch in db.query(Machine).filter(Machine.current_status.in_(["breakdown", "idle"])).order_by(Machine.name):
            down = mch.current_status == "breakdown"
            out.append({"topic": "machines", "level": "alert" if down else "warn",
                        "message": f"{mch.name} {'is broken down' if down else 'is idle'}"})
    if role in (rbac.ROLE_OWNER, rbac.ROLE_STORE_MANAGER):
        fallback = get_settings().default_reorder_level_kg
        for y in db.query(YarnStock).order_by(YarnStock.yarn_type):
            level = float(y.reorder_level_kg or 0) or fallback
            if float(y.quantity_kg or 0) < level:
                out.append({"topic": "yarn", "level": "warn",
                            "message": f"Low stock: {y.yarn_type} ({y.colour}) at {float(y.quantity_kg or 0):,.0f} kg"})
    if role in (rbac.ROLE_OWNER, rbac.ROLE_QUALITY_INSPECTOR):
        pending = db.query(Roll).filter(Roll.status == "pending").count()
        if pending:
            out.append({"topic": "quality", "level": "info",
                        "message": f"{pending} roll{'s' if pending != 1 else ''} waiting for inspection"})
    return {"alerts": out, "listeners": bus.subscriber_count()}

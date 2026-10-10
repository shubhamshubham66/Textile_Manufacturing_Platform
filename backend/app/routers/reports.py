"""Owner reports + dashboard — scene 6.

Owner (resources "reports" / "dashboard"); every endpoint 403s for other roles.
All reports accept an optional month window via ?start=YYYY-MM-DD&end=YYYY-MM-DD.
When omitted they default to the CURRENT calendar month so a fresh page already
shows "this month".

  GET /api/reports/cost-per-order   yarn + wages + machine cost per order
  GET /api/reports/machines         output, running/idle/breakdown h, idle loss
  GET /api/reports/profit-loss      month cash-basis net (in − bills − wages paid)
  GET /api/reports/wages            owner wages view (total, per employee, order)
  GET /api/reports/dashboard        cards + orders-by-stage + idle loss by reason
"""

from __future__ import annotations

import calendar
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import require_resource
from app.models import Machine, Order, YarnStock
from app.services.owner_closing import (
    buyer_payments_list,
    order_history,
    order_slip,
    raw_material_bills,
)
from app.services.reports import (
    cost_per_order,
    idle_loss_by_reason,
    idle_loss_total,
    machine_report,
    profit_or_loss,
    wages_report,
)

settings = get_settings()
router = APIRouter(prefix="/api/reports", tags=["reports"])


def _month_window(start: date | None, end: date | None) -> tuple[date, date]:
    """Resolve the reporting window. Default = the current calendar month.

    If only one bound is given we keep it and fill the other from the current
    month, so partial queries never explode.
    """
    today = date.today()
    if start is None and end is None:
        first = today.replace(day=1)
        last = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        return first, last
    if start is None:
        start = end.replace(day=1)
    if end is None:
        end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
    return start, end


@router.get("/cost-per-order")
def cost_per_order_report(
    start: date | None = Query(None),
    end: date | None = Query(None),
    _=Depends(require_resource("reports")),
    db: Session = Depends(get_db),
):
    s, e = _month_window(start, end)
    return {"start": s.isoformat(), "end": e.isoformat(), "rows": cost_per_order(db, s, e)}


@router.get("/machines")
def machines_report(
    start: date | None = Query(None),
    end: date | None = Query(None),
    _=Depends(require_resource("reports")),
    db: Session = Depends(get_db),
):
    s, e = _month_window(start, end)
    report = machine_report(db, s, e)
    return {"start": s.isoformat(), "end": e.isoformat(), **report}


@router.get("/profit-loss")
def profit_loss_report(
    start: date | None = Query(None),
    end: date | None = Query(None),
    _=Depends(require_resource("reports")),
    db: Session = Depends(get_db),
):
    s, e = _month_window(start, end)
    pl = profit_or_loss(db, s, e)
    return {"start": s.isoformat(), "end": e.isoformat(), **pl}


@router.get("/wages")
def wages_report_endpoint(
    start: date | None = Query(None),
    end: date | None = Query(None),
    _=Depends(require_resource("reports")),
    db: Session = Depends(get_db),
):
    s, e = _month_window(start, end)
    report = wages_report(db, s, e)
    return {"start": s.isoformat(), "end": e.isoformat(), **report}


@router.get("/dashboard")
def dashboard(
    start: date | None = Query(None),
    end: date | None = Query(None),
    _=Depends(require_resource("dashboard")),
    db: Session = Depends(get_db),
):
    s, e = _month_window(start, end)

    # Orders by stage (not date-filtered: it is the current pipeline snapshot).
    stage_rows = (
        db.query(Order.status, func.count(Order.id)).group_by(Order.status).all()
    )
    orders_by_stage = {status: int(c) for status, c in stage_rows}

    # Low stock (current snapshot).
    low = []
    for st in db.query(YarnStock).all():
        threshold = (
            float(st.reorder_level_kg)
            if st.reorder_level_kg and float(st.reorder_level_kg) > 0
            else settings.default_reorder_level_kg
        )
        if float(st.quantity_kg) <= threshold:
            low.append(
                {"yarn_type": st.yarn_type, "colour": st.colour,
                 "quantity_kg": float(st.quantity_kg)}
            )

    # Idle loss inside the selected month (same numbers as the Machine report).
    machines = db.query(Machine).all()
    total_idle_loss = idle_loss_total(db, s, e)

    # Month cash-basis net (matches Reports > Profit / loss exactly).
    pl = profit_or_loss(db, s, e)

    return {
        "start": s.isoformat(),
        "end": e.isoformat(),
        "machine_count": len(machines),
        "orders_by_stage": orders_by_stage,
        "low_stock_count": len(low),
        "low_stock": low,
        "idle_loss_rupees": round(total_idle_loss, 2),
        "idle_loss_by_reason": idle_loss_by_reason(db, s, e),
        "profit_loss": pl,
    }


# --------------------------------------------------------------------------- #
# Owner "closing the books" — read-only order history, slip, and the money
# tables that must tie out to the Month summary band. Owner only (403 else).
# --------------------------------------------------------------------------- #
@router.get("/orders")
def orders_history(
    start: date | None = Query(None),
    end: date | None = Query(None),
    _=Depends(require_resource("reports")),
    db: Session = Depends(get_db),
):
    s, e = _month_window(start, end)
    data = order_history(db, s, e)
    return {"start": s.isoformat(), "end": e.isoformat(), **data}


@router.get("/orders/{order_id}/slip")
def order_slip_json(
    order_id: int,
    start: date | None = Query(None),
    end: date | None = Query(None),
    _=Depends(require_resource("reports")),
    db: Session = Depends(get_db),
):
    s, e = _month_window(start, end)
    slip = order_slip(db, order_id, s, e)
    if slip is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"start": s.isoformat(), "end": e.isoformat(), **slip}


@router.get("/orders/{order_id}/slip/pdf")
def order_slip_pdf(
    order_id: int,
    start: date | None = Query(None),
    end: date | None = Query(None),
    _=Depends(require_resource("reports")),
    db: Session = Depends(get_db),
):
    s, e = _month_window(start, end)
    slip = order_slip(db, order_id, s, e)
    if slip is None:
        raise HTTPException(status_code=404, detail="Order not found")
    pdf = _render_order_slip_pdf(slip)
    return StreamingResponse(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{slip["order_no"]}-slip.pdf"'},
    )


@router.get("/bills")
def raw_material_bills_report(
    start: date | None = Query(None),
    end: date | None = Query(None),
    _=Depends(require_resource("reports")),
    db: Session = Depends(get_db),
):
    s, e = _month_window(start, end)
    return {"start": s.isoformat(), "end": e.isoformat(), **raw_material_bills(db, s, e)}


@router.get("/buyer-payments")
def buyer_payments_report(
    start: date | None = Query(None),
    end: date | None = Query(None),
    _=Depends(require_resource("reports")),
    db: Session = Depends(get_db),
):
    s, e = _month_window(start, end)
    return {"start": s.isoformat(), "end": e.isoformat(), **buyer_payments_list(db, s, e)}


def _render_order_slip_pdf(slip: dict):
    """One-page order slip PDF. Mirrors the invoice PDF approach (lazy reportlab
    import + BytesIO canvas), so there is no new dependency."""
    from io import BytesIO

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail="PDF export needs reportlab, which is not installed.",
        ) from exc

    def rupees(v: float) -> str:
        return f"Rs {float(v or 0):,.2f}"

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 25 * mm

    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, y, "Everest Textile Mills")
    c.setFont("Helvetica", 11)
    y -= 7 * mm
    c.drawString(20 * mm, y, f"Order slip — {slip['order_no']}")
    y -= 10 * mm

    c.setFont("Helvetica", 10)
    created = (slip.get("created_at") or "")[:10]
    lines = [
        f"Buyer: {slip['buyer_name']}",
        f"Fabric: {slip['fabric_type']}   Colour: {slip['colour']}",
        f"Quantity: {slip['quantity_meters']:,.2f} m   Rate: {rupees(slip['unit_price'])}/m",
        f"Deadline: {slip.get('deadline') or '-'}   Status: {slip['status']}",
        f"Progress: {slip['progress_percent']}%   Created: {created}",
    ]
    if slip.get("dispatch_no") or slip.get("invoice_no"):
        lines.append(
            f"Dispatch: {slip.get('dispatch_no') or '-'}   Invoice: {slip.get('invoice_no') or '-'}"
        )
    for ln in lines:
        c.drawString(20 * mm, y, ln)
        y -= 6 * mm

    # Rolls
    y -= 4 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, f"Rolls ({len(slip['rolls'])})")
    y -= 6 * mm
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, y, "Roll")
    c.drawString(55 * mm, y, "Length (m)")
    c.drawString(90 * mm, y, "Machine")
    c.drawString(130 * mm, y, "Result")
    y -= 5 * mm
    for r in slip["rolls"]:
        if y < 50 * mm:
            c.showPage()
            y = h - 25 * mm
            c.setFont("Helvetica", 9)
        c.drawString(20 * mm, y, str(r["roll_no"]))
        c.drawRightString(80 * mm, y, f"{r['length_meters']:,.2f}")
        c.drawString(90 * mm, y, str(r["machine"]))
        c.drawString(130 * mm, y, str(r["result"]))
        y -= 5 * mm

    # Cost summary
    cost = slip["cost"]
    y -= 6 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, "Cost summary (estimate)")
    y -= 6 * mm
    c.setFont("Helvetica", 10)
    for label, val in [
        ("Yarn", cost["yarn"]),
        ("Wages", cost["wages"]),
        ("Machine", cost["machine"]),
        ("Total cost", cost["total"]),
        ("Revenue (est)", cost["revenue_est"]),
        ("Margin (est)", cost["margin_est"]),
    ]:
        c.drawString(20 * mm, y, label)
        c.drawRightString(90 * mm, y, rupees(val))
        y -= 6 * mm

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

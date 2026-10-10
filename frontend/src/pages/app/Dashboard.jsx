import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";
import {
  inr,
  statusLabel,
  currentMonthValue,
  monthRange,
  monthLabel,
} from "../../lib/format.js";
import MonthPicker from "../../components/owner/MonthPicker.jsx";
import { Waterfall, HBars } from "../../components/owner/Charts.jsx";
import "../../owner.css";

const STAGE_ORDER = [
  "draft",
  "confirmed",
  "in_production",
  "in_quality",
  "ready_to_ship",
  "dispatched",
  "closed",
];

// One colour per stage (consistent with chips elsewhere).
const STAGE_COLOUR = {
  draft: "#94a3b8",
  confirmed: "#0ea5e9",
  in_production: "#6366f1",
  in_quality: "#f59e0b",
  ready_to_ship: "#14b8a6",
  dispatched: "#0d9488",
  closed: "#166534",
};

// Owner dashboard: month-filtered cards, a profit/loss waterfall, orders by
// stage (clickable), idle loss by reason, and a live machine strip.
export default function Dashboard() {
  const [month, setMonth] = useState(currentMonthValue());
  const [data, setData] = useState(null);
  const [machines, setMachines] = useState(null); // may 403 for strip; optional
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load(m) {
    setLoading(true);
    setError("");
    try {
      const { start, end } = monthRange(m);
      const d = await apiFetch(
        `/api/reports/dashboard?start=${start}&end=${end}`,
      );
      setData(d);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(month);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [month]);

  function goToStage(stage) {
    // Hand the desired filter to the Orders page, then ask the shell to switch.
    window.__ownerOrdersFilter = stage;
    window.dispatchEvent(
      new CustomEvent("etm:navigate", { detail: { path: "/app/orders" } }),
    );
  }

  if (loading && !data)
    return (
      <div className="module owner-page">
        <h2>Dashboard</h2>
        <p className="muted">Loading…</p>
      </div>
    );
  if (error)
    return (
      <div className="module owner-page">
        <h2>Dashboard</h2>
        <div className="form-error">{error}</div>
      </div>
    );
  if (!data) return null;

  const stages = STAGE_ORDER.filter((s) => data.orders_by_stage[s] != null).map(
    (s) => [s, data.orders_by_stage[s]],
  );
  const pl = data.profit_loss;
  const totalOut = pl.supplier_payments_out + pl.wages;

  const waterfallSteps = [
    { label: "Payments in", value: pl.buyer_payments_in, kind: "in" },
    { label: "Material bills", value: pl.supplier_payments_out, kind: "out" },
    { label: "Wages", value: pl.wages, kind: "out" },
    {
      label: pl.is_profit ? "Net profit" : "Net loss",
      value: pl.profit_or_loss,
      kind: "net",
    },
  ];

  const stageBars = stages.map(([s, c]) => ({
    label: statusLabel(s),
    value: c,
    colour: STAGE_COLOUR[s] || "#0d9488",
    stage: s,
  }));

  const reasonBars = (data.idle_loss_by_reason || []).map((r) => ({
    label: r.reason,
    value: r.loss_rupees,
  }));

  return (
    <div className="module owner-page">
      <div className="owner-toolbar">
        <h2>Dashboard</h2>
        <MonthPicker value={month} onChange={setMonth} />
      </div>

      <div className="card-row">
        <div className="kpi">
          <span className="kpi-label">Orders</span>
          <span className="kpi-value owner-num">
            {Object.values(data.orders_by_stage).reduce((a, b) => a + b, 0)}
          </span>
          <span className="muted">across {stages.length} stages</span>
        </div>
        <div className={`kpi ${data.low_stock_count > 0 ? "kpi-warn" : ""}`}>
          <span className="kpi-label">Low stock items</span>
          <span className="kpi-value owner-num">{data.low_stock_count}</span>
          <span className="muted">
            {data.low_stock
              .map((s) => `${s.yarn_type} (${s.colour})`)
              .join(", ") || "all healthy"}
          </span>
        </div>
        <div className="kpi kpi-accent">
          <span className="kpi-label">Idle machine loss</span>
          <span className="kpi-value owner-num">
            {inr(data.idle_loss_rupees)}
          </span>
          <span className="muted">
            this month, {data.machine_count} machines
          </span>
        </div>
        <div className={`kpi ${pl.is_profit ? "kpi-ok" : "kpi-bad"}`}>
          <span className="kpi-label">Profit or loss (this month)</span>
          <span
            className={`kpi-value owner-num ${pl.is_profit ? "owner-pos" : "owner-neg"}`}
          >
            {inr(pl.profit_or_loss)}
          </span>
          <span className="muted">
            in {inr(pl.buyer_payments_in)} · out {inr(totalOut)}
          </span>
        </div>
      </div>

      <div className="owner-charts">
        <Waterfall
          steps={waterfallSteps}
          title={`Profit or loss — ${monthLabel(month)} (cash basis)`}
        />
        <HBars
          title="Orders by stage (click to open)"
          data={stageBars}
          onBarClick={(d) => goToStage(d.stage)}
        />
      </div>

      <section className="panel">
        <h3>Idle machine loss by reason — {monthLabel(month)}</h3>
        <HBars title="Lost rupees by reason" data={reasonBars} money />
      </section>

      <section className="panel">
        <h3>Profit / loss breakdown — {monthLabel(month)}</h3>
        <p className="muted" style={{ marginTop: "-0.4rem" }}>
          Cash basis: money actually received minus bills and wages paid this
          month.
        </p>
        <div className="pl-box">
          <div className="pl-row">
            <span>Buyer payments in</span>
            <strong className="owner-pos owner-num">
              {inr(pl.buyer_payments_in)}
            </strong>
          </div>
          <div className="pl-row">
            <span>Raw material bills</span>
            <strong className="owner-neg owner-num">
              − {inr(pl.supplier_payments_out)}
            </strong>
          </div>
          <div className="pl-row">
            <span>Wages paid</span>
            <strong className="owner-neg owner-num">− {inr(pl.wages)}</strong>
          </div>
          <div className="pl-row pl-total">
            <span>{pl.is_profit ? "Net profit" : "Net loss"}</span>
            <strong
              className={`owner-num ${pl.is_profit ? "owner-pos" : "owner-neg"}`}
            >
              {inr(pl.profit_or_loss)}
            </strong>
          </div>
        </div>
      </section>
    </div>
  );
}

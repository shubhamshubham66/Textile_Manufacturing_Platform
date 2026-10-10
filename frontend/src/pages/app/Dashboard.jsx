import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";
import {
  money,
  qty,
  statusLabel,
  currentMonth,
  monthLabel,
  recentMonths,
} from "../../lib/format.js";
import MonthPicker from "../../components/owner/MonthPicker.jsx";
import Waterfall from "../../components/owner/Waterfall.jsx";

const STAGE_ORDER = [
  "draft",
  "confirmed",
  "in_production",
  "in_quality",
  "ready_to_ship",
  "dispatched",
  "closed",
];

// Owner dashboard: month-scoped KPIs + waterfall P&L, orders-by-stage, machine
// strip, idle-loss-by-reason. All numbers come from /api/reports/dashboard.
export default function Dashboard() {
  const [month, setMonth] = useState(currentMonth());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load(m) {
    setLoading(true);
    setError("");
    try {
      setData(await apiFetch(`/api/reports/dashboard?month=${m}`));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(month);
  }, [month]);

  const header = (
    <div className="owner-head">
      <h2>Dashboard</h2>
      <MonthPicker
        value={month}
        options={recentMonths(12)}
        onChange={setMonth}
      />
    </div>
  );

  if (loading)
    return (
      <div className="module">
        {header}
        <p className="muted">Loading…</p>
      </div>
    );
  if (error)
    return (
      <div className="module">
        {header}
        <div className="form-error">{error}</div>
      </div>
    );
  if (!data) return null;

  const pl = data.profit_loss;
  const stages = STAGE_ORDER.filter((s) => data.orders_by_stage[s] != null).map(
    (s) => [s, data.orders_by_stage[s]],
  );
  const maxStage = Math.max(1, ...stages.map(([, c]) => c));
  const totalOrders = Object.values(data.orders_by_stage).reduce(
    (a, b) => a + b,
    0,
  );
  const maxReason = Math.max(
    1,
    ...data.idle_loss_by_reason.map((r) => r.rupees),
  );

  return (
    <div className="module">
      {header}

      <div className="card-row">
        <div className="kpi">
          <span className="kpi-label">Orders</span>
          <span className="kpi-value num">{totalOrders}</span>
          <span className="muted">across {stages.length} stages</span>
        </div>
        <div className={`kpi ${data.low_stock_count > 0 ? "kpi-warn" : ""}`}>
          <span className="kpi-label">Low stock items</span>
          <span className="kpi-value num">{data.low_stock_count}</span>
          <span className="muted">
            {data.low_stock
              .map((s) => `${s.yarn_type} (${s.colour})`)
              .join(", ") || "all healthy"}
          </span>
        </div>
        <div className="kpi kpi-accent">
          <span className="kpi-label">Idle machine loss</span>
          <span className="kpi-value num">{money(data.idle_loss_rupees)}</span>
          <span className="muted">
            this month, {data.machine_count} machines
          </span>
        </div>
        <div className={`kpi ${pl.is_profit ? "kpi-ok" : "kpi-bad"}`}>
          <span className="kpi-label">
            Profit or loss ({monthLabel(data.month)})
          </span>
          <span className={`kpi-value num ${pl.is_profit ? "pos" : "neg"}`}>
            {money(pl.net)}
          </span>
          <span className="muted">cash basis</span>
        </div>
      </div>

      <section className="panel">
        <h3>Profit or loss — {monthLabel(data.month)}</h3>
        <Waterfall
          inAmount={pl.buyer_payments_in}
          bills={pl.raw_material_bills_out}
          wages={pl.wages_paid}
          net={pl.net}
        />
        <div className="pl-box">
          <div className="pl-row">
            <span>Buyer payments received</span>
            <strong className="pos num">{money(pl.buyer_payments_in)}</strong>
          </div>
          <div className="pl-row">
            <span>Raw material bills paid</span>
            <strong className="neg num">
              − {money(pl.raw_material_bills_out)}
            </strong>
          </div>
          <div className="pl-row">
            <span>Wages paid</span>
            <strong className="neg num">− {money(pl.wages_paid)}</strong>
          </div>
          <div className="pl-row pl-total">
            <span>{pl.is_profit ? "Net profit" : "Net loss"}</span>
            <strong className={`num ${pl.is_profit ? "pos" : "neg"}`}>
              {money(pl.net)}
            </strong>
          </div>
        </div>
      </section>

      <section className="panel">
        <h3>Machines now</h3>
        {data.machine_strip.length === 0 ? (
          <p className="muted">No machines.</p>
        ) : (
          <div className="machine-strip">
            {data.machine_strip.map((mc) => (
              <a
                key={mc.name}
                className={`mstrip mstrip-${mc.status}`}
                href="#/machines"
                title="Open machine report"
              >
                <div className="mstrip-top">
                  <strong>{mc.name}</strong>
                  <span className={`chip chip-${mc.status}`}>
                    {statusLabel(mc.status)}
                  </span>
                </div>
                <div className="muted mstrip-type">{mc.type}</div>
                <div className="mstrip-order">
                  {mc.order_no ? mc.order_no : "—"}
                </div>
                {mc.reason && <div className="mstrip-reason">{mc.reason}</div>}
              </a>
            ))}
          </div>
        )}
      </section>

      <div className="owner-two">
        <section className="panel">
          <h3>Orders by stage</h3>
          {stages.length === 0 ? (
            <p className="muted">No orders this month.</p>
          ) : (
            <div className="bars">
              {stages.map(([stage, count]) => (
                <div className="bar-row" key={stage}>
                  <span className="bar-label">{statusLabel(stage)}</span>
                  <div className="bar-track">
                    <div
                      className={`bar-fill stage-${stage}`}
                      style={{ width: `${(count / maxStage) * 100}%` }}
                    />
                  </div>
                  <span className="bar-count num">{count}</span>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="panel">
          <h3>Idle loss by reason</h3>
          {data.idle_loss_by_reason.length === 0 ? (
            <p className="muted">No idle or breakdown time recorded.</p>
          ) : (
            <div className="bars">
              {data.idle_loss_by_reason.map((r) => (
                <div className="bar-row" key={r.reason}>
                  <span className="bar-label">{r.reason}</span>
                  <div className="bar-track">
                    <div
                      className="bar-fill stage-breakdown"
                      style={{ width: `${(r.rupees / maxReason) * 100}%` }}
                    />
                  </div>
                  <span className="bar-count num">{money(r.rupees)}</span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

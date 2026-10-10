import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";
import { inr, statusLabel } from "../../lib/format.js";

const STAGE_ORDER = [
  "draft",
  "confirmed",
  "in_production",
  "in_quality",
  "ready_to_ship",
  "dispatched",
  "closed",
];

// Owner dashboard: key cards (orders by stage, low stock, idle loss, profit/loss)
// with a simple CSS bar chart for orders by stage.
export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setData(await apiFetch("/api/reports/dashboard"));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);


  if (loading)
    return (
      <div className="module">
        <h2>Dashboard</h2>
        <p className="muted">Loading…</p>
      </div>
    );
  if (error)
    return (
      <div className="module">
        <h2>Dashboard</h2>
        <div className="form-error">{error}</div>
      </div>
    );
  if (!data) return null;

  const stages = STAGE_ORDER.filter((s) => data.orders_by_stage[s] != null).map(
    (s) => [s, data.orders_by_stage[s]],
  );
  const maxStage = Math.max(1, ...stages.map(([, c]) => c));
  const pl = data.profit_loss;

  return (
    <div className="module">
      <h2>Dashboard</h2>

      <div className="card-row">
        <div className="kpi">
          <span className="kpi-label">Orders</span>
          <span className="kpi-value">
            {Object.values(data.orders_by_stage).reduce((a, b) => a + b, 0)}
          </span>
          <span className="muted">across {stages.length} stages</span>
        </div>
        <div className={`kpi ${data.low_stock_count > 0 ? "kpi-warn" : ""}`}>
          <span className="kpi-label">Low stock items</span>
          <span className="kpi-value">{data.low_stock_count}</span>
          <span className="muted">
            {data.low_stock
              .map((s) => `${s.yarn_type} (${s.colour})`)
              .join(", ") || "all healthy"}
          </span>
        </div>
        <div className="kpi kpi-accent">
          <span className="kpi-label">Idle machine loss</span>
          <span className="kpi-value">{inr(data.idle_loss_rupees)}</span>
          <span className="muted">our unique metric</span>
        </div>
        <div className={`kpi ${pl.is_profit ? "kpi-ok" : "kpi-bad"}`}>
          <span className="kpi-label">{pl.is_profit ? "Profit" : "Loss"}</span>
          <span className="kpi-value">{inr(pl.profit_or_loss)}</span>
          <span className="muted">
            in {inr(pl.buyer_payments_in)} · out{" "}
            {inr(pl.supplier_payments_out + pl.wages)}
          </span>
        </div>
      </div>

      <section className="panel">
        <h3>Orders by stage</h3>
        {stages.length === 0 ? (
          <p className="muted">No orders.</p>
        ) : (
          <div className="bars">
            {stages.map(([stage, count]) => (
              <div className="bar-row" key={stage}>
                <span className="bar-label">{statusLabel(stage)}</span>
                <div className="bar-track">
                  <div
                    className="bar-fill"
                    style={{ width: `${(count / maxStage) * 100}%` }}
                  />
                </div>
                <span className="bar-count">{count}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="panel">
        <h3>Profit / loss breakdown</h3>
        <div className="pl-box">
          <div className="pl-row">
            <span>Buyer payments in</span>
            <strong className="pos">{inr(pl.buyer_payments_in)}</strong>
          </div>
          <div className="pl-row">
            <span>Supplier payments out</span>
            <strong className="neg">− {inr(pl.supplier_payments_out)}</strong>
          </div>
          <div className="pl-row">
            <span>Wages</span>
            <strong className="neg">− {inr(pl.wages)}</strong>
          </div>
          <div className="pl-row pl-total">
            <span>{pl.is_profit ? "Profit" : "Loss"}</span>
            <strong className={pl.is_profit ? "pos" : "neg"}>
              {inr(pl.profit_or_loss)}
            </strong>
          </div>
        </div>
      </section>
    </div>
  );
}

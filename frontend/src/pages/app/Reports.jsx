import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";
import { inr } from "../../lib/format.js";

// Owner reports: cost per order, machine report, profit/loss (month).
export default function Reports() {
  const [tab, setTab] = useState("cost");
  const [cost, setCost] = useState([]);
  const [machines, setMachines] = useState([]);
  const [pl, setPl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [c, m, p] = await Promise.all([
        apiFetch("/api/reports/cost-per-order"),
        apiFetch("/api/reports/machines"),
        apiFetch("/api/reports/profit-loss"),
      ]);
      setCost(c);
      setMachines(m);
      setPl(p);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);


  return (
    <div className="module">
      <h2>Owner reports</h2>
      {error && <div className="form-error">{error}</div>}

      <section className="panel">
        <div className="tabs">
          {[
            ["cost", "Cost per order"],
            ["machine", "Machine report"],
            ["pl", "Profit / loss"],
          ].map(([k, label]) => (
            <button
              key={k}
              className={`tab ${tab === k ? "active" : ""}`}
              onClick={() => setTab(k)}
            >
              {label}
            </button>
          ))}
        </div>

        {loading ? (
          <p className="muted">Loading…</p>
        ) : tab === "cost" ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Order</th>
                <th>Output (m)</th>
                <th>Yarn ₹</th>
                <th>Wages ₹</th>
                <th>Machine ₹</th>
                <th>Total cost</th>
                <th>Revenue (est)</th>
                <th>Margin (est)</th>
              </tr>
            </thead>
            <tbody>
              {cost.map((r) => (
                <tr key={r.order_no}>
                  <td>{r.order_no}</td>
                  <td>{r.output_meters}</td>
                  <td>{inr(r.yarn_cost)}</td>
                  <td>{inr(r.wage_cost)}</td>
                  <td>{inr(r.machine_cost)}</td>
                  <td>
                    <strong>{inr(r.total_cost)}</strong>
                  </td>
                  <td>{inr(r.revenue_est)}</td>
                  <td className={r.margin_est >= 0 ? "pos" : "neg"}>
                    {inr(r.margin_est)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : tab === "machine" ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Machine</th>
                <th>Type</th>
                <th>Status</th>
                <th>Output (m)</th>
                <th>Idle h</th>
                <th>Breakdown h</th>
                <th>Idle loss ₹</th>
              </tr>
            </thead>
            <tbody>
              {machines.map((m) => (
                <tr key={m.machine}>
                  <td>{m.machine}</td>
                  <td>{m.type}</td>
                  <td>
                    <span className={`status status-${m.current_status}`}>
                      {m.current_status}
                    </span>
                  </td>
                  <td>{m.total_output_meters}</td>
                  <td>{m.idle_hours}</td>
                  <td>{m.breakdown_hours}</td>
                  <td>
                    <strong>{inr(m.idle_loss_rupees)}</strong>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          pl && (
            <div className="pl-box">
              <div className="pl-row">
                <span>Buyer payments in</span>
                <strong className="pos">{inr(pl.buyer_payments_in)}</strong>
              </div>
              <div className="pl-row">
                <span>Supplier payments out</span>
                <strong className="neg">
                  − {inr(pl.supplier_payments_out)}
                </strong>
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
              <p className="muted">
                All-time by default. Supplier bills and wages typically precede
                buyer collection, so an early loss is expected in the seed data.
              </p>
            </div>
          )
        )}
      </section>
    </div>
  );
}

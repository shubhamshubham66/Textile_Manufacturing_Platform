import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";
import {
  money,
  moneyOrDash,
  qty,
  statusLabel,
  currentMonth,
  monthLabel,
  recentMonths,
} from "../../lib/format.js";
import MonthPicker from "../../components/owner/MonthPicker.jsx";

// Owner reports: cost per order, machine report, profit/loss, wages — all
// month-scoped. Numbers come from /api/reports/* and match docs/MONTH_END_HANDCHECK.
export default function Reports() {
  const [month, setMonth] = useState(currentMonth());
  const [tab, setTab] = useState("cost");
  const [cost, setCost] = useState(null);
  const [machines, setMachines] = useState(null);
  const [pl, setPl] = useState(null);
  const [wages, setWages] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load(m) {
    setLoading(true);
    setError("");
    try {
      const [c, mc, p, w] = await Promise.all([
        apiFetch(`/api/reports/cost-per-order?month=${m}`),
        apiFetch(`/api/reports/machines?month=${m}`),
        apiFetch(`/api/reports/profit-loss?month=${m}`),
        apiFetch(`/api/reports/wages?month=${m}`),
      ]);
      setCost(c);
      setMachines(mc);
      setPl(p);
      setWages(w);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(month);
  }, [month]);

  const marginClass = (v) => (v > 0 ? "pos" : v < 0 ? "neg" : "muted");

  return (
    <div className="module">
      <div className="owner-head">
        <h2>Owner reports</h2>
        <MonthPicker
          value={month}
          options={recentMonths(12)}
          onChange={setMonth}
        />
      </div>
      {error && <div className="form-error">{error}</div>}

      <section className="panel">
        <div className="tabs">
          {[
            ["cost", "Cost per order"],
            ["machine", "Machine report"],
            ["pl", "Profit / loss"],
            ["wages", "Wages"],
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
          <CostTab cost={cost} marginClass={marginClass} />
        ) : tab === "machine" ? (
          <MachineTab machines={machines} />
        ) : tab === "pl" ? (
          <PlTab pl={pl} month={month} />
        ) : (
          <WagesTab wages={wages} />
        )}
      </section>
    </div>
  );
}

function CostTab({ cost, marginClass }) {
  if (!cost || cost.rows.length === 0)
    return <p className="muted">No orders for this month.</p>;
  const t = cost.totals;
  // stacked bars scaled to the largest total cost
  const maxCost = Math.max(1, ...cost.rows.map((r) => r.total_cost));
  return (
    <>
      <div className="cost-bars">
        {cost.rows
          .filter((r) => r.total_cost > 0)
          .map((r) => {
            const pct = (v) => `${(v / maxCost) * 100}%`;
            return (
              <div className="cost-bar-row" key={r.order_no}>
                <span className="cost-bar-label num">{r.order_no}</span>
                <div
                  className="cost-bar"
                  title={`Yarn ${money(r.yarn_cost)}, Wages ${money(r.wage_cost)}, Machine ${money(r.machine_cost)}`}
                >
                  <div
                    className="seg seg-yarn"
                    style={{ width: pct(r.yarn_cost) }}
                  />
                  <div
                    className="seg seg-wage"
                    style={{ width: pct(r.wage_cost) }}
                  />
                  <div
                    className="seg seg-machine"
                    style={{ width: pct(r.machine_cost) }}
                  />
                </div>
                <span className="cost-bar-rev num">
                  rev {money(r.revenue_est)}
                </span>
              </div>
            );
          })}
        <div className="cost-legend">
          <span>
            <i className="seg-yarn" /> Yarn
          </span>
          <span>
            <i className="seg-wage" /> Wages
          </span>
          <span>
            <i className="seg-machine" /> Machine
          </span>
        </div>
      </div>

      <div className="table-scroll">
        <table className="data-table money-table">
          <thead>
            <tr>
              <th>Order</th>
              <th className="r">Output (m)</th>
              <th className="r">Yarn</th>
              <th className="r">Wages</th>
              <th className="r">Machine</th>
              <th className="r">Total cost</th>
              <th className="r">Revenue (est)</th>
              <th className="r">Margin (est)</th>
            </tr>
          </thead>
          <tbody>
            {cost.rows.map((r) => (
              <tr key={r.order_no}>
                <td>{r.order_no}</td>
                <td className="r num">
                  {r.output_meters ? qty(r.output_meters) : "—"}
                </td>
                <td className="r num">{moneyOrDash(r.yarn_cost)}</td>
                <td className="r num">{moneyOrDash(r.wage_cost)}</td>
                <td className="r num">{moneyOrDash(r.machine_cost)}</td>
                <td className="r num">
                  <strong>{moneyOrDash(r.total_cost)}</strong>
                </td>
                <td className="r num">{moneyOrDash(r.revenue_est)}</td>
                <td className={`r num ${marginClass(r.margin_est)}`}>
                  {r.total_cost ? money(r.margin_est) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="totals-row">
              <td>Total</td>
              <td className="r num">{qty(t.output_meters)}</td>
              <td className="r num">{money(t.yarn_cost)}</td>
              <td className="r num">{money(t.wage_cost)}</td>
              <td className="r num">{money(t.machine_cost)}</td>
              <td className="r num">{money(t.total_cost)}</td>
              <td className="r num">{money(t.revenue_est)}</td>
              <td className={`r num ${t.margin_est >= 0 ? "pos" : "neg"}`}>
                {money(t.margin_est)}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="muted small">
        Margin is an estimate (invoiced-rate revenue − cost). Cash collection is
        on the Profit / loss tab.
      </p>
    </>
  );
}

function MachineTab({ machines }) {
  if (!machines || machines.rows.length === 0)
    return <p className="muted">No machines.</p>;
  const t = machines.totals;
  return (
    <div className="table-scroll">
      <table className="data-table money-table">
        <thead>
          <tr>
            <th>Machine</th>
            <th>Type</th>
            <th>Status</th>
            <th className="r">Output (m)</th>
            <th className="r">Running (h)</th>
            <th className="r">Idle (h)</th>
            <th className="r">Breakdown (h)</th>
            <th className="r">Idle loss</th>
            <th>Top reason</th>
          </tr>
        </thead>
        <tbody>
          {machines.rows.map((m) => (
            <tr key={m.machine}>
              <td>{m.machine}</td>
              <td>{m.type}</td>
              <td>
                <span className={`chip chip-${m.current_status}`}>
                  {statusLabel(m.current_status)}
                </span>
              </td>
              <td className="r num">{qty(m.total_output_meters)}</td>
              <td className="r num">{qty(m.running_hours)}</td>
              <td className="r num">{qty(m.idle_hours)}</td>
              <td className="r num">{qty(m.breakdown_hours)}</td>
              <td className="r num">{moneyOrDash(m.idle_loss_rupees)}</td>
              <td>{m.top_reason || "—"}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="totals-row">
            <td colSpan={3}>Total</td>
            <td className="r num">{qty(t.total_output_meters)}</td>
            <td className="r num">{qty(t.running_hours)}</td>
            <td className="r num">{qty(t.idle_hours)}</td>
            <td className="r num">{qty(t.breakdown_hours)}</td>
            <td className="r num">{money(t.idle_loss_rupees)}</td>
            <td></td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

function PlTab({ pl, month }) {
  if (!pl) return <p className="muted">No data.</p>;
  return (
    <div className="pl-box">
      <h3 className="pl-head">Month-end summary — {monthLabel(month)}</h3>
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
        <span>{pl.is_profit ? "Net profit (cash)" : "Net loss (cash)"}</span>
        <strong className={`num ${pl.is_profit ? "pos" : "neg"}`}>
          {money(pl.net)}
        </strong>
      </div>
      <p className="muted small">
        Cash basis: money actually received and paid in {monthLabel(month)}.
      </p>
    </div>
  );
}

function WagesTab({ wages }) {
  if (!wages) return <p className="muted">No data.</p>;
  if (wages.per_employee.length === 0)
    return <p className="muted">No wages paid this month.</p>;
  const maxAmt = Math.max(1, ...wages.per_employee.map((e) => e.amount));
  return (
    <>
      <div className="kpi kpi-inline">
        <span className="kpi-label">Total wages paid</span>
        <span className="kpi-value num">{money(wages.total_wages_paid)}</span>
      </div>

      <div className="bars wages-bars">
        {wages.per_employee.map((e) => (
          <div className="bar-row" key={e.employee}>
            <span className="bar-label">{e.employee}</span>
            <div className="bar-track">
              <div
                className="bar-fill stage-confirmed"
                style={{ width: `${(e.amount / maxAmt) * 100}%` }}
              />
            </div>
            <span className="bar-count num">{money(e.amount)}</span>
          </div>
        ))}
      </div>

      <div className="owner-two">
        <div className="table-scroll">
          <table className="data-table money-table">
            <thead>
              <tr>
                <th>Employee</th>
                <th className="r">Days</th>
                <th className="r">Rate/day</th>
                <th className="r">Amount</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {wages.per_employee.map((e) => (
                <tr key={e.employee}>
                  <td>{e.employee}</td>
                  <td className="r num">{qty(e.days)}</td>
                  <td className="r num">{money(e.rate)}</td>
                  <td className="r num">{money(e.amount)}</td>
                  <td>
                    <span className="chip chip-paid">Paid</span>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="totals-row">
                <td colSpan={3}>Total</td>
                <td className="r num">{money(wages.total_wages_paid)}</td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>

        <div className="table-scroll">
          <table className="data-table money-table">
            <thead>
              <tr>
                <th>Order</th>
                <th className="r">Wages allocated</th>
              </tr>
            </thead>
            <tbody>
              {wages.per_order.map((o) => (
                <tr key={o.order_no}>
                  <td>{o.order_no}</td>
                  <td className="r num">{money(o.wage_cost)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <p className="muted small">
        Wages are allocated to orders by each order's share of output metres —
        the same figure feeds Cost per order (no double counting).
      </p>
    </>
  );
}

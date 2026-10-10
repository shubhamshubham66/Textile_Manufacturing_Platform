import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";
import { isLiveRefresh, useLive } from "../../live/LiveContext.jsx";
import {
  inr,
  qty,
  hrs,
  statusLabel,
  currentMonthValue,
  monthRange,
  monthLabel,
} from "../../lib/format.js";
import MonthPicker from "../../components/owner/MonthPicker.jsx";
import { StackedBars, HBars } from "../../components/owner/Charts.jsx";
import "../../owner.css";

const COST_SERIES = [
  { key: "yarn_cost", label: "Yarn", colour: "#0d9488" },
  { key: "wage_cost", label: "Wages", colour: "#6366f1" },
  { key: "machine_cost", label: "Machine", colour: "#f59e0b" },
];

function Money({ value }) {
  const cls = value > 0 ? "owner-pos" : value < 0 ? "owner-neg" : "owner-zero";
  return <span className={`owner-num ${cls}`}>{inr(value)}</span>;
}

export default function Reports() {
  const [tab, setTab] = useState("cost");
  const [month, setMonth] = useState(currentMonthValue());
  const [cost, setCost] = useState(null);
  const [machines, setMachines] = useState(null);
  const [pl, setPl] = useState(null);
  const [wages, setWages] = useState(null);
  const [dues, setDues] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load(m) {
    if (!isLiveRefresh()) setLoading(true);
    setError("");
    try {
      const { start, end } = monthRange(m);
      const qs = `start=${start}&end=${end}`;
      const [c, mc, p, w, d] = await Promise.all([
        apiFetch(`/api/reports/cost-per-order?${qs}`),
        apiFetch(`/api/reports/machines?${qs}`),
        apiFetch(`/api/reports/profit-loss?${qs}`),
        apiFetch(`/api/reports/wages?${qs}`),
        apiFetch(`/api/payments/dues`),
      ]);
      setCost(c);
      setMachines(mc);
      setPl(p);
      setWages(w);
      setDues(d);
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

  // Reload quietly when something this page shows changes elsewhere.
  useLive(["machines", "production", "orders", "yarn", "quality", "payments", "wages"], () => load(month));

  const tabs = [
    ["cost", "Cost per order"],
    ["machine", "Machine report"],
    ["pl", "Profit / loss"],
    ["wages", "Wages"],
  ];

  return (
    <div className="module owner-page">
      <div className="owner-toolbar">
        <h2>Owner reports</h2>
        <MonthPicker value={month} onChange={setMonth} />
      </div>
      {error && <div className="form-error">{error}</div>}

      <section className="panel">
        <div className="tabs">
          {tabs.map(([k, label]) => (
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
          <p className="muted">Loading {monthLabel(month)}…</p>
        ) : tab === "cost" ? (
          <CostTab cost={cost} month={month} />
        ) : tab === "machine" ? (
          <MachineTab machines={machines} month={month} />
        ) : tab === "pl" ? (
          <PlTab pl={pl} wages={wages} cost={cost} dues={dues} month={month} />
        ) : (
          <WagesTab wages={wages} month={month} />
        )}
      </section>
    </div>
  );
}

/* ---------------- Cost per order ---------------- */
function CostTab({ cost, month }) {
  const rows = cost?.rows || [];
  const withOutput = rows.filter(
    (r) => r.output_meters > 0 || r.total_cost > 0,
  );
  if (withOutput.length === 0)
    return (
      <p className="muted">
        No production or cost recorded in {monthLabel(month)}.
      </p>
    );

  const totals = withOutput.reduce(
    (a, r) => ({
      yarn: a.yarn + r.yarn_cost,
      wage: a.wage + r.wage_cost,
      machine: a.machine + r.machine_cost,
      total: a.total + r.total_cost,
      rev: a.rev + r.revenue_est,
      margin: a.margin + r.margin_est,
    }),
    { yarn: 0, wage: 0, machine: 0, total: 0, rev: 0, margin: 0 },
  );

  const chartData = withOutput.map((r) => ({
    label: r.order_no.replace("ORD-", ""),
    parts: {
      yarn_cost: r.yarn_cost,
      wage_cost: r.wage_cost,
      machine_cost: r.machine_cost,
    },
    marker: { value: r.revenue_est, label: "Revenue" },
  }));

  return (
    <>
      <div className="owner-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Order</th>
            <th className="num">Output</th>
            <th className="num">Yarn</th>
            <th className="num">Wages</th>
            <th className="num">Machine</th>
            <th className="num">Total cost</th>
            <th className="num">Revenue (est)</th>
            <th className="num">Margin (est)</th>
          </tr>
        </thead>
        <tbody>
          {withOutput.map((r) => (
            <tr key={r.order_no}>
              <td>{r.order_no}</td>
              <td className="num">{qty(r.output_meters, "m")}</td>
              <td className="num">
                {r.yarn_cost > 0 ? (
                  <span
                    className="owner-num"
                    title={
                      r.yarn_basis === "estimate"
                        ? "Estimate: no yarn receipt is linked to this order, so metres made × yarn per metre × average purchase rate"
                        : "Yarn receipts linked to this order, received this month"
                    }
                  >
                    {inr(r.yarn_cost)}
                    {r.yarn_basis === "estimate" && <small className="owner-est"> est</small>}
                  </span>
                ) : (
                  <span
                    className="owner-zero"
                    title="No yarn linked to this order"
                  >
                    —
                  </span>
                )}
              </td>
              <td className="num owner-num">{inr(r.wage_cost)}</td>
              <td className="num owner-num">{inr(r.machine_cost)}</td>
              <td className="num owner-num">
                <strong>{inr(r.total_cost)}</strong>
              </td>
              <td className="num owner-num">{inr(r.revenue_est)}</td>
              <td className="num">
                <Money value={r.margin_est} />
              </td>
            </tr>
          ))}
          <tr className="owner-total">
            <td>Total</td>
            <td className="num" />
            <td className="num owner-num">{inr(totals.yarn)}</td>
            <td className="num owner-num">{inr(totals.wage)}</td>
            <td className="num owner-num">{inr(totals.machine)}</td>
            <td className="num owner-num">{inr(totals.total)}</td>
            <td className="num owner-num">{inr(totals.rev)}</td>
            <td className="num">
              <Money value={totals.margin} />
            </td>
          </tr>
        </tbody>
      </table>
      </div>
      <p className="muted">
        Machine cost = running hours this month × power + overhead rate;
        operator wages are only in the Wages column (never double-counted).
        Revenue and margin are estimates. "est" marks yarn estimated from
        metres made because no yarn receipt is linked to the order.
      </p>
      <StackedBars
        data={chartData}
        series={COST_SERIES}
        title="Cost per order (stacked) vs revenue — ₹"
      />
    </>
  );
}

/* ---------------- Machine report ---------------- */
function MachineTab({ machines, month }) {
  const rows = machines?.machines || [];
  const totals = machines?.totals;
  if (rows.length === 0)
    return (
      <p className="muted">No machines to report for {monthLabel(month)}.</p>
    );

  const outputBars = rows.map((m) => ({
    label: m.machine,
    value: m.total_output_meters,
  }));
  const quiet =
    totals &&
    !totals.total_output_meters &&
    !totals.running_hours &&
    !totals.idle_hours &&
    !totals.breakdown_hours;

  return (
    <>
      {quiet && (
        <p className="muted">
          No machine activity recorded in {monthLabel(month)}: no output and no
          running, idle or breakdown time.
        </p>
      )}
      <div className="owner-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Machine</th>
            <th>Type</th>
            <th>Status</th>
            <th className="num">Output</th>
            <th className="num">Running</th>
            <th className="num">Idle</th>
            <th className="num">Breakdown</th>
            <th className="num">Idle loss</th>
            <th>Top idle reason</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((m) => (
            <tr key={m.machine}>
              <td>{m.machine}</td>
              <td>{m.type}</td>
              <td>
                <StatusChip status={m.current_status} />
              </td>
              <td className="num">{qty(m.total_output_meters, "m")}</td>
              <td className="num">{hrs(m.running_hours)}</td>
              <td className="num">{hrs(m.idle_hours)}</td>
              <td className="num">{hrs(m.breakdown_hours)}</td>
              <td className="num owner-num">
                <strong>{inr(m.idle_loss_rupees)}</strong>
              </td>
              <td>{m.top_idle_reason}</td>
            </tr>
          ))}
          {totals && (
            <tr className="owner-total">
              <td>Total</td>
              <td />
              <td />
              <td className="num">{qty(totals.total_output_meters, "m")}</td>
              <td className="num">{hrs(totals.running_hours)}</td>
              <td className="num">{hrs(totals.idle_hours)}</td>
              <td className="num">{hrs(totals.breakdown_hours)}</td>
              <td className="num owner-num">{inr(totals.idle_loss_rupees)}</td>
              <td />
            </tr>
          )}
        </tbody>
      </table>
      </div>
      <HBars title="Metres produced per machine" data={outputBars} unit="m" />
    </>
  );
}

/* ---------------- Profit / loss (month summary) ---------------- */
function PlTab({ pl, wages, cost, dues, month }) {
  if (!pl) return <p className="muted">No data.</p>;
  const estMargin = (cost?.rows || []).reduce((a, r) => a + r.margin_est, 0);
  const receivable = dues?.total_receivable || 0;
  const payable = dues?.total_payable || 0;

  return (
    <div className="pl-box">
      <h3 style={{ marginTop: 0 }}>Month-end summary — {monthLabel(month)}</h3>
      {!pl.buyer_payments_in && !pl.supplier_payments_out && !pl.wages && (
        <p className="muted">
          No payments received, bills paid or wages paid in {monthLabel(month)}.
        </p>
      )}
      <div className="pl-row">
        <span>Buyer payments received</span>
        <strong className="owner-pos owner-num">
          {inr(pl.buyer_payments_in)}
        </strong>
      </div>
      <div className="pl-row">
        <span>Raw material bills paid</span>
        <strong className="owner-neg owner-num">
          − {inr(pl.supplier_payments_out)}
        </strong>
      </div>
      <div className="pl-row">
        <span>Wages paid</span>
        <strong className="owner-neg owner-num">− {inr(pl.wages)}</strong>
      </div>
      <div className="pl-row pl-total">
        <span>{pl.is_profit ? "Net profit" : "Net loss"} (cash basis)</span>
        <strong
          className={`owner-num ${pl.is_profit ? "owner-pos" : "owner-neg"}`}
        >
          {inr(pl.profit_or_loss)}
        </strong>
      </div>
      <p className="muted" style={{ marginTop: "0.8rem" }}>
        Below is <em>not</em> part of the cash net — shown for context only:
      </p>
      <ul className="muted" style={{ lineHeight: 1.8 }}>
        <li>
          Estimated order margin (invoiced − cost):{" "}
          <strong className="owner-num">{inr(estMargin)}</strong>
        </li>
        <li>
          Wages due (worked this month, not yet paid):{" "}
          <strong className="owner-num">{inr(pl.wages_due || 0)}</strong>
        </li>
        <li>
          Buyers still owe us:{" "}
          <strong className="owner-num">{inr(receivable)}</strong>
        </li>
        <li>
          We still owe suppliers:{" "}
          <strong className="owner-num">{inr(payable)}</strong>
        </li>
      </ul>
    </div>
  );
}

/* ---------------- Wages ---------------- */
function WagesTab({ wages, month }) {
  if (!wages) return <p className="muted">No data.</p>;
  const emps = wages.per_employee || [];
  if (emps.length === 0)
    return <p className="muted">No wages recorded in {monthLabel(month)}.</p>;

  const empBars = emps.map((e) => ({ label: e.employee, value: e.amount }));

  return (
    <>
      <div
        className="card-row"
        style={{ gridTemplateColumns: "repeat(3,1fr)" }}
      >
        <div className="kpi">
          <span className="kpi-label">Total wages</span>
          <span className="kpi-value owner-num">{inr(wages.total_wages)}</span>
          <span className="muted">this month</span>
        </div>
        <div className="kpi kpi-ok">
          <span className="kpi-label">Paid</span>
          <span className="kpi-value owner-num">{inr(wages.total_paid)}</span>
        </div>
        <div className="kpi kpi-warn">
          <span className="kpi-label">Unpaid</span>
          <span className="kpi-value owner-num">{inr(wages.total_unpaid)}</span>
        </div>
      </div>

      <h3>Wages per employee</h3>
      <div className="owner-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Employee</th>
            <th>Role</th>
            <th className="num">Days</th>
            <th className="num">Daily rate</th>
            <th className="num">Amount</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {emps.map((e, i) => (
            <tr key={i}>
              <td>{e.employee}</td>
              <td>{e.role_on_floor || "—"}</td>
              <td className="num">{e.days_present}</td>
              <td className="num owner-num">{inr(e.daily_wage)}</td>
              <td className="num owner-num">{inr(e.amount)}</td>
              <td>
                <span
                  className={`owner-chip ${e.status === "paid" ? "owner-chip-green" : "owner-chip-amber"}`}
                >
                  {e.status === "paid" ? "Paid" : "Unpaid"}
                </span>
              </td>
            </tr>
          ))}
          <tr className="owner-total">
            <td>Total</td>
            <td />
            <td className="num" />
            <td className="num" />
            <td className="num owner-num">{inr(wages.total_wages)}</td>
            <td />
          </tr>
        </tbody>
      </table>
      </div>

      <HBars title="Wages per employee — ₹" data={empBars} money />

      <h3>Wages allocated per order</h3>
      {(wages.per_order || []).length === 0 ? (
        <p className="muted">No production output to allocate wages against.</p>
      ) : (
        <div className="owner-table-wrap">
      <table className="data-table">
          <thead>
            <tr>
              <th>Order</th>
              <th className="num">Output</th>
              <th className="num">Wages allocated</th>
            </tr>
          </thead>
          <tbody>
            {wages.per_order.map((o) => (
              <tr key={o.order_no}>
                <td>{o.order_no}</td>
                <td className="num">{qty(o.output_meters, "m")}</td>
                <td className="num owner-num">{inr(o.wages_allocated)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      )}
      <p className="muted">
        Per-order wages use each order's share of production output — the same
        basis as the Wages column in Cost per order, so the two tie out.
      </p>
    </>
  );
}

function StatusChip({ status }) {
  const map = {
    running: "owner-chip-green",
    idle: "owner-chip-amber",
    breakdown: "owner-chip-red",
  };
  return (
    <span className={`owner-chip ${map[status] || "owner-chip-grey"}`}>
      {statusLabel(status)}
    </span>
  );
}

import { useEffect, useRef, useState } from "react";
import { apiFetch, getToken } from "../../lib/api.js";
import { isLiveRefresh, useLive } from "../../live/LiveContext.jsx";
import {
  inr,
  qty,
  hrs,
  statusLabel,
  ddmmyyyy,
  currentMonthValue,
  monthRange,
  monthLabel,
} from "../../lib/format.js";
import MonthPicker from "../../components/owner/MonthPicker.jsx";
import { useVisiblePolling } from "../../components/owner/usePolling.js";
import {
  Waterfall,
  HBars,
  StackedBars,
} from "../../components/owner/Charts.jsx";
import "../../owner.css";

// The owner's single, read-only "closing the books" screen. Every number is for
// the selected month, served by owner-only aggregation endpoints. The owner only
// views here — no create/confirm/cancel.

const GROUP_CHIPS = [
  ["all", "All"],
  ["awaiting", "Awaiting"],
  ["confirmed", "Confirmed"],
  ["ongoing", "Ongoing"],
  ["completed", "Completed"],
  ["cancelled", "Cancelled"],
];

const STATUS_CHIP = {
  draft: "owner-chip-grey",
  confirmed: "owner-chip-blue",
  in_production: "owner-chip-blue",
  in_quality: "owner-chip-amber",
  ready_to_ship: "owner-chip-blue",
  dispatched: "owner-chip-green",
  closed: "owner-chip-green",
  cancelled: "owner-chip-red",
};

const COST_SERIES = [
  { key: "yarn_cost", label: "Yarn", colour: "#0d9488" },
  { key: "wage_cost", label: "Wages", colour: "#6366f1" },
  { key: "machine_cost", label: "Machine", colour: "#f59e0b" },
];

function nowClock() {
  return new Date().toLocaleTimeString("en-IN", { hour12: false });
}

export default function Dashboard() {
  const [month, setMonth] = useState(currentMonthValue());
  const [d, setD] = useState(null); // { dashboard, cost, machines, wages, dues, orders, bills, buyerPay }
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshNote, setRefreshNote] = useState("");
  const [updatedAt, setUpdatedAt] = useState("");
  const [chip, setChip] = useState("all");
  const [search, setSearch] = useState("");
  const [slipOrder, setSlipOrder] = useState(null); // order row for the side panel
  const scrollRef = useRef(0);

  async function load(m, { quiet = false } = {}) {
    if (!quiet && !isLiveRefresh()) setLoading(true);
    setError("");
    const { start, end } = monthRange(m);
    const q = `start=${start}&end=${end}`;
    try {
      const [dashboard, cost, machines, wages, dues, orders, bills, buyerPay] =
        await Promise.all([
          apiFetch(`/api/reports/dashboard?${q}`),
          apiFetch(`/api/reports/cost-per-order?${q}`),
          apiFetch(`/api/reports/machines?${q}`),
          apiFetch(`/api/reports/wages?${q}`),
          apiFetch(`/api/payments/dues`),
          apiFetch(`/api/reports/orders?${q}`),
          apiFetch(`/api/reports/bills?${q}`),
          apiFetch(`/api/reports/buyer-payments?${q}`),
        ]);
      setD({ dashboard, cost, machines, wages, dues, orders, bills, buyerPay });
      setUpdatedAt(nowClock());
      setRefreshNote("");
    } catch (err) {
      // Keep the old data on a failed refresh; only hard-fail the first load.
      if (!d) setError(err.message);
      else setRefreshNote("Could not refresh, retrying…");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(month);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [month]);

  // Keep scroll position across refreshes.
  useEffect(() => {
    const onScroll = () => {
      scrollRef.current = window.scrollY;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  useEffect(() => {
    if (d) window.scrollTo(0, scrollRef.current);
  }, [d]);

  // 30s visible polling + SSE live refresh (both quiet).
  useVisiblePolling(() => load(month, { quiet: true }), 30000, [month]);
  useLive(
    [
      "machines",
      "production",
      "orders",
      "yarn",
      "quality",
      "payments",
      "wages",
    ],
    () => load(month, { quiet: true }),
  );

  if (loading && !d)
    return (
      <div className="module owner-page">
        <h2>Dashboard</h2>
        <p className="muted">Loading {monthLabel(month)}…</p>
      </div>
    );
  if (error && !d)
    return (
      <div className="module owner-page">
        <h2>Dashboard</h2>
        <div className="form-error">{error}</div>
      </div>
    );
  if (!d) return null;

  const pl = d.dashboard.profit_loss;
  const dues = d.dues || { total_receivable: 0, total_payable: 0 };
  const estMargin = (d.cost.rows || []).reduce((a, r) => a + r.margin_est, 0);

  // Order history filtering.
  const allRows = d.orders.rows || [];
  const counts = d.orders.counts || {};
  const q = search.trim().toLowerCase();
  const rows = allRows.filter((r) => {
    if (chip !== "all" && r.group !== chip) return false;
    if (!q) return true;
    return (
      r.order_no.toLowerCase().includes(q) ||
      r.buyer_name.toLowerCase().includes(q) ||
      r.fabric_type.toLowerCase().includes(q) ||
      r.colour.toLowerCase().includes(q)
    );
  });

  const waterfallSteps = [
    { label: "Payments in", value: pl.buyer_payments_in, kind: "in" },
    { label: "Material bills", value: pl.supplier_payments_out, kind: "out" },
    { label: "Wages paid", value: pl.wages, kind: "out" },
    {
      label: pl.is_profit ? "Net profit" : "Net loss",
      value: pl.profit_or_loss,
      kind: "net",
    },
  ];

  const noMoneyYet =
    pl.buyer_payments_in === 0 &&
    pl.supplier_payments_out === 0 &&
    pl.wages === 0;
  const verdict = noMoneyYet
    ? "No payments, bills or wages recorded this month yet."
    : pl.is_profit
      ? `The mill made a profit of ${inr(pl.profit_or_loss)} this month.`
      : `The mill made a loss of ${inr(Math.abs(pl.profit_or_loss))} this month.`;

  return (
    <div className="module owner-page">
      {/* A. Top bar */}
      <div className="owner-toolbar">
        <h2>Owner dashboard — closing the books</h2>
        <div className="owner-toolbar-actions">
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() =>
              window.dispatchEvent(
                new CustomEvent("etm:navigate", {
                  detail: { path: "/app/team" },
                }),
              )
            }
          >
            ＋ Create manager
          </button>
          <MonthPicker value={month} onChange={setMonth} />
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => load(month)}
          >
            Refresh
          </button>
          <span className="muted owner-updated">
            Updated {updatedAt || "—"}
          </span>
        </div>
      </div>
      {refreshNote && <div className="callout callout-warn">{refreshNote}</div>}

      {/* B. Month summary band */}
      <section className="panel owner-band">
        <h3>{monthLabel(month)} — money in one place (cash basis)</h3>
        <div className="owner-band-grid">
          <div className="owner-band-lines">
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
              <span>{pl.is_profit ? "Net profit" : "Net loss"}</span>
              <strong
                className={`owner-num ${pl.is_profit ? "owner-pos" : "owner-neg"}`}
              >
                {inr(pl.profit_or_loss)}
              </strong>
            </div>
            <p
              className={`owner-verdict ${noMoneyYet ? "owner-zero" : pl.is_profit ? "owner-pos" : "owner-neg"}`}
            >
              {verdict}
            </p>
            <p className="muted owner-band-context">
              Not part of the cash net — buyers owe us{" "}
              <strong className="owner-num">
                {inr(dues.total_receivable)}
              </strong>
              , we owe suppliers{" "}
              <strong className="owner-num">{inr(dues.total_payable)}</strong>,
              estimated order margin{" "}
              <strong className="owner-num">{inr(estMargin)}</strong>.
            </p>
          </div>
          <Waterfall
            steps={waterfallSteps}
            title={`Profit or loss — ${monthLabel(month)}`}
          />
        </div>
      </section>

      {/* C. Order history */}
      <section className="panel">
        <div className="toolbar">
          <h3>Order history</h3>
          <input
            placeholder="Search order / buyer / fabric / colour…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="owner-chips">
          {GROUP_CHIPS.map(([k, label]) => (
            <button
              key={k}
              className={`owner-filter-chip ${chip === k ? "active" : ""}`}
              onClick={() => setChip(k)}
            >
              {label} <span className="owner-chip-count">{counts[k] ?? 0}</span>
            </button>
          ))}
        </div>
        {(counts.all ?? 0) === 0 ? (
          <p className="muted">
            No orders yet. Orders appear here as the Store manager records them.
          </p>
        ) : rows.length === 0 ? (
          <p className="muted">No orders match this filter.</p>
        ) : (
          <table className="data-table owner-sticky">
            <thead>
              <tr>
                <th>Order</th>
                <th>Buyer</th>
                <th>Fabric / colour</th>
                <th className="num">Metres</th>
                <th className="num">Rate</th>
                <th>Deadline</th>
                <th>Status</th>
                <th className="num">Progress</th>
                <th>On time</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.id}
                  className="owner-clickable-row"
                  onClick={() => setSlipOrder(r)}
                >
                  <td>{r.order_no}</td>
                  <td>{r.buyer_name}</td>
                  <td>
                    {r.fabric_type} · {r.colour}
                  </td>
                  <td className="num">{qty(r.quantity_meters, "m")}</td>
                  <td className="num owner-num">{inr(r.unit_price)}</td>
                  <td>{ddmmyyyy(r.deadline)}</td>
                  <td>
                    <span
                      className={`owner-chip ${STATUS_CHIP[r.status] || "owner-chip-grey"}`}
                    >
                      {statusLabel(r.status)}
                    </span>
                  </td>
                  <td className="num">{r.progress_percent}%</td>
                  <td>
                    {r.status === "cancelled" ? (
                      <span className="muted">—</span>
                    ) : r.late ? (
                      <span className="owner-flag-late">Late</span>
                    ) : (
                      <span className="owner-flag-ontrack">On track</span>
                    )}
                  </td>
                  <td className="row-actions">
                    <button
                      className="link-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSlipOrder(r);
                      }}
                    >
                      Order slip
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* E. Cost per order */}
      <CostSection cost={d.cost} />

      {/* F. Machine production */}
      <MachineSection machines={d.machines} />

      {/* G. Money in one place */}
      <MoneySection
        wages={d.wages}
        bills={d.bills}
        buyerPay={d.buyerPay}
        pl={pl}
      />

      {slipOrder && (
        <OrderSlipPanel
          order={slipOrder}
          month={month}
          onClose={() => setSlipOrder(null)}
        />
      )}
    </div>
  );
}

/* ---------------- Cost per order (E) ---------------- */
function CostSection({ cost }) {
  const rows = (cost.rows || []).filter(
    (r) => r.output_meters > 0 || r.total_cost > 0,
  );
  if (rows.length === 0)
    return (
      <section className="panel">
        <h3>Cost per order</h3>
        <p className="muted">No production or cost recorded this month.</p>
      </section>
    );
  const t = rows.reduce(
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
  const chartData = rows.map((r) => ({
    label: r.order_no.replace("ORD-", ""),
    parts: {
      yarn_cost: r.yarn_cost,
      wage_cost: r.wage_cost,
      machine_cost: r.machine_cost,
    },
    marker: { value: r.revenue_est, label: "Revenue" },
  }));
  const marginPct = (r) =>
    r.revenue_est > 0 ? (r.margin_est / r.revenue_est) * 100 : 0;

  return (
    <section className="panel">
      <h3>Cost per order</h3>
      <table className="data-table owner-sticky">
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
            <th className="num">Margin %</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.order_no}>
              <td>{r.order_no}</td>
              <td className="num">{qty(r.output_meters, "m")}</td>
              <td className="num owner-num">
                {r.yarn_cost > 0 ? (
                  inr(r.yarn_cost)
                ) : (
                  <span className="owner-zero" title="No yarn used">
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
              <td
                className={`num owner-num ${r.margin_est >= 0 ? "owner-pos" : "owner-neg"}`}
              >
                {inr(r.margin_est)}
              </td>
              <td
                className={`num ${r.margin_est >= 0 ? "owner-pos" : "owner-neg"}`}
              >
                {marginPct(r).toFixed(1)}%
              </td>
            </tr>
          ))}
          <tr className="owner-total">
            <td>Total</td>
            <td className="num" />
            <td className="num owner-num">{inr(t.yarn)}</td>
            <td className="num owner-num">{inr(t.wage)}</td>
            <td className="num owner-num">{inr(t.machine)}</td>
            <td className="num owner-num">{inr(t.total)}</td>
            <td className="num owner-num">{inr(t.rev)}</td>
            <td
              className={`num owner-num ${t.margin >= 0 ? "owner-pos" : "owner-neg"}`}
            >
              {inr(t.margin)}
            </td>
            <td className="num">
              {t.rev > 0 ? ((t.margin / t.rev) * 100).toFixed(1) : "0.0"}%
            </td>
          </tr>
        </tbody>
      </table>
      <StackedBars
        data={chartData}
        series={COST_SERIES}
        title="Cost per order (stacked) vs revenue — ₹"
      />
    </section>
  );
}

/* ---------------- Machine production (F) ---------------- */
function MachineSection({ machines }) {
  const rows = machines.machines || [];
  const t = machines.totals;
  if (rows.length === 0)
    return (
      <section className="panel">
        <h3>Machine production</h3>
        <p className="muted">No machines to report this month.</p>
      </section>
    );
  const bars = rows.map((m) => ({
    label: m.machine,
    value: m.total_output_meters,
  }));
  return (
    <section className="panel">
      <h3>Machine production</h3>
      <table className="data-table owner-sticky">
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
                <span
                  className={`owner-chip ${
                    m.current_status === "running"
                      ? "owner-chip-green"
                      : m.current_status === "breakdown"
                        ? "owner-chip-red"
                        : "owner-chip-amber"
                  }`}
                >
                  {statusLabel(m.current_status)}
                </span>
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
          {t && (
            <tr className="owner-total">
              <td>Total</td>
              <td />
              <td />
              <td className="num">{qty(t.total_output_meters, "m")}</td>
              <td className="num">{hrs(t.running_hours)}</td>
              <td className="num">{hrs(t.idle_hours)}</td>
              <td className="num">{hrs(t.breakdown_hours)}</td>
              <td className="num owner-num">{inr(t.idle_loss_rupees)}</td>
              <td />
            </tr>
          )}
        </tbody>
      </table>
      <HBars title="Metres produced per machine" data={bars} unit="m" />
    </section>
  );
}

/* ---------------- Money in one place (G) ---------------- */
function MoneySection({ wages, bills, buyerPay, pl }) {
  return (
    <section className="panel">
      <h3>Money in one place</h3>
      <p className="muted" style={{ marginTop: "-0.4rem" }}>
        Totals here match the month summary band above.
      </p>
      <div className="owner-money-grid">
        {/* Wages */}
        <div>
          <h4>
            Wages paid this month (
            {inr(wages.paid_in_month ?? wages.total_paid)})
          </h4>
          <table className="data-table">
            <thead>
              <tr>
                <th>Employee</th>
                <th className="num">Days</th>
                <th className="num">Rate</th>
                <th className="num">Amount</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {(wages.per_employee || []).length === 0 ? (
                <tr>
                  <td colSpan={5} className="muted">
                    No wages recorded this month.
                  </td>
                </tr>
              ) : (
                (wages.per_employee || []).map((e, i) => (
                  <tr key={i}>
                    <td>{e.employee}</td>
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
                ))
              )}
              <tr className="owner-total">
                <td>Total</td>
                <td className="num" />
                <td className="num" />
                <td className="num owner-num">{inr(wages.total_wages)}</td>
                <td />
              </tr>
            </tbody>
          </table>
        </div>

        {/* Raw material bills */}
        <div>
          <h4>Raw material bills</h4>
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Supplier</th>
                <th>Bill</th>
                <th className="num">Amount</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {(bills.bills || []).length === 0 ? (
                <tr>
                  <td colSpan={5} className="muted">
                    No raw material bills recorded.
                  </td>
                </tr>
              ) : (
                (bills.bills || []).map((b, i) => (
                  <tr key={i}>
                    <td>{ddmmyyyy(b.date)}</td>
                    <td>{b.supplier}</td>
                    <td>{b.bill_no}</td>
                    <td className="num owner-num">{inr(b.amount)}</td>
                    <td>
                      <span
                        className={`owner-chip ${b.status === "received" ? "owner-chip-green" : "owner-chip-amber"}`}
                      >
                        {statusLabel(b.status)}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          <p className="muted">
            Paid this month{" "}
            <strong className="owner-num">{inr(bills.total_paid)}</strong> ·
            outstanding{" "}
            <strong className="owner-num">
              {inr(bills.total_outstanding)}
            </strong>
          </p>
        </div>

        {/* Buyer payments */}
        <div>
          <h4>Buyer payments received ({inr(buyerPay.total_received)})</h4>
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Buyer</th>
                <th>Invoice</th>
                <th className="num">Amount</th>
                <th>Method</th>
              </tr>
            </thead>
            <tbody>
              {(buyerPay.payments || []).length === 0 ? (
                <tr>
                  <td colSpan={5} className="muted">
                    No buyer payments received this month.
                  </td>
                </tr>
              ) : (
                (buyerPay.payments || []).map((p, i) => (
                  <tr key={i}>
                    <td>{ddmmyyyy(p.date)}</td>
                    <td>{p.buyer}</td>
                    <td>{p.invoice_no || "—"}</td>
                    <td className="num owner-num">{inr(p.amount)}</td>
                    <td>{p.method}</td>
                  </tr>
                ))
              )}
              <tr className="owner-total">
                <td>Total</td>
                <td />
                <td />
                <td className="num owner-num">
                  {inr(buyerPay.total_received)}
                </td>
                <td />
              </tr>
            </tbody>
          </table>
          <p className="muted">
            Still owed by buyers{" "}
            <strong className="owner-num">
              {inr(buyerPay.total_outstanding)}
            </strong>
          </p>
        </div>
      </div>
    </section>
  );
}

/* ---------------- Order slip side panel (D) ---------------- */
function OrderSlipPanel({ order, month, onClose }) {
  const [slip, setSlip] = useState(null);
  const [error, setError] = useState("");
  const { start, end } = monthRange(month);

  useEffect(() => {
    setSlip(null);
    setError("");
    apiFetch(`/api/reports/orders/${order.id}/slip?start=${start}&end=${end}`)
      .then(setSlip)
      .catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [order.id]);

  function openPdf() {
    // Owner-guarded PDF needs the bearer token; fetch as a blob and open it.
    const url = `/api/reports/orders/${order.id}/slip/pdf?start=${start}&end=${end}`;
    fetch(url, { headers: { Authorization: `Bearer ${getToken()}` } })
      .then((r) => r.blob())
      .then((b) => window.open(URL.createObjectURL(b), "_blank"))
      .catch(() => setError("Could not open the PDF."));
  }

  return (
    <div className="owner-drawer-backdrop" onClick={onClose}>
      <div
        className="owner-drawer owner-slip"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label={`Order slip ${order.order_no}`}
      >
        <div className="owner-slip-actions no-print">
          <button className="link-btn" onClick={onClose}>
            close
          </button>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => window.print()}
            >
              Print
            </button>
            <button className="btn btn-ghost btn-sm" onClick={openPdf}>
              Download PDF
            </button>
          </div>
        </div>

        {error && <div className="form-error">{error}</div>}
        {!slip ? (
          <p className="muted">Loading slip…</p>
        ) : (
          <div className="owner-slip-body">
            <h3>Order slip — {slip.order_no}</h3>
            <table className="owner-slip-kv">
              <tbody>
                <tr>
                  <td>Buyer</td>
                  <td>{slip.buyer_name}</td>
                </tr>
                <tr>
                  <td>Fabric / colour</td>
                  <td>
                    {slip.fabric_type} · {slip.colour}
                  </td>
                </tr>
                <tr>
                  <td>Quantity</td>
                  <td>{qty(slip.quantity_meters, "m")}</td>
                </tr>
                <tr>
                  <td>Rate</td>
                  <td>{inr(slip.unit_price)} / m</td>
                </tr>
                <tr>
                  <td>Deadline</td>
                  <td>{ddmmyyyy(slip.deadline)}</td>
                </tr>
                <tr>
                  <td>Status</td>
                  <td>
                    {statusLabel(slip.status)} · {slip.progress_percent}%{" "}
                    {slip.status !== "cancelled" &&
                      (slip.late ? "(Late)" : "(On track)")}
                  </td>
                </tr>
                {(slip.dispatch_no || slip.invoice_no) && (
                  <tr>
                    <td>Dispatch / invoice</td>
                    <td>
                      {slip.dispatch_no || "—"} / {slip.invoice_no || "—"}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>

            <h4>Rolls ({slip.rolls.length})</h4>
            {slip.rolls.length === 0 ? (
              <p className="muted">No rolls made yet.</p>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Roll</th>
                    <th className="num">Length</th>
                    <th>Machine</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {slip.rolls.map((r) => (
                    <tr key={r.roll_no}>
                      <td>{r.roll_no}</td>
                      <td className="num">{qty(r.length_meters, "m")}</td>
                      <td>{r.machine}</td>
                      <td>{statusLabel(r.result)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            <h4>Cost summary (estimate)</h4>
            <table className="owner-slip-kv">
              <tbody>
                <tr>
                  <td>Yarn</td>
                  <td className="owner-num">{inr(slip.cost.yarn)}</td>
                </tr>
                <tr>
                  <td>Wages</td>
                  <td className="owner-num">{inr(slip.cost.wages)}</td>
                </tr>
                <tr>
                  <td>Machine</td>
                  <td className="owner-num">{inr(slip.cost.machine)}</td>
                </tr>
                <tr>
                  <td>
                    <strong>Total cost</strong>
                  </td>
                  <td className="owner-num">
                    <strong>{inr(slip.cost.total)}</strong>
                  </td>
                </tr>
                <tr>
                  <td>Revenue (est)</td>
                  <td className="owner-num">{inr(slip.cost.revenue_est)}</td>
                </tr>
                <tr>
                  <td>Margin (est)</td>
                  <td
                    className={`owner-num ${slip.cost.margin_est >= 0 ? "owner-pos" : "owner-neg"}`}
                  >
                    {inr(slip.cost.margin_est)}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";
import { isLiveRefresh, useLive } from "../../live/LiveContext.jsx";
import {
  inr,
  ddmmyyyy,
  statusLabel,
  currentMonthValue,
  monthRange,
  monthLabel,
} from "../../lib/format.js";
import "../../owner.css";

// Owner's Payments page: read-only money view for one month. The owner picks a
// month and one of three views (raw material bills, worker cost, payments from
// buyers). Recording payments stays with the accountant; the owner can only
// void a wrong entry.
const VIEWS = [
  ["raw", "Raw material bills"],
  ["wages", "Worker cost"],
  ["buyers", "Payments from buyers"],
];

const inMonth = (value, month) => String(value || "").slice(0, 7) === month;

export default function OwnerMoney() {
  const [month, setMonth] = useState(currentMonthValue());
  const [view, setView] = useState("raw");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [voidTarget, setVoidTarget] = useState(null);
  const [voidReason, setVoidReason] = useState("");
  const [voiding, setVoiding] = useState(false);

  async function load(m = month) {
    if (!isLiveRefresh()) setLoading(true);
    setError("");
    const { start, end } = monthRange(m);
    const q = `start=${start}&end=${end}`;
    try {
      const [payments, bills, wages, buyers, dues] = await Promise.all([
        apiFetch("/api/payments"),
        apiFetch(`/api/reports/bills?${q}`),
        apiFetch(`/api/reports/wages?${q}`),
        apiFetch(`/api/reports/buyer-payments?${q}`),
        apiFetch("/api/payments/dues"),
      ]);
      setData({ payments, bills, wages, buyers, dues });
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

  useLive(["payments", "wages", "yarn"], () => load(month));

  async function confirmVoid(ev) {
    ev.preventDefault();
    if (voidReason.trim().length < 3) return;
    setVoiding(true);
    try {
      await apiFetch(`/api/payments/${voidTarget.id}/void`, {
        method: "POST",
        body: { reason: voidReason.trim() },
      });
      setMsg(`Voided ${inr(voidTarget.amount)} · ${voidTarget.party || "—"}.`);
      setVoidTarget(null);
      setVoidReason("");
      await load(month);
    } catch (err) {
      setError(err.message);
    } finally {
      setVoiding(false);
    }
  }

  const monthPays = (dir) =>
    (data?.payments || []).filter(
      (p) => p.direction === dir && inMonth(p.paid_at, month),
    );
  const live = (rows) => rows.filter((p) => !p.voided);
  const sum = (rows, k = "amount") =>
    rows.reduce((t, r) => t + Number(r[k] || 0), 0);

  const supPays = monthPays("outgoing");
  const buyPays = monthPays("incoming");
  const totals = data && {
    raw: sum(live(supPays)),
    wages: data.wages.total_wages,
    buyers: sum(live(buyPays)),
  };

  return (
    <div className="module owner-page">
      <div className="owner-toolbar">
        <div>
          <h2>Payments</h2>
          <p className="muted" style={{ margin: 0 }}>
            Where the money went in {monthLabel(month)}.
          </p>
        </div>
        <div className="owner-money-filters">
          <label className="owner-month">
            <span>Show</span>
            <select value={view} onChange={(e) => setView(e.target.value)}>
              {VIEWS.map(([k, label], i) => (
                <option key={k} value={k}>
                  {i + 1}. {label}
                </option>
              ))}
            </select>
          </label>
          <label className="owner-month">
            <span>Month</span>
            <input
              type="month"
              value={month}
              onChange={(e) => e.target.value && setMonth(e.target.value)}
            />
          </label>
        </div>
      </div>

      {error && <div className="form-error">{error}</div>}
      {msg && <div className="callout callout-ok">{msg}</div>}

      {/* The three totals double as tabs. */}
      <div className="owner-money-cards">
        {VIEWS.map(([k, label], i) => (
          <button
            key={k}
            type="button"
            className={`owner-money-card is-${k}${view === k ? " is-active" : ""}`}
            onClick={() => setView(k)}
            aria-pressed={view === k}
          >
            <span className="owner-money-label">
              <span className="owner-money-num">{i + 1}</span>
              {label}
            </span>
            <strong className="owner-money-value">
              {totals ? inr(totals[k]) : "—"}
            </strong>
            <span className="owner-money-sub">
              {k === "raw" && "paid to suppliers"}
              {k === "wages" && "wages for the month"}
              {k === "buyers" && "received from buyers"}
            </span>
          </button>
        ))}
      </div>

      {loading || !data ? (
        <section className="panel">
          <p className="muted">Loading {monthLabel(month)}…</p>
        </section>
      ) : view === "raw" ? (
        <RawView
          data={data}
          pays={supPays}
          month={month}
          onVoid={setVoidTarget}
        />
      ) : view === "wages" ? (
        <WagesView wages={data.wages} month={month} />
      ) : (
        <BuyersView
          data={data}
          pays={buyPays}
          month={month}
          onVoid={setVoidTarget}
        />
      )}

      {voidTarget && (
        <div
          className="owner-drawer-backdrop"
          onClick={() => !voiding && setVoidTarget(null)}
        >
          <div
            className="owner-dialog"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-label="Void payment"
          >
            <h3>Void payment</h3>
            <p className="muted">
              {inr(voidTarget.amount)} · {voidTarget.party || "—"} ·{" "}
              {ddmmyyyy(voidTarget.paid_at)}
            </p>
            <p className="muted">
              The record stays for the audit trail but leaves every total. This
              cannot be undone.
            </p>
            <form onSubmit={confirmVoid}>
              <label className="field">
                <span>Reason (required)</span>
                <input
                  autoFocus
                  value={voidReason}
                  onChange={(e) => setVoidReason(e.target.value)}
                  placeholder="e.g. duplicate test entry"
                />
              </label>
              <div className="form-actions" style={{ gap: "0.5rem" }}>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => setVoidTarget(null)}
                  disabled={voiding}
                >
                  Cancel
                </button>
                <button
                  className="btn btn-primary btn-sm"
                  disabled={voiding || voidReason.trim().length < 3}
                >
                  {voiding ? "Voiding…" : "Void payment"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// 10 rows per page; page buttons 1, 2, 3 … under a table.
const PAGE_SIZE = 10;

function usePaged(rows, resetKey) {
  const [page, setPage] = useState(1);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  useEffect(() => setPage(1), [resetKey]);
  const cur = Math.min(page, pages);
  return {
    page: cur,
    pages,
    setPage,
    rows: rows.slice((cur - 1) * PAGE_SIZE, cur * PAGE_SIZE),
    total: rows.length,
  };
}

function Pager({ p }) {
  if (p.pages <= 1) return null;
  const from = (p.page - 1) * PAGE_SIZE + 1;
  const to = Math.min(p.page * PAGE_SIZE, p.total);
  return (
    <nav className="owner-pager" aria-label="Pages">
      <span className="muted">
        {from}–{to} of {p.total}
      </span>
      <div className="owner-pager-btns">
        <button
          type="button"
          onClick={() => p.setPage(p.page - 1)}
          disabled={p.page === 1}
          aria-label="Previous page"
        >
          ‹
        </button>
        {Array.from({ length: p.pages }, (_, i) => i + 1).map((n) => (
          <button
            key={n}
            type="button"
            className={n === p.page ? "is-current" : ""}
            aria-current={n === p.page ? "page" : undefined}
            onClick={() => p.setPage(n)}
          >
            {n}
          </button>
        ))}
        <button
          type="button"
          onClick={() => p.setPage(p.page + 1)}
          disabled={p.page === p.pages}
          aria-label="Next page"
        >
          ›
        </button>
      </div>
    </nav>
  );
}

function PaymentRows({ rows, onVoid, emptyText }) {
  const pg = usePaged(rows, emptyText);
  if (rows.length === 0) return <p className="muted">{emptyText}</p>;
  return (
    <>
    <div className="owner-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Party</th>
            <th>Method</th>
            <th className="num">Amount</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {pg.rows.map((p) => (
            <tr key={p.id} className={p.voided ? "owner-voided" : ""}>
              <td>{ddmmyyyy(p.paid_at)}</td>
              <td>{p.party || "—"}</td>
              <td>{p.method}</td>
              <td className="num owner-num">
                {inr(p.amount)}
                {p.voided && (
                  <div className="owner-void-note">Voided: {p.void_reason}</div>
                )}
              </td>
              <td className="owner-void-cell">
                {p.voided ? (
                  <span className="owner-chip owner-chip-grey">Voided</span>
                ) : (
                  <button className="link-btn" onClick={() => onVoid(p)}>
                    Void
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    <Pager p={pg} />
    </>
  );
}

function RawView({ data, pays, month, onVoid }) {
  const bills = data.bills.bills.filter((b) => inMonth(b.date, month));
  const billsPg = usePaged(bills, month);
  const raised = bills
    .filter((b) => b.status !== "cancelled")
    .reduce((t, b) => t + b.amount, 0);
  return (
    <>
      <section className="panel">
        <div className="owner-money-facts">
          <Fact label="Paid this month" value={data.bills.total_paid} />
          <Fact label="Bills raised this month" value={raised} />
          <Fact
            label="Still to pay suppliers (all months)"
            value={data.dues.total_payable}
            tone="out"
          />
        </div>
      </section>
      <section className="panel">
        <h3>Paid to suppliers</h3>
        <PaymentRows
          rows={pays}
          onVoid={onVoid}
          emptyText={`No supplier payments in ${monthLabel(month)}.`}
        />
      </section>
      <section className="panel">
        <h3>Raw material bills</h3>
        {bills.length === 0 ? (
          <p className="muted">No bills raised in {monthLabel(month)}.</p>
        ) : (
          <>
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Bill no</th>
                  <th>Supplier</th>
                  <th>Yarn</th>
                  <th>Status</th>
                  <th className="num">Amount</th>
                </tr>
              </thead>
              <tbody>
                {billsPg.rows.map((b) => (
                  <tr key={b.bill_no}>
                    <td>{ddmmyyyy(b.date)}</td>
                    <td>{b.bill_no}</td>
                    <td>{b.supplier}</td>
                    <td>
                      {b.yarn_type}
                      {b.colour ? ` · ${b.colour}` : ""}
                    </td>
                    <td>
                      <span className="owner-chip owner-chip-grey">
                        {statusLabel(b.status)}
                      </span>
                    </td>
                    <td className="num owner-num">{inr(b.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager p={billsPg} />
          </>
        )}
      </section>
    </>
  );
}

function WagesView({ wages, month }) {
  const wagePg = usePaged(wages.per_employee, month);
  return (
    <>
      <section className="panel">
        <div className="owner-money-facts">
          <Fact label="Wages for the month" value={wages.total_wages} />
          <Fact label="Paid" value={wages.total_paid} tone="in" />
          <Fact label="Still due" value={wages.total_unpaid} tone="out" />
        </div>
      </section>
      <section className="panel">
        <h3>Worker cost by employee</h3>
        {wages.per_employee.length === 0 ? (
          <p className="muted">No wages in {monthLabel(month)}.</p>
        ) : (
          <>
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Work</th>
                  <th>Period</th>
                  <th className="num">Days</th>
                  <th className="num">Daily wage</th>
                  <th className="num">Amount</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {wagePg.rows.map((w, i) => (
                  <tr key={i}>
                    <td>{w.employee}</td>
                    <td>{w.role_on_floor || "—"}</td>
                    <td>
                      {ddmmyyyy(w.period_start)} – {ddmmyyyy(w.period_end)}
                    </td>
                    <td className="num">{w.days_present}</td>
                    <td className="num owner-num">{inr(w.daily_wage)}</td>
                    <td className="num owner-num">{inr(w.amount)}</td>
                    <td>
                      <span
                        className={`owner-chip ${w.status === "paid" ? "owner-chip-green" : "owner-chip-amber"}`}
                      >
                        {w.status === "paid" ? "Paid" : "Due"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager p={wagePg} />
          </>
        )}
      </section>
    </>
  );
}

function BuyersView({ data, pays, month, onVoid }) {
  const owe = data.dues.buyers_owe_us;
  const owePg = usePaged(owe, month);
  return (
    <>
      <section className="panel">
        <div className="owner-money-facts">
          <Fact
            label="Received this month"
            value={data.buyers.total_received}
            tone="in"
          />
          <Fact
            label="Buyers still owe (all months)"
            value={data.dues.total_receivable}
            tone="out"
          />
          <Fact label="Payments this month" count={pays.filter((p) => !p.voided).length} />
        </div>
      </section>
      <section className="panel">
        <h3>Payments received</h3>
        <PaymentRows
          rows={pays}
          onVoid={onVoid}
          emptyText={`No buyer payments in ${monthLabel(month)}.`}
        />
      </section>
      <section className="panel">
        <h3>Still to receive</h3>
        {owe.length === 0 ? (
          <p className="muted">All buyers have paid in full.</p>
        ) : (
          <>
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Buyer</th>
                  <th>Invoice</th>
                  <th>Invoice date</th>
                  <th className="num">Due</th>
                  <th className="num">Age</th>
                </tr>
              </thead>
              <tbody>
                {owePg.rows.map((b, i) => (
                  <tr key={i}>
                    <td>{b.buyer_name}</td>
                    <td>{b.invoice_no}</td>
                    <td>{ddmmyyyy(b.invoice_date)}</td>
                    <td className="num owner-num">{inr(b.due)}</td>
                    <td className="num">
                      <span
                        className={`owner-chip ${b.overdue ? "owner-chip-red" : "owner-chip-grey"}`}
                      >
                        {b.days_overdue} d{b.overdue ? " · overdue" : ""}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager p={owePg} />
          </>
        )}
      </section>
    </>
  );
}

function Fact({ label, value, count, tone }) {
  return (
    <div className={`owner-money-fact${tone ? ` tone-${tone}` : ""}`}>
      <span>{label}</span>
      <strong>{count !== undefined ? count : inr(value)}</strong>
    </div>
  );
}

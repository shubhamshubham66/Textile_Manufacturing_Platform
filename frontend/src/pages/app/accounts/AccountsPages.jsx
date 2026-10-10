// Accounts & Finance Manager: Sales Invoices, Overtime, Production Expenses,
// Other Expenses, Financial Reports, Notifications and Activity Logs.
// (Buyer Payments, Supplier Payments, Attendance and Wages reuse the existing
// Payments / Attendance / Wages pages via shared resources.)
import { useState } from "react";
import { apiFetch } from "../../../lib/api.js";
import {
  Badge,
  Dialog,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Notice,
  PageHead,
  Stat,
  when,
  useApi,
} from "../../../components/super/kit.jsx";
import "../../../owner.css";

const n = (v) => Number(v || 0).toLocaleString("en-IN");
const rupee = (v) =>
  `₹${Number(v || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

// --------------------------------------------------------------------------- //
export function AccountsInvoices() {
  const { data, error, loading, reload } = useApi("/api/accounts/invoices", [
    "payments",
    "orders",
  ]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead
        title="Sales invoices"
        sub="Invoices raised from completed dispatches, with paid/outstanding balance."
      />
      {data.invoices.length === 0 ? (
        <Empty>No invoices yet.</Empty>
      ) : (
        <section className="panel">
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Order · buyer</th>
                  <th>Dispatch</th>
                  <th className="num">Total</th>
                  <th className="num">Paid</th>
                  <th className="num">Balance</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.invoices.map((inv) => (
                  <tr key={inv.id}>
                    <td>
                      <strong>{inv.invoice_no}</strong>
                      <small className="sm-sub">{when(inv.created_at)}</small>
                    </td>
                    <td>
                      {inv.order_no}
                      <small className="sm-sub">{inv.buyer}</small>
                    </td>
                    <td>{inv.dispatch_no || "—"}</td>
                    <td className="num">{rupee(inv.total)}</td>
                    <td className="num">{rupee(inv.paid)}</td>
                    <td className="num">{rupee(inv.balance)}</td>
                    <td>
                      <Badge
                        value={
                          inv.status === "paid"
                            ? "ok"
                            : inv.status === "part_paid"
                              ? "waiting"
                              : "pending"
                        }
                        label={inv.status.replace("_", " ")}
                      />
                    </td>
                    <td>
                      <a
                        className="link-btn"
                        href={`/api/dispatch/invoice/${inv.id}/pdf`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        PDF
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
export function AccountsOvertime() {
  const { data, error, loading, reload } = useApi("/api/accounts/overtime", [
    "attendance",
    "wages",
  ]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead title="Overtime records" sub={data.note} />
      <div className="sm-stats sm-stats-4">
        <Stat
          label="Overtime hours"
          value={`${n(data.total_overtime_hours)} h`}
          tone={data.total_overtime_hours ? "amber" : undefined}
        />
        <Stat label="Records" value={data.rows.length} />
      </div>
      {data.rows.length === 0 ? (
        <Empty>No overtime in this period.</Empty>
      ) : (
        <section className="panel">
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Worker</th>
                  <th>Date</th>
                  <th>Shift</th>
                  <th className="num">Hours</th>
                  <th className="num">Overtime</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r, i) => (
                  <tr key={i}>
                    <td>{r.employee}</td>
                    <td>{r.work_date}</td>
                    <td>{r.shift}</td>
                    <td className="num">{n(r.hours_worked)}</td>
                    <td className="num">{n(r.overtime_hours)} h</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
export function AccountsProductionExpenses() {
  const { data, error, loading, reload } = useApi(
    "/api/accounts/production-expenses",
    ["production", "payments"],
  );
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead
        title="Production expenses"
        sub={`Cost per order (yarn + wages + machine) for ${data.start} to ${data.end}.`}
      />
      <div className="sm-stats sm-stats-4">
        <Stat label="Yarn" value={rupee(data.totals.yarn)} />
        <Stat label="Wages" value={rupee(data.totals.wages)} />
        <Stat label="Machine" value={rupee(data.totals.machine)} />
        <Stat label="Total" value={rupee(data.totals.total)} tone="blue" />
      </div>
      {data.orders.length === 0 ? (
        <Empty>No production costs in this period.</Empty>
      ) : (
        <section className="panel">
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
                  <th className="num">Margin (est)</th>
                </tr>
              </thead>
              <tbody>
                {data.orders.map((o) => (
                  <tr key={o.order_no}>
                    <td>
                      <strong>{o.order_no}</strong>
                    </td>
                    <td className="num">{n(o.output_meters)} m</td>
                    <td className="num">
                      {rupee(o.yarn_cost)}
                      {o.yarn_basis === "estimate" && (
                        <small className="sm-sub muted">est</small>
                      )}
                    </td>
                    <td className="num">{rupee(o.wage_cost)}</td>
                    <td className="num">{rupee(o.machine_cost)}</td>
                    <td className="num">{rupee(o.total_cost)}</td>
                    <td
                      className="num"
                      style={{
                        color:
                          o.margin_est < 0
                            ? "var(--danger, #c0392b)"
                            : undefined,
                      }}
                    >
                      {rupee(o.margin_est)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
export function AccountsExpenses() {
  const { data, error, loading, reload } = useApi("/api/accounts/expenses", [
    "payments",
  ]);
  const [form, setForm] = useState(false);
  const [msg, setMsg] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead
        title="Other expenses"
        sub="Factory rent, utilities, transport and other authorized expenses."
      >
        <button
          className="btn btn-primary btn-sm"
          onClick={() => setForm(true)}
        >
          ＋ Record expense
        </button>
      </PageHead>
      <Notice onClose={() => setMsg("")}>{msg}</Notice>
      <div className="sm-stats sm-stats-4">
        <Stat label="Total other expenses" value={rupee(data.total)} />
        <Stat label="Entries" value={data.expenses.length} />
      </div>
      {data.expenses.length === 0 ? (
        <Empty>No other expenses recorded yet.</Empty>
      ) : (
        <section className="panel">
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Category</th>
                  <th className="num">Amount</th>
                  <th>Method</th>
                  <th>Reference</th>
                  <th>Note</th>
                </tr>
              </thead>
              <tbody>
                {data.expenses.map((e) => (
                  <tr key={e.id}>
                    <td>{when(e.paid_at)}</td>
                    <td>
                      <Badge value="info" label={e.category} />
                    </td>
                    <td className="num">{rupee(e.amount)}</td>
                    <td>{e.method}</td>
                    <td>{e.reference || "—"}</td>
                    <td>{e.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {form && (
        <ExpenseDialog
          categories={data.categories}
          onClose={() => setForm(false)}
          onDone={(t) => {
            setForm(false);
            setMsg(t);
            reload();
          }}
        />
      )}
    </div>
  );
}

function ExpenseDialog({ categories, onClose, onDone }) {
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState(categories[0] || "other");
  const [note, setNote] = useState("");
  const [method, setMethod] = useState("bank");
  const [reference, setReference] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function go() {
    if (!amount || Number(amount) <= 0) return setErr("Enter the amount.");
    if (note.trim().length < 2) return setErr("Add a short note.");
    setBusy(true);
    setErr("");
    try {
      const res = await apiFetch("/api/accounts/expenses", {
        method: "POST",
        body: {
          amount: Number(amount),
          category,
          note: note.trim(),
          method,
          reference: reference.trim() || null,
        },
      });
      onDone(`Expense recorded (${res.category} ${rupee(res.amount)}).`);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog title="Record expense" onClose={onClose}>
      <ErrorBox error={err} />
      <Field label="Amount (₹)">
        <input
          type="number"
          min="0"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          autoFocus
        />
      </Field>
      <Field label="Category">
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Method">
        <select value={method} onChange={(e) => setMethod(e.target.value)}>
          <option value="bank">Bank</option>
          <option value="cash">Cash</option>
          <option value="upi">UPI</option>
        </select>
      </Field>
      <Field label="Reference (optional, blocks duplicates)">
        <input
          value={reference}
          onChange={(e) => setReference(e.target.value)}
        />
      </Field>
      <Field label="Note" wide>
        <textarea
          rows={2}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </Field>
      <div className="sm-row-end">
        <button className="btn btn-ghost btn-sm" onClick={onClose}>
          Cancel
        </button>
        <button className="btn btn-primary btn-sm" onClick={go} disabled={busy}>
          {busy ? "Saving…" : "Record expense"}
        </button>
      </div>
    </Dialog>
  );
}

// --------------------------------------------------------------------------- //
export function AccountsReports() {
  const [period, setPeriod] = useState("month");
  const { data, error, loading, reload } = useApi(
    `/api/accounts/reports?period=${period}`,
    ["payments", "wages", "orders"],
  );
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead
        title="Financial reports"
        sub={`Income, expenses, cash-flow and profit/loss — ${data.start} to ${data.end}.`}
      >
        <div className="sm-tabs" role="tablist">
          {[
            ["day", "Day"],
            ["month", "Month"],
            ["year", "Year"],
          ].map(([k, l]) => (
            <button
              key={k}
              role="tab"
              aria-selected={period === k}
              className={period === k ? "is-active" : ""}
              onClick={() => setPeriod(k)}
            >
              {l}
            </button>
          ))}
        </div>
      </PageHead>

      <div className="sm-stats sm-stats-4">
        <Stat label="Invoiced" value={rupee(data.income.invoiced)} />
        <Stat label="Cash in" value={rupee(data.cash_flow.in)} tone="green" />
        <Stat label="Cash out" value={rupee(data.cash_flow.out)} />
        <Stat
          label="Net cash flow"
          value={rupee(data.cash_flow.net)}
          tone={data.cash_flow.net >= 0 ? "green" : "red"}
        />
      </div>

      <div className="sm-grid-2">
        <section className="panel">
          <h3>Expenses</h3>
          <ul className="sm-bars">
            {[
              ["Supplier payments", data.expenses.supplier_payments],
              ["Wages paid", data.expenses.wages_paid],
              ["Other expenses", data.expenses.other_expenses],
            ].map(([label, val]) => {
              const max = Math.max(
                1,
                data.expenses.supplier_payments,
                data.expenses.wages_paid,
                data.expenses.other_expenses,
              );
              return (
                <li key={label}>
                  <span>{label}</span>
                  <i style={{ width: `${(val / max) * 100}%` }} />
                  <b>{rupee(val)}</b>
                </li>
              );
            })}
          </ul>
          <p className="muted sm-small">
            Total expenses: {rupee(data.expenses.total)}
          </p>
        </section>

        <section className="panel">
          <h3>Profit / loss</h3>
          <div className="sm-stats">
            <Stat
              label={
                data.is_profit ? "Profit (cash basis)" : "Loss (cash basis)"
              }
              value={rupee(data.profit_or_loss)}
              tone={data.is_profit ? "green" : "red"}
            />
            <Stat
              label="Wages due"
              value={rupee(data.wages_due)}
              tone={data.wages_due ? "amber" : undefined}
            />
          </div>
          <dl className="sm-mini">
            <div>
              <dt>Receivable (buyers owe)</dt>
              <dd>{rupee(data.receivable)}</dd>
            </div>
            <div>
              <dt>Payable (we owe suppliers)</dt>
              <dd>{rupee(data.payable)}</dd>
            </div>
          </dl>
        </section>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
export function AccountsNotifications() {
  const { data, error, loading, reload } = useApi(
    "/api/accounts/notifications",
    ["notifications", "payments", "orders"],
  );
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;

  async function markRead(id) {
    try {
      await apiFetch(`/api/accounts/notifications/${id}/read`, {
        method: "POST",
      });
      reload();
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="module sm-page">
      <PageHead
        title="Notifications"
        sub={`${data.unread} unread · invoicing, payment follow-ups and dues.`}
      />
      {data.notifications.length === 0 ? (
        <Empty>You're all caught up — no notifications.</Empty>
      ) : (
        <section className="panel">
          <ul className="sm-exceptions is-plain">
            {data.notifications.map((nt) => (
              <li key={nt.id} style={{ opacity: nt.read ? 0.6 : 1 }}>
                <strong>{nt.title}</strong>
                {nt.body ? ` — ${nt.body}` : ""}
                <small className="sm-sub">
                  {nt.from || "System"} · {when(nt.created_at)}
                  {!nt.read && (
                    <button
                      className="link-btn"
                      onClick={() => markRead(nt.id)}
                      style={{ marginLeft: 8 }}
                    >
                      mark read
                    </button>
                  )}
                </small>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
export function AccountsActivity() {
  const { data, error, loading, reload } = useApi("/api/accounts/activity", [
    "payments",
    "orders",
    "dispatch",
    "attendance",
  ]);
  const [cat, setCat] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const rows = cat ? data.rows.filter((r) => r.category === cat) : data.rows;
  return (
    <div className="module sm-page">
      <PageHead
        title="Activity logs"
        sub="A trail of payment, order, dispatch and attendance actions."
      />
      <div className="sm-tabs" role="tablist">
        <button
          role="tab"
          aria-selected={cat === ""}
          className={cat === "" ? "is-active" : ""}
          onClick={() => setCat("")}
        >
          All
        </button>
        {data.categories.map((cName) => (
          <button
            key={cName}
            role="tab"
            aria-selected={cat === cName}
            className={cat === cName ? "is-active" : ""}
            onClick={() => setCat(cName)}
          >
            {cName}
          </button>
        ))}
      </div>
      {rows.length === 0 ? (
        <Empty>No activity recorded.</Empty>
      ) : (
        <section className="panel">
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Who</th>
                  <th>Category</th>
                  <th>Action</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((a) => (
                  <tr key={a.id}>
                    <td>{when(a.at)}</td>
                    <td>{a.user}</td>
                    <td>
                      <Badge value="info" label={a.category} />
                    </td>
                    <td>{a.action.replace(/_/g, " ")}</td>
                    <td>{a.details}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

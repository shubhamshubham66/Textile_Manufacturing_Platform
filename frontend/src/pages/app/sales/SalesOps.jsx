// Invoice Details (read-only), Notifications, Reports and Activity Logs for the
// Sales & Dispatch Manager.
import { useState } from "react";
import { apiFetch, openPdf } from "../../../lib/api.js";
import {
  Badge,
  Empty,
  ErrorBox,
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
// Invoice Details (read-only).
// --------------------------------------------------------------------------- //
export function SalesInvoices() {
  const { data, error, loading, reload } = useApi("/api/sales/invoices", [
    "payments",
    "orders",
  ]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead title="Invoice details" sub={data.note} />
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
                      <button
                        type="button"
                        className="link-btn"
                        onClick={() => openPdf(`/api/dispatch/invoice/${inv.id}/pdf`)}
                      >
                        PDF
                      </button>
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
// Notifications.
// --------------------------------------------------------------------------- //
export function SalesNotifications() {
  const { data, error, loading, reload } = useApi("/api/sales/notifications", [
    "notifications",
    "quality",
    "orders",
    "payments",
  ]);
  const [msg, setMsg] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;

  async function markRead(id) {
    try {
      await apiFetch(`/api/sales/notifications/${id}/read`, { method: "POST" });
      reload();
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="module sm-page">
      <PageHead
        title="Notifications"
        sub={`${data.unread} unread · QC approvals, dispatch and payment follow-ups.`}
      />
      <Notice onClose={() => setMsg("")}>{msg}</Notice>
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
// Reports.
// --------------------------------------------------------------------------- //
export function SalesReports() {
  const { data, error, loading, reload } = useApi("/api/sales/reports", [
    "orders",
    "payments",
  ]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const maxMeters = Math.max(1, ...data.by_buyer.map((b) => b.meters));
  return (
    <div className="module sm-page">
      <PageHead
        title="Sales & dispatch reports"
        sub={`Dispatch and delivery summary from ${data.start} to ${data.end}.`}
      />
      <div className="sm-stats sm-stats-4">
        <Stat label="Dispatches" value={data.total_dispatches} />
        <Stat
          label="Metres shipped"
          value={`${n(data.total_meters)} m`}
          tone="green"
        />
        <Stat
          label="Delivered"
          value={data.delivered}
          hint={`${data.pending_delivery} pending`}
        />
        <Stat label="Invoiced" value={rupee(data.invoiced_total)} />
      </div>

      <section className="panel">
        <h3>Dispatch by buyer</h3>
        {data.by_buyer.length === 0 ? (
          <Empty>No dispatches in this period.</Empty>
        ) : (
          <ul className="sm-bars">
            {data.by_buyer.map((b) => (
              <li key={b.buyer}>
                <span>{b.buyer}</span>
                <i style={{ width: `${(b.meters / maxMeters) * 100}%` }} />
                <b>
                  {n(b.meters)} m ({b.dispatches})
                </b>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel">
        <h3>Pending buyer payments (read-only)</h3>
        {data.dues.rows.filter((r) => r.balance > 0).length === 0 ? (
          <Empty>No outstanding buyer payments.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Buyer</th>
                  <th className="num">Total</th>
                  <th className="num">Balance</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.dues.rows
                  .filter((r) => r.balance > 0)
                  .map((r) => (
                    <tr key={r.invoice_no}>
                      <td>{r.invoice_no}</td>
                      <td>{r.buyer}</td>
                      <td className="num">{rupee(r.total)}</td>
                      <td className="num">{rupee(r.balance)}</td>
                      <td>
                        <Badge
                          value={
                            r.status === "part_paid" ? "waiting" : "pending"
                          }
                          label={r.status.replace("_", " ")}
                        />
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
            <p className="muted sm-small">
              Total outstanding: {rupee(data.dues.total_outstanding)}. Payments
              are recorded by the accountant.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Activity Logs.
// --------------------------------------------------------------------------- //
export function SalesActivity() {
  const { data, error, loading, reload } = useApi("/api/sales/activity", [
    "dispatch",
    "orders",
    "quality",
    "payments",
  ]);
  const [cat, setCat] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const rows = cat ? data.rows.filter((r) => r.category === cat) : data.rows;
  return (
    <div className="module sm-page">
      <PageHead
        title="Activity logs"
        sub="A trail of dispatch, order, QC and payment actions."
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

// Sales & Dispatch Manager dashboard — the seven required cards from live data
// (/api/sales/dashboard). Reuses the shared super UI kit for a consistent look.
import {
  Badge,
  Empty,
  ErrorBox,
  Loading,
  PageHead,
  Stat,
  go,
  when,
  useApi,
} from "../../../components/super/kit.jsx";
import "../../../owner.css";

const n = (v) => Number(v || 0).toLocaleString("en-IN");
const rupee = (v) =>
  `₹${Number(v || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

export default function SalesDashboard() {
  const { data, error, loading, reload } = useApi("/api/sales/dashboard", [
    "orders",
    "quality",
    "payments",
    "tasks",
  ]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const c = data.cards;

  return (
    <div className="module sm-page">
      <PageHead
        title="Sales & dispatch dashboard"
        sub="Live view of buyer orders, QC-approved stock, dispatches, deliveries and pending payments."
      />

      <div className="sm-stats sm-stats-4">
        <Stat
          label="Total buyer orders"
          value={c.total_buyer_orders}
          hint="confirmed onward"
          onClick={() => go("/app/sd-orders")}
        />
        <Stat
          label="Pending dispatches"
          value={c.pending_dispatches}
          hint="not yet delivered"
          tone={c.pending_dispatches ? "amber" : undefined}
          onClick={() => go("/app/sd-delivery")}
        />
        <Stat
          label="QC-approved stock"
          value={`${n(c.qc_approved_rolls)} rolls`}
          hint={`${n(c.qc_approved_meters)} m ready`}
          tone={c.qc_approved_rolls ? "green" : undefined}
          onClick={() => go("/app/sd-stock")}
        />
        <Stat
          label="Orders ready for dispatch"
          value={c.orders_ready_for_dispatch}
          hint="have approved stock"
          tone={c.orders_ready_for_dispatch ? "green" : undefined}
          onClick={() => go("/app/sd-planning")}
        />
      </div>
      <div className="sm-stats sm-stats-4">
        <Stat
          label="Dispatched orders"
          value={c.dispatched_orders}
          onClick={() => go("/app/sd-history")}
        />
        <Stat
          label="Delayed deliveries"
          value={c.delayed_deliveries}
          hint={c.delayed_deliveries ? "past deadline" : "on time"}
          tone={c.delayed_deliveries ? "red" : "green"}
          onClick={() => go("/app/sd-tracking")}
        />
        <Stat
          label="Pending buyer payments"
          value={c.pending_buyer_payments}
          hint={`${rupee(c.pending_buyer_amount)} outstanding`}
          tone={c.pending_buyer_payments ? "amber" : undefined}
          onClick={() => go("/app/sd-invoices")}
        />
        <Stat
          label="Read-only (Accounts)"
          value="₹"
          hint="payments owned by accountant"
        />
      </div>

      {data.delayed.length > 0 && (
        <section className="panel sm-attention">
          <h3>Delayed deliveries — notify the Supermanager</h3>
          <ul className="sm-exceptions">
            {data.delayed.map((o) => (
              <li key={o.id}>
                <span aria-hidden>!</span> <strong>{o.order_no}</strong> (
                {o.buyer}) past deadline
                {o.deadline ? ` (${o.deadline})` : ""} · {o.status_label}.
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="sm-grid-2">
        <section className="panel">
          <h3>Ready for dispatch</h3>
          {data.ready_for_dispatch.length === 0 ? (
            <Empty>No orders have approved stock waiting to ship.</Empty>
          ) : (
            <div className="owner-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Order</th>
                    <th>Buyer</th>
                    <th className="num">Rolls ready</th>
                    <th>Deadline</th>
                  </tr>
                </thead>
                <tbody>
                  {data.ready_for_dispatch.map((o) => (
                    <tr key={o.id} className={o.late ? "row-warn" : ""}>
                      <td>
                        <strong>{o.order_no}</strong>
                      </td>
                      <td>{o.buyer}</td>
                      <td className="num">
                        {o.rolls_ready} · {n(o.meters_ready)} m
                      </td>
                      <td>{o.deadline || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="panel">
          <h3>Pending buyer payments (read-only)</h3>
          {data.pending_payments.filter((p) => p.balance > 0).length === 0 ? (
            <Empty>No outstanding buyer payments.</Empty>
          ) : (
            <ul className="sm-exceptions is-plain">
              {data.pending_payments
                .filter((p) => p.balance > 0)
                .map((p) => (
                  <li key={p.invoice_no}>
                    <strong>{p.invoice_no}</strong> ({p.buyer}) —{" "}
                    {rupee(p.balance)} due
                    <small className="sm-sub">{p.order_no}</small>
                  </li>
                ))}
            </ul>
          )}
        </section>
      </div>

      <section className="panel">
        <h3>Recent dispatches</h3>
        {data.recent_dispatches.length === 0 ? (
          <Empty>No dispatches yet.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Dispatch</th>
                  <th>Order · buyer</th>
                  <th className="num">Rolls / m</th>
                  <th>Vehicle</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_dispatches.map((d) => (
                  <tr key={d.id}>
                    <td>
                      <strong>{d.dispatch_no}</strong>
                      {d.challan_no && (
                        <small className="sm-sub">{d.challan_no}</small>
                      )}
                    </td>
                    <td>
                      {d.order_no}
                      <small className="sm-sub">{d.buyer}</small>
                    </td>
                    <td className="num">
                      {d.total_rolls} · {n(d.total_meters)} m
                    </td>
                    <td>{d.vehicle_no || "—"}</td>
                    <td>
                      <Badge
                        value={d.delivered_at ? "shipped" : "packed"}
                        label={d.delivered_at ? "Delivered" : d.status}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel">
        <h3>Recent activity</h3>
        {data.activity.length === 0 ? (
          <Empty>No activity recorded yet.</Empty>
        ) : (
          <ul className="sm-exceptions is-plain">
            {data.activity.map((a) => (
              <li key={a.id}>
                <strong>{a.action.replace(/_/g, " ")}</strong> — {a.details}
                <small className="sm-sub">
                  {a.user} · {when(a.at)}
                </small>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

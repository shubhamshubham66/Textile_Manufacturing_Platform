import { HBars } from "../../../components/owner/Charts.jsx";
import { Badge, Empty, ErrorBox, Loading, PageHead, Stat, go, when, day, useApi } from "../../../components/super/kit.jsx";
import { statusLabel } from "../../../lib/format.js";
import "../../../owner.css";

const STATUS_COLOUR = {
  pending_review: "#d97706", draft: "#94a3b8", clarification: "#f59e0b", confirmed: "#2563eb",
  in_production: "#4f46e5", in_quality: "#7c3aed", ready_to_ship: "#0d9488", dispatched: "#15803d",
  closed: "#166534", rejected: "#dc2626", cancelled: "#9ca3af",
};
const ALL_TOPICS = ["orders", "machines", "production", "quality", "yarn", "payments", "wages", "tasks"];


export default function SuperDashboard() {
  const { data, error, loading, reload } = useApi("/api/super/overview", ALL_TOPICS);

  if (loading && !data) return <Loading text="Loading the factory overview…" />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const c = data.cards;

  return (
    <div className="module sm-page">
      <PageHead title="Factory overview" sub="Everything below comes from today's live data." />
      <ErrorBox error={error} />

      <div className="sm-stats">
        <Stat label="Department managers" value={c.department_managers} onClick={() => go("/app/super-managers")} />
        <Stat label="Workers" value={c.workers} onClick={() => go("/app/super-workers")} />
        <Stat label="Pending buyer orders" value={c.pending_orders} tone={c.pending_orders ? "amber" : undefined} onClick={() => go("/app/order-desk")} />
        <Stat label="Confirmed orders" value={c.confirmed_orders} onClick={() => go("/app/order-desk")} />
        <Stat label="Orders in production" value={c.in_production} onClick={() => go("/app/super-production")} />
        <Stat label="QC pending (rolls)" value={c.qc_pending} tone={c.qc_pending ? "amber" : undefined} onClick={() => go("/app/super-quality")} />
        <Stat label="Dispatch pending" value={c.dispatch_pending} onClick={() => go("/app/super-dispatch")} />
        <Stat label="Workers present today" value={`${c.present_today} / ${c.workers}`} onClick={() => go("/app/super-attendance")} />
      </div>

      <div className="sm-grid-2">
        <section className="panel">
          <div className="sm-panel-head">
            <h3>Critical alerts</h3>
            <button className="link-btn" onClick={() => go("/app/super-alerts")}>
              All {data.alerts_total} alerts
            </button>
          </div>
          {data.alerts.length === 0 ? (
            <Empty>No critical or warning alerts right now.</Empty>
          ) : (
            <ul className="sm-alerts">
              {data.alerts.map((a, i) => (
                <li key={i} className={`sm-alert is-${a.severity}`}>
                  <button type="button" onClick={() => go(a.page)}>
                    <Badge value={a.severity} />
                    <span>
                      <strong>{a.title}</strong>
                      <small className="muted">{a.detail}</small>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel">
          <div className="sm-panel-head">
            <h3>Pending approvals</h3>
            <button className="link-btn" onClick={() => go("/app/order-desk")}>
              Open order management
            </button>
          </div>
          {data.pending_approvals.length === 0 ? (
            <Empty>No orders are waiting for a decision.</Empty>
          ) : (
            <ul className="sm-list">
              {data.pending_approvals.map((o) => (
                <li key={o.id}>
                  <button type="button" onClick={() => go("/app/order-desk")}>
                    <span>
                      <span>
                        <strong>{o.order_no}</strong> · {o.buyer}
                      </span>
                      <small className="muted">
                        {o.fabric_type} {o.colour} · {o.quantity_meters.toLocaleString("en-IN")} m · due {day(o.deadline)}
                      </small>
                    </span>
                    <Badge value={o.status} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <div className="sm-grid-2">
        <section className="panel">
          <HBars
            title="Order progress — orders at each stage"
            data={data.order_progress.map((r) => ({
              label: statusLabel(r.status),
              value: r.count,
              colour: STATUS_COLOUR[r.status],
            }))}
            unit=""
          />
        </section>

        <section className="panel">
          <h3>Recent activity</h3>
          {data.activity.length === 0 ? (
            <Empty>Nothing recorded yet. Actions appear here as people work.</Empty>
          ) : (
            <ol className="sm-timeline">
              {data.activity.map((a) => (
                <li key={a.id}>
                  <span className={`sm-dot cat-${a.category}`} aria-hidden />
                  <div>
                    <span>{a.details}</span>
                    <small className="muted">
                      {a.user} · {when(a.at)}
                    </small>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>

      <section className="panel">
        <div className="sm-panel-head">
          <h3>Department performance — this month</h3>
          <button className="link-btn" onClick={() => go("/app/super-managers")}>
            Department managers
          </button>
        </div>
        <div className="sm-depts">
          {data.departments.map((d) => (
            <article key={d.department} className="sm-dept">
              <header>
                <strong>{d.label}</strong>
                <small className="muted">{d.managers.length ? d.managers.join(", ") : "No manager assigned"}</small>
              </header>
              <dl>
                {d.metrics.map((m) => (
                  <div key={m.label}>
                    <dt>{m.label}</dt>
                    <dd>{m.value}</dd>
                  </div>
                ))}
              </dl>
              <footer>
                <span>{d.tasks_open} open tasks</span>
                {d.tasks_overdue > 0 && <Badge value="delayed" label={`${d.tasks_overdue} overdue`} />}
              </footer>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="sm-panel-head">
          <h3>Recent orders</h3>
          <button className="link-btn" onClick={() => go("/app/order-desk")}>
            All orders
          </button>
        </div>
        <div className="owner-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Order</th>
                <th>Buyer</th>
                <th>Fabric</th>
                <th className="num">Metres</th>
                <th>Deadline</th>
                <th>Progress</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_orders.map((o) => (
                <tr key={o.id}>
                  <td>{o.order_no}</td>
                  <td>{o.buyer}</td>
                  <td>
                    {o.fabric_type} · {o.colour}
                  </td>
                  <td className="num">{o.quantity_meters.toLocaleString("en-IN")}</td>
                  <td>
                    {day(o.deadline)} {o.late && <Badge value="delayed" label="Late" />}
                  </td>
                  <td>
                    <span className="sm-progress" title={`${o.progress}%`}>
                      <i style={{ width: `${o.progress}%` }} />
                    </span>
                  </td>
                  <td>
                    <Badge value={o.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}


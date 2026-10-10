// Production Manager dashboard — the seven required cards, built from live
// data via /api/prod/dashboard. Reuses the shared super UI kit so the look
// matches the rest of the app.
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

export default function ProdDashboard() {
  const { data, error, loading, reload } = useApi("/api/prod/dashboard", [
    "production",
    "machines",
    "orders",
    "quality",
    "tasks",
    "yarn",
  ]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const c = data.cards;

  return (
    <div className="module sm-page">
      <PageHead
        title="Production dashboard"
        sub="Live view of the floor — orders, targets, machines, workers, materials, delays and QC handovers."
      />

      {/* The seven required cards */}
      <div className="sm-stats sm-stats-4">
        <Stat
          label="Active production orders"
          value={c.active_orders}
          hint="confirmed · in production · in QC"
          onClick={() => go("/app/pm-orders")}
        />
        <Stat
          label="Today's target vs actual"
          value={`${n(c.today_actual)} / ${n(c.today_target)} m`}
          hint={`${c.today_percent}% of today's target made`}
          tone={
            c.today_percent >= 100
              ? "green"
              : c.today_percent >= 60
                ? "amber"
                : c.today_actual
                  ? "amber"
                  : undefined
          }
          onClick={() => go("/app/pm-monitoring")}
        />
        <Stat
          label="Machine status"
          value={`${c.machines_running}/${c.machine_total} running`}
          hint={`${c.machines_idle} idle · ${c.machines_down} down`}
          tone={c.machines_down ? "red" : c.machines_idle ? "amber" : "green"}
          onClick={() => go("/app/pm-machines")}
        />
        <Stat
          label="Worker tasks"
          value={c.worker_tasks_open}
          hint={
            c.worker_tasks_overdue
              ? `${c.worker_tasks_overdue} overdue`
              : "all on track"
          }
          tone={c.worker_tasks_overdue ? "red" : undefined}
          onClick={() => go("/app/pm-workers")}
        />
      </div>
      <div className="sm-stats sm-stats-4">
        <Stat
          label="Material shortages"
          value={c.material_shortages}
          hint={
            c.material_shortages ? "need a purchase request" : "all covered"
          }
          tone={c.material_shortages ? "red" : "green"}
          onClick={() => go("/app/pm-materials")}
        />
        <Stat
          label="Delayed orders"
          value={c.delayed_orders}
          hint={c.delayed_orders ? "past deadline" : "none late"}
          tone={c.delayed_orders ? "red" : "green"}
          onClick={() => go("/app/pm-monitoring")}
        />
        <Stat
          label="Pending QC handover"
          value={c.qc_pending_batches}
          hint={`${n(c.qc_pending_rolls)} rolls awaiting inspection`}
          tone={c.qc_pending_batches ? "amber" : undefined}
          onClick={() => go("/app/pm-qc")}
        />
        <Stat
          label="Rework / rejects"
          value={c.rework_rejects}
          hint={c.rework_rejects ? "returned by QC" : "none"}
          tone={c.rework_rejects ? "amber" : undefined}
          onClick={() => go("/app/pm-qc")}
        />
      </div>

      {/* Delays need attention first */}
      {data.delayed_orders.length > 0 && (
        <section className="panel sm-attention">
          <h3>Delayed orders — tell the Supermanager</h3>
          <ul className="sm-exceptions">
            {data.delayed_orders.map((o) => (
              <li key={o.id}>
                <span aria-hidden>!</span> <strong>{o.order_no}</strong> (
                {o.buyer}) is past its deadline
                {o.deadline ? ` (${o.deadline})` : ""} with {o.progress}% made.
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="sm-grid-2">
        <section className="panel">
          <h3>Active orders</h3>
          {data.active_orders.length === 0 ? (
            <Empty>No orders are in production right now.</Empty>
          ) : (
            <div className="owner-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Order</th>
                    <th className="num">Ordered</th>
                    <th>Progress</th>
                    <th>Deadline</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.active_orders.map((o) => (
                    <tr key={o.id} className={o.late ? "row-warn" : ""}>
                      <td>
                        <strong>{o.order_no}</strong>
                        <small className="sm-sub">
                          {o.buyer} · {o.fabric_type} {o.colour}
                        </small>
                      </td>
                      <td className="num">{n(o.quantity_meters)} m</td>
                      <td>
                        <span className="sm-progress" title={`${o.progress}%`}>
                          <i style={{ width: `${o.progress}%` }} />
                        </span>{" "}
                        <small>{o.progress}%</small>
                      </td>
                      <td>
                        {o.deadline || "—"}{" "}
                        {o.delay && (
                          <Badge
                            value={o.delay === "late" ? "delayed" : "warning"}
                            label={o.delay === "late" ? "Late" : "At risk"}
                          />
                        )}
                      </td>
                      <td>
                        <Badge value={o.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="panel">
          <h3>Worker tasks in progress</h3>
          {data.worker_tasks.length === 0 ? (
            <Empty>No open worker tasks.</Empty>
          ) : (
            <ul className="sm-exceptions is-plain">
              {data.worker_tasks.map((t) => (
                <li key={t.id}>
                  <strong>{t.title}</strong> <Badge value={t.shown_status} />
                  {t.worker ? (
                    <small className="sm-sub">{t.worker.name}</small>
                  ) : (
                    <small className="sm-sub muted">unassigned</small>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <div className="sm-grid-2">
        <section className="panel">
          <h3>Material shortages</h3>
          {data.material_shortages.length === 0 ? (
            <Empty>Every active order has enough yarn.</Empty>
          ) : (
            <ul className="sm-exceptions">
              {data.material_shortages.map((s) => (
                <li key={s.order_id}>
                  <span aria-hidden>!</span> <strong>{s.order_no}</strong> short{" "}
                  {n(s.short_kg)} kg {s.colour}
                  {s.request ? (
                    <small className="sm-sub">
                      request {s.request.pr_no} · {s.request.status}
                    </small>
                  ) : (
                    <small className="sm-sub muted">
                      no request raised yet
                    </small>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel">
          <h3>Pending QC handover</h3>
          {data.qc_pending.length === 0 ? (
            <Empty>Nothing waiting for QC.</Empty>
          ) : (
            <div className="owner-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Order</th>
                    <th className="num">Rolls</th>
                    <th className="num">Metres</th>
                  </tr>
                </thead>
                <tbody>
                  {data.qc_pending.map((b) => (
                    <tr key={b.order_id}>
                      <td>{b.order_no}</td>
                      <td className="num">{b.rolls}</td>
                      <td className="num">{n(b.meters)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

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

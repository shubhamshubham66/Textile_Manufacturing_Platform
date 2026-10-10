// Worker dashboard — the six cards from live data (/api/worker/dashboard),
// scoped to the logged-in worker's own Employee record.
import {
  Badge,
  Empty,
  ErrorBox,
  Loading,
  PageHead,
  Stat,
  go,
  useApi,
} from "../../../components/super/kit.jsx";
import "../../../owner.css";

const n = (v) => Number(v || 0).toLocaleString("en-IN");
const ATT_LABEL = {
  present: "Present",
  half_day: "Half day",
  absent: "Absent",
  not_marked: "Not marked",
};

export default function WorkerDashboard() {
  const { data, error, loading, reload } = useApi("/api/worker/dashboard", [
    "tasks",
    "production",
    "orders",
  ]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const c = data.cards;

  return (
    <div className="module sm-page">
      <PageHead
        title={`Hello, ${data.worker.name}`}
        sub={`${data.worker.role_on_floor || "Employee"}${data.worker.department ? ` · ${data.worker.department}` : ""}${data.manager ? ` · reports to ${data.manager.name}` : ""}`}
      />

      <div className="sm-stats sm-stats-4">
        <Stat
          label="Today's attendance"
          value={ATT_LABEL[c.today_attendance] || c.today_attendance}
          hint={c.checked_in ? "checked in" : ""}
          tone={
            c.today_attendance === "present"
              ? "green"
              : c.today_attendance === "not_marked"
                ? "amber"
                : undefined
          }
          onClick={() => go("/app/wk-attendance")}
        />
        <Stat
          label="Assigned tasks"
          value={c.assigned_tasks}
          onClick={() => go("/app/wk-tasks")}
        />
        <Stat
          label="In progress"
          value={c.in_progress}
          tone={c.in_progress ? "blue" : undefined}
          onClick={() => go("/app/wk-tasks")}
        />
        <Stat
          label="Completed"
          value={c.completed}
          tone="green"
          onClick={() => go("/app/wk-history")}
        />
      </div>
      <div className="sm-stats sm-stats-4">
        <Stat
          label="Pending tasks"
          value={c.pending}
          tone={c.pending ? "amber" : undefined}
          onClick={() => go("/app/wk-tasks")}
        />
        <Stat
          label="Paused"
          value={c.paused}
          tone={c.paused ? "amber" : undefined}
          onClick={() => go("/app/wk-tasks")}
        />
        <Stat
          label="Production today"
          value={`${n(c.today_output)} m`}
          hint="your output logged today"
          tone={c.today_output ? "green" : undefined}
          onClick={() => go("/app/wk-production")}
        />
      </div>

      <section className="panel">
        <h3>My current tasks</h3>
        {data.tasks.length === 0 ? (
          <Empty>No tasks assigned to you right now.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Task</th>
                  <th>Order</th>
                  <th>Priority</th>
                  <th>Deadline</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.tasks.map((t) => (
                  <tr key={t.id}>
                    <td>
                      <strong>{t.title}</strong>
                      {t.details && (
                        <small className="sm-sub">{t.details}</small>
                      )}
                    </td>
                    <td>{t.order_no || "—"}</td>
                    <td>
                      <Badge value={t.priority} />
                    </td>
                    <td>{t.deadline || "—"}</td>
                    <td>
                      <Badge value={t.shown_status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="muted sm-small">
          Go to{" "}
          <button className="link-btn" onClick={() => go("/app/wk-tasks")}>
            My Tasks
          </button>{" "}
          to start, pause or complete work.
        </p>
      </section>
    </div>
  );
}

import { useEffect, useState } from "react";
import { apiFetch } from "../../../lib/api.js";
import { Badge, Dialog, Empty, ErrorBox, Field, Loading, Notice, PageHead, day, when, useApi } from "../../../components/super/kit.jsx";
import "../../../owner.css";

const PRIORITIES = ["low", "medium", "high", "urgent"];
const STATUSES = [
  ["", "All statuses"],
  ["pending", "Pending"],
  ["in_progress", "In progress"],
  ["completed", "Completed"],
  ["delayed", "Delayed"],
];

// Assign instructions to department managers and follow their progress.
export default function SuperTasks() {
  const [filters, setFilters] = useState({ department: "", status: "", priority: "" });
  const qs = new URLSearchParams(Object.entries(filters).filter(([, v]) => v)).toString();
  const { data, error, loading, reload } = useApi(`/api/super/tasks${qs ? `?${qs}` : ""}`, ["tasks", "orders"]);
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState(null);
  const [msg, setMsg] = useState(null);
  const setF = (k) => (e) => setFilters({ ...filters, [k]: e.target.value });
  const tasks = data?.tasks || [];
  const n = (s) => tasks.filter((t) => t.shown_status === s).length;

  return (
    <div className="module sm-page">
      <PageHead title="Assign instructions" sub="Give a department manager a task, with priority and a deadline. They post progress from their My tasks page.">
        <button className="btn btn-primary" onClick={() => setOpen(true)}>
          ＋ New instruction
        </button>
      </PageHead>
      <Notice kind={msg?.kind} onClose={() => setMsg(null)}>
        {msg?.text}
      </Notice>
      <ErrorBox error={error} onRetry={reload} />

      <div className="sm-stats sm-stats-4">
        <div className="sm-stat"><span className="sm-stat-label">Pending</span><strong className="sm-stat-value">{n("pending")}</strong></div>
        <div className="sm-stat"><span className="sm-stat-label">In progress</span><strong className="sm-stat-value">{n("in_progress")}</strong></div>
        <div className={`sm-stat${n("delayed") ? " tone-red" : ""}`}><span className="sm-stat-label">Delayed</span><strong className="sm-stat-value">{n("delayed")}</strong></div>
        <div className="sm-stat"><span className="sm-stat-label">Completed</span><strong className="sm-stat-value">{n("completed")}</strong></div>
      </div>

      <section className="panel">
        <div className="sm-toolbar">
          <h3>Instructions</h3>
          <div className="sm-filters">
            <select className="sm-select" value={filters.department} onChange={setF("department")} aria-label="Department">
              <option value="">All departments</option>
              {(data?.departments || []).map((d) => (
                <option key={d.key} value={d.key}>
                  {d.label}
                </option>
              ))}
            </select>
            <select className="sm-select" value={filters.status} onChange={setF("status")} aria-label="Status">
              {STATUSES.map(([k, l]) => (
                <option key={k} value={k}>
                  {l}
                </option>
              ))}
            </select>
            <select className="sm-select" value={filters.priority} onChange={setF("priority")} aria-label="Priority">
              <option value="">All priorities</option>
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p[0].toUpperCase() + p.slice(1)}
                </option>
              ))}
            </select>
          </div>
        </div>
        {loading && !data ? (
          <Loading />
        ) : tasks.length === 0 ? (
          <Empty>No instructions match. Confirming an order creates them automatically, or add one above.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Instruction</th>
                  <th>Department · manager</th>
                  <th>Order</th>
                  <th>Priority</th>
                  <th>Deadline</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((t) => (
                  <tr key={t.id}>
                    <td>
                      <strong>{t.title}</strong>
                      {t.auto && <small className="sm-sub">Created on order confirmation</small>}
                      {t.worker && <small className="sm-sub">Worker: {t.worker.name}</small>}
                    </td>
                    <td>
                      {t.department_label}
                      <small className="sm-sub">{t.manager?.name || "Not assigned — any manager of the department"}</small>
                    </td>
                    <td>{t.order_no || "—"}</td>
                    <td>
                      <Badge value={t.priority} />
                    </td>
                    <td>{day(t.deadline)}</td>
                    <td>
                      <Badge value={t.shown_status} />
                    </td>
                    <td>
                      <button className="btn btn-ghost btn-sm" onClick={() => setDetail(t)}>
                        Open
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {open && (
        <TaskForm
          meta={data}
          onClose={() => setOpen(false)}
          onSaved={(t) => {
            setOpen(false);
            setMsg({ kind: "ok", text: `Instruction sent to ${t.manager?.name || t.department_label}.` });
            reload();
          }}
        />
      )}
      {detail && (
        <TaskDetail
          task={detail}
          managers={(data?.managers || []).filter((m) => m.department === detail.department)}
          onClose={() => setDetail(null)}
          onChanged={() => {
            setDetail(null);
            reload();
          }}
        />
      )}
    </div>
  );
}

function TaskForm({ meta, onClose, onSaved }) {
  const [f, setF] = useState({ department: "", manager_user_id: "", title: "", details: "", priority: "medium", deadline: "", order_id: "" });
  const [errs, setErrs] = useState({});
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const mgrs = (meta?.managers || []).filter((m) => m.department === f.department);

  async function submit(e) {
    e.preventDefault();
    const x = {};
    if (!f.department) x.department = "Choose a department.";
    if (f.title.trim().length < 3) x.title = "Write a short title (3+ characters).";
    if (f.deadline && f.deadline < new Date().toISOString().slice(0, 10)) x.deadline = "Deadline cannot be in the past.";
    setErrs(x);
    if (Object.keys(x).length) return;
    setBusy(true);
    setErr("");
    try {
      const t = await apiFetch("/api/super/tasks", {
        method: "POST",
        body: {
          department: f.department,
          manager_user_id: f.manager_user_id ? Number(f.manager_user_id) : null,
          title: f.title.trim(),
          details: f.details.trim() || null,
          priority: f.priority,
          deadline: f.deadline || null,
          order_id: f.order_id ? Number(f.order_id) : null,
        },
      });
      onSaved(t);
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog title="New instruction" onClose={onClose} wide>
      <ErrorBox error={err} />
      <form className="form-grid sm-form" onSubmit={submit} noValidate>
        <Field label="Department" error={errs.department}>
          <select value={f.department} onChange={(e) => setF({ ...f, department: e.target.value, manager_user_id: "" })}>
            <option value="">Choose…</option>
            {(meta?.departments || []).map((d) => (
              <option key={d.key} value={d.key}>
                {d.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Manager">
          <select value={f.manager_user_id} onChange={set("manager_user_id")} disabled={!f.department}>
            <option value="">{f.department && mgrs.length === 0 ? "No manager in this department" : "Any manager of the department"}</option>
            {mgrs.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Instruction" error={errs.title} wide>
          <input value={f.title} onChange={set("title")} placeholder="e.g. Service loom Weave-02 before Monday" />
        </Field>
        <Field label="Task details" wide>
          <textarea rows={3} value={f.details} onChange={set("details")} />
        </Field>
        <Field label="Priority">
          <select value={f.priority} onChange={set("priority")}>
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {p[0].toUpperCase() + p.slice(1)}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Deadline" error={errs.deadline}>
          <input type="date" value={f.deadline} onChange={set("deadline")} />
        </Field>
        <Field label="For buyer order (optional)" wide>
          <select value={f.order_id} onChange={set("order_id")}>
            <option value="">Not linked to an order</option>
            {(meta?.orders || []).map((o) => (
              <option key={o.id} value={o.id}>
                {o.order_no} · {o.status.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </Field>
        <div className="sm-row-end sm-wide">
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary btn-sm" disabled={busy}>
            {busy ? "Sending…" : "Send instruction"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

function TaskDetail({ task, managers, onClose, onChanged }) {
  const [updates, setUpdates] = useState(null);
  const [f, setF] = useState({ priority: task.priority, deadline: task.deadline || "", status: task.status, manager_user_id: task.manager?.id || "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    apiFetch(`/api/super/tasks/${task.id}/updates`).then(setUpdates).catch((e) => setErr(e.message));
  }, [task.id]);

  async function save() {
    setBusy(true);
    setErr("");
    try {
      await apiFetch(`/api/super/tasks/${task.id}`, {
        method: "PUT",
        body: { priority: f.priority, deadline: f.deadline || null, status: f.status, manager_user_id: f.manager_user_id ? Number(f.manager_user_id) : null },
      });
      onChanged();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog title={task.title} onClose={onClose} wide>
      <ErrorBox error={err} />
      <p className="muted">
        {task.department_label}
        {task.order_no ? ` · ${task.order_no}` : ""} · created {when(task.created_at)}
      </p>
      {task.details && <p className="sm-quote">{task.details}</p>}
      <div className="form-grid sm-form">
        <Field label="Manager">
          <select value={f.manager_user_id} onChange={(e) => setF({ ...f, manager_user_id: e.target.value })}>
            <option value="">Any manager of the department</option>
            {managers.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Priority">
          <select value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })}>
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {p[0].toUpperCase() + p.slice(1)}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Deadline">
          <input type="date" value={f.deadline} onChange={(e) => setF({ ...f, deadline: e.target.value })} />
        </Field>
        <Field label="Status">
          <select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}>
            <option value="pending">Pending</option>
            <option value="in_progress">In progress</option>
            <option value="completed">Completed</option>
          </select>
        </Field>
      </div>
      <div className="sm-row-end">
        <button className="btn btn-primary btn-sm" onClick={save} disabled={busy}>
          {busy ? "Saving…" : "Save"}
        </button>
      </div>
      <h4>Progress updates</h4>
      {!updates ? (
        <Loading />
      ) : updates.length === 0 ? (
        <Empty>No updates from the manager yet.</Empty>
      ) : (
        <ol className="sm-timeline">
          {updates.map((u) => (
            <li key={u.id}>
              <span className="sm-dot" aria-hidden />
              <div>
                <span>
                  <Badge value={u.status} /> {u.note}
                </span>
                <small className="muted">
                  {u.user} · {when(u.at)}
                </small>
              </div>
            </li>
          ))}
        </ol>
      )}
    </Dialog>
  );
}

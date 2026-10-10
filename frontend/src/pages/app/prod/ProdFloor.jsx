// Machine Management, Worker & Task Assignment and Production Monitoring for
// the Production Manager. These write to the live tables (machine status,
// worker tasks, production output).
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
// Machine Management — change status (running / idle / breakdown) with a reason.
// --------------------------------------------------------------------------- //
export function ProdMachines() {
  const { data, error, loading, reload } = useApi("/api/prod/machines", [
    "machines",
    "production",
  ]);
  const [edit, setEdit] = useState(null);
  const [msg, setMsg] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead
        title="Machine management"
        sub="Status, assigned order and downtime loss for every machine."
      />
      <div className="sm-stats sm-stats-4">
        <Stat label="Running" value={data.counts.running} tone="green" />
        <Stat
          label="Idle"
          value={data.counts.idle}
          tone={data.counts.idle ? "amber" : undefined}
        />
        <Stat
          label="Maintenance / breakdown"
          value={data.counts.maintenance}
          tone={data.counts.maintenance ? "red" : undefined}
        />
        <Stat
          label="Downtime loss"
          value={rupee(data.idle_loss.total_rupees)}
          hint={`${n(data.idle_loss.total_hours)} h lost`}
          tone={data.idle_loss.total_rupees ? "red" : undefined}
        />
      </div>
      <Notice onClose={() => setMsg("")}>{msg}</Notice>

      <section className="panel">
        <div className="sm-machines">
          {data.machines.map((m) => (
            <article key={m.id} className={`sm-machine is-${m.raw_status}`}>
              <header>
                <strong>{m.name}</strong>
                <Badge value={m.status} />
              </header>
              <small className="muted">
                {m.type} · since {when(m.since)}
              </small>
              <p>
                {m.order_no
                  ? `On ${m.order_no}${m.stage ? ` (${m.stage})` : ""} · ${m.progress}%`
                  : "No order loaded"}
              </p>
              <small>
                {n(m.total_meters)} m made
                {m.lost_hours
                  ? ` · ${n(m.lost_hours)} h lost (${rupee(m.loss_rupees)})`
                  : ""}
              </small>
              <div className="sm-row-end" style={{ marginTop: 8 }}>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => setEdit(m)}
                >
                  Change status
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>

      {edit && (
        <StatusDialog
          machine={edit}
          onClose={() => setEdit(null)}
          onDone={(t) => {
            setEdit(null);
            setMsg(t);
            reload();
          }}
        />
      )}
    </div>
  );
}

function StatusDialog({ machine, onClose, onDone }) {
  const [status, setStatus] = useState("running");
  const [reason, setReason] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const needsReason = status === "idle" || status === "breakdown";

  async function go() {
    if (needsReason && reason.trim().length < 3)
      return setErr("Give a reason for idle/breakdown.");
    setBusy(true);
    setErr("");
    try {
      await apiFetch(`/api/prod/machines/${machine.id}/status`, {
        method: "POST",
        body: { status, reason: reason.trim() || null },
      });
      onDone(`${machine.name} set to ${status}.`);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog title={`${machine.name} — status`} onClose={onClose}>
      <ErrorBox error={err} />
      <Field label="Status">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          autoFocus
        >
          <option value="running">Running</option>
          <option value="idle">Idle</option>
          <option value="breakdown">Breakdown</option>
        </select>
      </Field>
      {needsReason && (
        <Field label="Reason (required)">
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. no order, waiting for yarn, motor fault"
          />
        </Field>
      )}
      <div className="sm-row-end">
        <button className="btn btn-ghost btn-sm" onClick={onClose}>
          Cancel
        </button>
        <button className="btn btn-primary btn-sm" onClick={go} disabled={busy}>
          {busy ? "Saving…" : "Save status"}
        </button>
      </div>
    </Dialog>
  );
}

// --------------------------------------------------------------------------- //
// Worker & Task Assignment.
// --------------------------------------------------------------------------- //
export function ProdWorkers() {
  const { data, error, loading, reload } = useApi("/api/prod/workers", [
    "tasks",
    "wages",
  ]);
  const [form, setForm] = useState(false);
  const [assign, setAssign] = useState(null);
  const [msg, setMsg] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead
        title="Worker & task assignment"
        sub="Hand production tasks to floor workers and track their progress."
      >
        <button
          className="btn btn-primary btn-sm"
          onClick={() => setForm(true)}
        >
          ＋ New task
        </button>
      </PageHead>
      <Notice onClose={() => setMsg("")}>{msg}</Notice>

      <section className="panel">
        <h3>Floor workers</h3>
        {data.workers.length === 0 ? (
          <Empty>No workers in the production department yet.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Worker</th>
                  <th>Role</th>
                  <th className="num">Open tasks</th>
                  <th>Current</th>
                </tr>
              </thead>
              <tbody>
                {data.workers.map((w) => (
                  <tr key={w.id}>
                    <td>
                      <strong>{w.name}</strong>
                    </td>
                    <td>{w.role_on_floor || "—"}</td>
                    <td className="num">{w.open_tasks}</td>
                    <td>
                      {w.tasks.length ? (
                        w.tasks.map((t) => (
                          <Badge key={t.id} value={t.status} label={t.title} />
                        ))
                      ) : (
                        <span className="muted">idle</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel">
        <h3>Production tasks</h3>
        {data.tasks.length === 0 ? (
          <Empty>No tasks yet. Create one to assign work.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Task</th>
                  <th>Order</th>
                  <th>Worker</th>
                  <th>Priority</th>
                  <th>Deadline</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.tasks.map((t) => (
                  <tr key={t.id}>
                    <td>
                      <strong>{t.title}</strong>
                      {t.auto && (
                        <small className="sm-sub muted">
                          auto (from Supermanager)
                        </small>
                      )}
                    </td>
                    <td>{t.order_no || "—"}</td>
                    <td>
                      {t.worker ? (
                        t.worker.name
                      ) : (
                        <span className="muted">unassigned</span>
                      )}
                    </td>
                    <td>
                      <Badge value={t.priority} />
                    </td>
                    <td>{t.deadline || "—"}</td>
                    <td>
                      <Badge value={t.shown_status} />
                    </td>
                    <td>
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => setAssign(t)}
                      >
                        Manage
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {form && (
        <TaskDialog
          workers={data.workers}
          orders={data.orders}
          onClose={() => setForm(false)}
          onDone={(t) => {
            setForm(false);
            setMsg(t);
            reload();
          }}
        />
      )}
      {assign && (
        <ManageTask
          task={assign}
          workers={data.workers}
          onClose={() => setAssign(null)}
          onDone={(t) => {
            setAssign(null);
            setMsg(t);
            reload();
          }}
        />
      )}
    </div>
  );
}

function TaskDialog({ workers, orders, onClose, onDone }) {
  const [title, setTitle] = useState("");
  const [details, setDetails] = useState("");
  const [orderId, setOrderId] = useState("");
  const [workerId, setWorkerId] = useState("");
  const [priority, setPriority] = useState("medium");
  const [deadline, setDeadline] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function go() {
    if (title.trim().length < 3) return setErr("Give the task a title.");
    setBusy(true);
    setErr("");
    try {
      await apiFetch("/api/prod/tasks", {
        method: "POST",
        body: {
          title: title.trim(),
          details: details.trim() || null,
          order_id: orderId ? Number(orderId) : null,
          worker_employee_id: workerId ? Number(workerId) : null,
          priority,
          deadline: deadline || null,
        },
      });
      onDone("Task created.");
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog title="New production task" onClose={onClose}>
      <ErrorBox error={err} />
      <Field label="Title">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          autoFocus
          placeholder="e.g. Weave ORD-2003 — target 1,000 m"
        />
      </Field>
      <Field label="Details (optional)">
        <textarea
          rows={2}
          value={details}
          onChange={(e) => setDetails(e.target.value)}
        />
      </Field>
      <Field label="Order (optional)">
        <select value={orderId} onChange={(e) => setOrderId(e.target.value)}>
          <option value="">No specific order</option>
          {orders.map((o) => (
            <option key={o.id} value={o.id}>
              {o.order_no}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Assign to worker (optional)">
        <select value={workerId} onChange={(e) => setWorkerId(e.target.value)}>
          <option value="">Leave unassigned</option>
          {workers.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Priority">
        <select value={priority} onChange={(e) => setPriority(e.target.value)}>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
          <option value="urgent">Urgent</option>
        </select>
      </Field>
      <Field label="Deadline (optional)">
        <input
          type="date"
          value={deadline}
          onChange={(e) => setDeadline(e.target.value)}
        />
      </Field>
      <div className="sm-row-end">
        <button className="btn btn-ghost btn-sm" onClick={onClose}>
          Cancel
        </button>
        <button className="btn btn-primary btn-sm" onClick={go} disabled={busy}>
          {busy ? "Saving…" : "Create task"}
        </button>
      </div>
    </Dialog>
  );
}

function ManageTask({ task, workers, onClose, onDone }) {
  const [workerId, setWorkerId] = useState(
    task.worker ? String(task.worker.id) : "",
  );
  const [status, setStatus] = useState(task.status);
  const [note, setNote] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function go() {
    setBusy(true);
    setErr("");
    try {
      await apiFetch(`/api/prod/tasks/${task.id}/assign`, {
        method: "POST",
        body: { worker_employee_id: workerId ? Number(workerId) : null },
      });
      await apiFetch(`/api/prod/tasks/${task.id}/status`, {
        method: "POST",
        body: { status, note: note.trim() || null },
      });
      onDone("Task updated.");
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog title={task.title} onClose={onClose}>
      <ErrorBox error={err} />
      <Field label="Assign to worker">
        <select
          value={workerId}
          onChange={(e) => setWorkerId(e.target.value)}
          autoFocus
        >
          <option value="">Unassigned</option>
          {workers.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Status">
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="pending">Pending</option>
          <option value="in_progress">In progress</option>
          <option value="completed">Completed</option>
        </select>
      </Field>
      <Field label="Note (optional)">
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
          {busy ? "Saving…" : "Save"}
        </button>
      </div>
    </Dialog>
  );
}

// --------------------------------------------------------------------------- //
// Production Monitoring — output, waste, downtime; log output.
// --------------------------------------------------------------------------- //
export function ProdMonitoring() {
  const { data, error, loading, reload } = useApi("/api/prod/monitoring", [
    "production",
    "machines",
    "orders",
  ]);
  const [log, setLog] = useState(false);
  const [msg, setMsg] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead
        title="Production monitoring"
        sub="Live output, machine state, downtime loss and anything running late."
      >
        <button className="btn btn-primary btn-sm" onClick={() => setLog(true)}>
          ＋ Log output
        </button>
      </PageHead>
      <div className="sm-stats sm-stats-4">
        <Stat
          label="Output today"
          value={`${n(data.today_output)} m`}
          tone={data.today_output ? "green" : undefined}
        />
        <Stat
          label="Running"
          value={data.machine_counts.running}
          tone="green"
        />
        <Stat
          label="Downtime now"
          value={data.downtime.length}
          tone={data.downtime.length ? "amber" : undefined}
        />
        <Stat
          label="Downtime loss"
          value={rupee(data.idle_loss_total)}
          tone={data.idle_loss_total ? "red" : undefined}
        />
      </div>
      <Notice onClose={() => setMsg("")}>{msg}</Notice>

      {data.delays.length > 0 && (
        <section className="panel sm-attention">
          <h3>Orders running late or at risk</h3>
          <ul className="sm-exceptions">
            {data.delays.map((o) => (
              <li key={o.id}>
                <span aria-hidden>!</span> <strong>{o.order_no}</strong>{" "}
                {o.delay === "late"
                  ? `past deadline (${o.deadline})`
                  : `due in ${o.days_left} days`}{" "}
                · {o.progress}% made.
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="sm-grid-2">
        <section className="panel">
          <h3>Machines</h3>
          <div className="sm-machines">
            {data.machines.map((m) => (
              <article key={m.id} className={`sm-machine is-${m.raw_status}`}>
                <header>
                  <strong>{m.name}</strong>
                  <Badge value={m.status} />
                </header>
                <p>
                  {m.order_no
                    ? `On ${m.order_no} · ${m.progress}%`
                    : "No order loaded"}
                </p>
                <small>
                  {n(m.total_meters)} m total
                  {m.lost_hours ? ` · ${n(m.lost_hours)} h lost` : ""}
                </small>
              </article>
            ))}
          </div>
        </section>

        <section className="panel">
          <h3>Recent output</h3>
          {data.recent_output.length === 0 ? (
            <Empty>No output logged yet.</Empty>
          ) : (
            <div className="owner-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Machine</th>
                    <th>Order</th>
                    <th>Stage</th>
                    <th className="num">Metres</th>
                    <th>Day</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_output.map((r, i) => (
                    <tr key={i}>
                      <td>{r.machine}</td>
                      <td>{r.order_no}</td>
                      <td>{r.stage}</td>
                      <td className="num">{n(r.output_meters)}</td>
                      <td>{r.log_date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {log && (
        <OutputDialog
          machines={data.machines}
          orders={data.orders}
          onClose={() => setLog(false)}
          onDone={(t) => {
            setLog(false);
            setMsg(t);
            reload();
          }}
        />
      )}
    </div>
  );
}

function OutputDialog({ machines, orders, onClose, onDone }) {
  const [machineId, setMachineId] = useState("");
  const [orderId, setOrderId] = useState("");
  const [meters, setMeters] = useState("");
  const [waste, setWaste] = useState("");
  const [stage, setStage] = useState("");
  const [shift, setShift] = useState("morning");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function go() {
    if (!machineId || !orderId) return setErr("Pick a machine and an order.");
    if (!meters || Number(meters) <= 0)
      return setErr("Enter the metres produced.");
    setBusy(true);
    setErr("");
    try {
      const res = await apiFetch("/api/prod/output", {
        method: "POST",
        body: {
          machine_id: Number(machineId),
          order_id: Number(orderId),
          output_meters: Number(meters),
          waste_meters: waste ? Number(waste) : 0,
          stage: stage || null,
          shift,
        },
      });
      onDone(
        `Logged ${n(res.logged_meters)} m — ${res.order_no} now ${res.order_progress_percent}%.`,
      );
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog title="Log production output" onClose={onClose}>
      <ErrorBox error={err} />
      <Field label="Machine">
        <select
          value={machineId}
          onChange={(e) => setMachineId(e.target.value)}
          autoFocus
        >
          <option value="">Select…</option>
          {machines.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name} ({m.type})
            </option>
          ))}
        </select>
      </Field>
      <Field label="Order">
        <select value={orderId} onChange={(e) => setOrderId(e.target.value)}>
          <option value="">Select…</option>
          {orders.map((o) => (
            <option key={o.id} value={o.id}>
              {o.order_no}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Metres produced">
        <input
          type="number"
          min="0"
          value={meters}
          onChange={(e) => setMeters(e.target.value)}
        />
      </Field>
      <Field label="Waste (metres, optional)">
        <input
          type="number"
          min="0"
          value={waste}
          onChange={(e) => setWaste(e.target.value)}
        />
      </Field>
      <Field label="Stage (optional)">
        <select value={stage} onChange={(e) => setStage(e.target.value)}>
          <option value="">Use machine's stage</option>
          <option value="spinning">Spinning</option>
          <option value="weaving">Weaving</option>
          <option value="dyeing">Dyeing</option>
        </select>
      </Field>
      <Field label="Shift">
        <select value={shift} onChange={(e) => setShift(e.target.value)}>
          <option value="morning">Morning</option>
          <option value="evening">Evening</option>
          <option value="night">Night</option>
        </select>
      </Field>
      <div className="sm-row-end">
        <button className="btn btn-ghost btn-sm" onClick={onClose}>
          Cancel
        </button>
        <button className="btn btn-primary btn-sm" onClick={go} disabled={busy}>
          {busy ? "Saving…" : "Log output"}
        </button>
      </div>
    </Dialog>
  );
}

// Worker: My Tasks (start/pause/complete), Production Updates, and Machine
// Status (report a breakdown / shortage / problem).
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
  useApi,
} from "../../../components/super/kit.jsx";
import "../../../owner.css";

const n = (v) => Number(v || 0).toLocaleString("en-IN");

// --------------------------------------------------------------------------- //
// My Tasks.
// --------------------------------------------------------------------------- //
export function WorkerTasks() {
  const { data, error, loading, reload } = useApi("/api/worker/tasks", [
    "tasks",
  ]);
  const [busy, setBusy] = useState(0);
  const [msg, setMsg] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;

  async function act(task, action) {
    setBusy(task.id);
    setMsg("");
    try {
      await apiFetch(`/api/worker/tasks/${task.id}/action`, {
        method: "POST",
        body: { action },
      });
      setMsg(
        `"${task.title}" ${action === "complete" ? "completed" : action + "ed"}.`,
      );
      reload();
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(0);
    }
  }

  return (
    <div className="module sm-page">
      <PageHead
        title="My tasks"
        sub="Start, pause and complete the work assigned to you. Completing a task notifies your manager."
      />
      <Notice onClose={() => setMsg("")}>{msg}</Notice>
      {data.tasks.length === 0 ? (
        <Empty>No tasks for you yet. Your manager will assign work here.</Empty>
      ) : (
        <ul className="sm-tasklist">
          {data.tasks.map((t) => (
            <li key={t.id} className={`is-${t.shown_status}`}>
              <div>
                <strong>{t.title}</strong>
                {t.details && <p className="muted">{t.details}</p>}
                <small className="muted">
                  {t.order_no ? `${t.order_no} · ` : ""}
                  {t.deadline ? `Due ${t.deadline}` : "No deadline"}
                  {!t.mine ? " · unassigned (start to pick up)" : ""}
                </small>
              </div>
              <div className="sm-task-side">
                <Badge value={t.priority} />
                <Badge value={t.shown_status} />
                <div className="sm-actions">
                  {t.status === "pending" && (
                    <button
                      className="btn btn-primary btn-sm"
                      disabled={busy === t.id}
                      onClick={() => act(t, "start")}
                    >
                      Start
                    </button>
                  )}
                  {t.status === "in_progress" && (
                    <>
                      <button
                        className="btn btn-ghost btn-sm"
                        disabled={busy === t.id}
                        onClick={() => act(t, "pause")}
                      >
                        Pause
                      </button>
                      <button
                        className="btn btn-primary btn-sm"
                        disabled={busy === t.id}
                        onClick={() => act(t, "complete")}
                      >
                        Complete
                      </button>
                    </>
                  )}
                  {t.status === "paused" && (
                    <>
                      <button
                        className="btn btn-primary btn-sm"
                        disabled={busy === t.id}
                        onClick={() => act(t, "resume")}
                      >
                        Resume
                      </button>
                      <button
                        className="btn btn-ghost btn-sm"
                        disabled={busy === t.id}
                        onClick={() => act(t, "complete")}
                      >
                        Complete
                      </button>
                    </>
                  )}
                  {t.status === "completed" && (
                    <span className="muted">Done</span>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Production Updates.
// --------------------------------------------------------------------------- //
export function WorkerProduction() {
  const { data, error, loading, reload } = useApi("/api/worker/production", [
    "production",
    "orders",
  ]);
  const [form, setForm] = useState(false);
  const [msg, setMsg] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead
        title="Production updates"
        sub="Submit your output, waste, defects and downtime. Your manager verifies and sends finished batches to QC."
      >
        <button
          className="btn btn-primary btn-sm"
          onClick={() => setForm(true)}
        >
          ＋ Submit update
        </button>
      </PageHead>
      <Notice onClose={() => setMsg("")}>{msg}</Notice>
      {data.recent.length === 0 ? (
        <Empty>No production updates from you yet.</Empty>
      ) : (
        <section className="panel">
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Machine</th>
                  <th>Order</th>
                  <th>Stage</th>
                  <th className="num">Output</th>
                  <th>Day</th>
                </tr>
              </thead>
              <tbody>
                {data.recent.map((r, i) => (
                  <tr key={i}>
                    <td>{r.machine}</td>
                    <td>{r.order_no}</td>
                    <td>{r.stage}</td>
                    <td className="num">{n(r.output_meters)} m</td>
                    <td>{r.log_date}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {form && (
        <ProductionDialog
          machines={data.machines}
          orders={data.orders}
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

function ProductionDialog({ machines, orders, onClose, onDone }) {
  const [machineId, setMachineId] = useState("");
  const [orderId, setOrderId] = useState("");
  const [meters, setMeters] = useState("");
  const [waste, setWaste] = useState("");
  const [defects, setDefects] = useState("");
  const [downtime, setDowntime] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function go() {
    if (!machineId || !orderId) return setErr("Pick a machine and an order.");
    if (!meters || Number(meters) <= 0)
      return setErr("Enter the metres produced.");
    setBusy(true);
    setErr("");
    try {
      await apiFetch("/api/worker/production", {
        method: "POST",
        body: {
          machine_id: Number(machineId),
          order_id: Number(orderId),
          output_meters: Number(meters),
          waste_meters: waste ? Number(waste) : 0,
          defects: defects ? Number(defects) : 0,
          downtime_minutes: downtime ? Number(downtime) : 0,
        },
      });
      onDone(`Logged ${n(Number(meters))} m. Your manager has been notified.`);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog title="Submit production update" onClose={onClose}>
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
              {o.order_no} — {o.fabric_type}
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
      <Field label="Waste (metres)">
        <input
          type="number"
          min="0"
          value={waste}
          onChange={(e) => setWaste(e.target.value)}
        />
      </Field>
      <Field label="Defects (count)">
        <input
          type="number"
          min="0"
          value={defects}
          onChange={(e) => setDefects(e.target.value)}
        />
      </Field>
      <Field label="Downtime (minutes)">
        <input
          type="number"
          min="0"
          value={downtime}
          onChange={(e) => setDowntime(e.target.value)}
        />
      </Field>
      <div className="sm-row-end">
        <button className="btn btn-ghost btn-sm" onClick={onClose}>
          Cancel
        </button>
        <button className="btn btn-primary btn-sm" onClick={go} disabled={busy}>
          {busy ? "Saving…" : "Submit update"}
        </button>
      </div>
    </Dialog>
  );
}

// --------------------------------------------------------------------------- //
// Machine Status + report a problem.
// --------------------------------------------------------------------------- //
export function WorkerMachines() {
  const { data, error, loading, reload } = useApi("/api/worker/machines", [
    "machines",
    "production",
  ]);
  const [report, setReport] = useState(null);
  const [msg, setMsg] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead title="Machine status" sub={data.note}>
        <button
          className="btn btn-primary btn-sm"
          onClick={() => setReport({})}
        >
          Report a problem
        </button>
      </PageHead>
      <Notice onClose={() => setMsg("")}>{msg}</Notice>
      <section className="panel">
        <div className="sm-machines">
          {data.machines.map((m) => (
            <article
              key={m.id}
              className={`sm-machine is-${m.status === "maintenance" ? "breakdown" : m.status}`}
            >
              <header>
                <strong>{m.name}</strong>
                <Badge value={m.status} />
              </header>
              <small className="muted">{m.type}</small>
              <p>
                {m.order_no
                  ? `On ${m.order_no}${m.stage ? ` (${m.stage})` : ""}`
                  : "No order loaded"}
              </p>
              <div className="sm-row-end" style={{ marginTop: 8 }}>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() =>
                    setReport({ machine_id: m.id, machine: m.name })
                  }
                >
                  Report
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>
      {report && (
        <ReportDialog
          prefill={report}
          onClose={() => setReport(null)}
          onDone={(t) => {
            setReport(null);
            setMsg(t);
          }}
        />
      )}
    </div>
  );
}

function ReportDialog({ prefill, onClose, onDone }) {
  const [kind, setKind] = useState("breakdown");
  const [message, setMessage] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function go() {
    if (message.trim().length < 3) return setErr("Describe the problem.");
    setBusy(true);
    setErr("");
    try {
      await apiFetch("/api/worker/report", {
        method: "POST",
        body: {
          kind,
          machine_id: prefill.machine_id || null,
          message: message.trim(),
        },
      });
      onDone("Reported. Your manager and the Supermanager have been notified.");
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title={
        prefill.machine ? `Report — ${prefill.machine}` : "Report a problem"
      }
      onClose={onClose}
    >
      <ErrorBox error={err} />
      <Field label="Type">
        <select
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          autoFocus
        >
          <option value="breakdown">Machine breakdown</option>
          <option value="material_shortage">Material shortage</option>
          <option value="problem">Production problem</option>
        </select>
      </Field>
      <Field label="What happened?" wide>
        <textarea
          rows={3}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
      </Field>
      <div className="sm-row-end">
        <button className="btn btn-ghost btn-sm" onClick={onClose}>
          Cancel
        </button>
        <button className="btn btn-primary btn-sm" onClick={go} disabled={busy}>
          {busy ? "Sending…" : "Send report"}
        </button>
      </div>
    </Dialog>
  );
}

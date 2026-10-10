import { useState } from "react";
import { apiFetch } from "../../lib/api.js";
import {
  Badge,
  Dialog,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Notice,
  PageHead,
  day,
  useApi,
} from "../../components/super/kit.jsx";
import "../../owner.css";

// Department manager: instructions from the Supermanager. Hand a task to a
// worker and post progress updates.
export default function MyTasks() {
  const { data, error, loading, reload } = useApi("/api/tasks/mine", ["tasks"]);
  const [open, setOpen] = useState(null);
  const [msg, setMsg] = useState("");
  const [show, setShow] = useState("open");

  if (loading && !data) return <Loading />;
  const tasks = (data?.tasks || []).filter(
    (t) =>
      show === "all" ||
      (show === "open" ? t.status !== "completed" : t.status === "completed"),
  );
  return (
    <div className="module sm-page">
      <PageHead
        title="My tasks"
        sub={
          data
            ? `Instructions for ${data.department_label} from the Supermanager.`
            : ""
        }
      />
      <Notice onClose={() => setMsg("")}>{msg}</Notice>
      <ErrorBox error={error} onRetry={reload} />
      <section className="panel">
        <div className="sm-tabs" role="tablist">
          {[
            ["open", "To do"],
            ["done", "Completed"],
            ["all", "All"],
          ].map(([k, l]) => (
            <button
              key={k}
              role="tab"
              aria-selected={show === k}
              className={show === k ? "is-active" : ""}
              onClick={() => setShow(k)}
            >
              {l}
            </button>
          ))}
        </div>
        {tasks.length === 0 ? (
          <Empty>
            {show === "open"
              ? "Nothing to do — no open instructions."
              : "No tasks here."}
          </Empty>
        ) : (
          <ul className="sm-tasklist">
            {tasks.map((t) => (
              <li key={t.id} className={`is-${t.shown_status}`}>
                <div>
                  <strong>{t.title}</strong>
                  {t.details && <p className="muted">{t.details}</p>}
                  <small className="muted">
                    {t.order_no ? `${t.order_no} · ` : ""}Due {day(t.deadline)}
                    {t.worker ? ` · Worker: ${t.worker.name}` : ""}
                  </small>
                </div>
                <div className="sm-task-side">
                  <Badge value={t.priority} />
                  <Badge value={t.shown_status} />
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => setOpen(t)}
                  >
                    Update
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
      {open && (
        <ProgressForm
          task={open}
          workers={data?.workers || []}
          onClose={() => setOpen(null)}
          onSaved={(newStatus) => {
            setOpen(null);
            setMsg("Update sent to the Supermanager.");
            // Jump to the tab that now shows the task, so it never looks like
            // the update "disappeared" (a completed task leaves the To-do tab).
            if (newStatus === "completed" && show === "open") setShow("done");
            reload();
          }}
        />
      )}
    </div>
  );
}

function ProgressForm({ task, workers, onClose, onSaved }) {
  const [status, setStatus] = useState(
    task.status === "pending" ? "in_progress" : task.status,
  );
  const [note, setNote] = useState("");
  const [worker, setWorker] = useState(task.worker?.id || "");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      await apiFetch(`/api/tasks/${task.id}/progress`, {
        method: "POST",
        body: {
          status,
          note: note.trim() || null,
          worker_employee_id: worker ? Number(worker) : null,
        },
      });
      onSaved(status);
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title={task.title} onClose={onClose}>
      <ErrorBox error={err} />
      <form className="form-grid sm-form" onSubmit={submit} noValidate>
        <Field label="Status">
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="pending">Pending</option>
            <option value="in_progress">In progress</option>
            <option value="completed">Completed</option>
          </select>
        </Field>
        <Field label="Worker on it">
          <select value={worker} onChange={(e) => setWorker(e.target.value)}>
            <option value="">Not assigned</option>
            {workers.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Progress note" wide>
          <textarea
            rows={3}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="What was done, what is left, any problem"
          />
        </Field>
        <div className="sm-row-end sm-wide">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={onClose}
          >
            Cancel
          </button>
          <button className="btn btn-primary btn-sm" disabled={busy}>
            {busy ? "Sending…" : "Send update"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

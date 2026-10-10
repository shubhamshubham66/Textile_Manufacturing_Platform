// Worker: Attendance (check-in/out), Overtime, Task History, Notifications and
// My Profile. All scoped to the logged-in worker.
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
// Attendance.
// --------------------------------------------------------------------------- //
export function WorkerAttendance() {
  const { data, error, loading, reload } = useApi("/api/worker/attendance", [
    "wages",
  ]);
  const [shift, setShift] = useState("morning");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;

  async function checkIn() {
    setBusy(true);
    setMsg("");
    try {
      await apiFetch("/api/worker/attendance/check-in", {
        method: "POST",
        body: { shift },
      });
      setMsg("Checked in. Your manager will verify today's attendance.");
      reload();
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function checkOut() {
    setBusy(true);
    setMsg("");
    try {
      await apiFetch("/api/worker/attendance/check-out", { method: "POST" });
      setMsg("Checked out.");
      reload();
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="module sm-page">
      <PageHead
        title="Attendance"
        sub="Check in when you start and check out when you leave. Your manager verifies it before wages are processed."
      />
      <Notice onClose={() => setMsg("")}>{msg}</Notice>

      <section className="panel">
        <h3>Today</h3>
        {data.today ? (
          <div className="sm-stats sm-stats-4">
            <Stat
              label="Status"
              value={data.today.status}
              tone={data.today.status === "present" ? "green" : "amber"}
            />
            <Stat
              label="Checked in"
              value={data.today.check_in ? when(data.today.check_in) : "—"}
            />
            <Stat
              label="Checked out"
              value={data.today.check_out ? when(data.today.check_out) : "—"}
            />
            <Stat
              label="Verified"
              value={data.today.verified ? "Yes" : "Pending"}
              tone={data.today.verified ? "green" : "amber"}
            />
          </div>
        ) : (
          <p className="muted">You have not checked in today.</p>
        )}
        <div className="sm-row-end" style={{ gap: 12, marginTop: 12 }}>
          {data.can_check_in && (
            <>
              <select
                value={shift}
                onChange={(e) => setShift(e.target.value)}
                className="sm-select"
              >
                <option value="morning">Morning</option>
                <option value="evening">Evening</option>
                <option value="night">Night</option>
              </select>
              <button
                className="btn btn-primary"
                disabled={busy}
                onClick={checkIn}
              >
                Check in
              </button>
            </>
          )}
          {data.can_check_out && (
            <button
              className="btn btn-primary"
              disabled={busy}
              onClick={checkOut}
            >
              Check out
            </button>
          )}
        </div>
      </section>

      <section className="panel">
        <h3>Recent attendance</h3>
        {data.rows.length === 0 ? (
          <Empty>No attendance records yet.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Shift</th>
                  <th>Status</th>
                  <th className="num">Hours</th>
                  <th>In / Out</th>
                  <th>Verified</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((a) => (
                  <tr key={a.id}>
                    <td>{a.work_date}</td>
                    <td>{a.shift}</td>
                    <td>
                      <Badge
                        value={
                          a.status === "present"
                            ? "present"
                            : a.status === "half_day"
                              ? "half_day"
                              : "absent"
                        }
                      />
                    </td>
                    <td className="num">{n(a.hours_worked)}</td>
                    <td>
                      {a.check_in ? when(a.check_in) : "—"} /{" "}
                      {a.check_out ? when(a.check_out) : "—"}
                    </td>
                    <td>
                      {a.verified ? (
                        <Badge value="ok" label="Verified" />
                      ) : (
                        <Badge value="waiting" label="Pending" />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Overtime.
// --------------------------------------------------------------------------- //
export function WorkerOvertime() {
  const { data, error, loading, reload } = useApi("/api/worker/overtime", [
    "wages",
  ]);
  const [form, setForm] = useState(false);
  const [msg, setMsg] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead title="Overtime records" sub={data.note}>
        <button
          className="btn btn-primary btn-sm"
          onClick={() => setForm(true)}
        >
          ＋ Submit overtime
        </button>
      </PageHead>
      <Notice onClose={() => setMsg("")}>{msg}</Notice>
      <div className="sm-stats sm-stats-4">
        <Stat
          label="Total overtime"
          value={`${n(data.total_hours)} h`}
          tone={data.total_hours ? "amber" : undefined}
        />
        <Stat label="Records" value={data.rows.length} />
      </div>
      {data.rows.length === 0 ? (
        <Empty>No overtime submitted yet.</Empty>
      ) : (
        <section className="panel">
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th className="num">Overtime</th>
                  <th>Verified</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r, i) => (
                  <tr key={i}>
                    <td>{r.work_date}</td>
                    <td className="num">{n(r.overtime_hours)} h</td>
                    <td>
                      {r.verified ? (
                        <Badge value="ok" label="Verified" />
                      ) : (
                        <Badge value="waiting" label="Pending" />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {form && (
        <OvertimeDialog
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

function OvertimeDialog({ onClose, onDone }) {
  const [hours, setHours] = useState("");
  const [workDate, setWorkDate] = useState("");
  const [reason, setReason] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function go() {
    if (!hours || Number(hours) <= 0)
      return setErr("Enter the overtime hours.");
    if (reason.trim().length < 3) return setErr("Add a reason.");
    setBusy(true);
    setErr("");
    try {
      await apiFetch("/api/worker/overtime", {
        method: "POST",
        body: {
          hours: Number(hours),
          work_date: workDate || null,
          reason: reason.trim(),
        },
      });
      onDone("Overtime submitted for your manager to verify.");
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title="Submit overtime" onClose={onClose}>
      <ErrorBox error={err} />
      <Field label="Hours">
        <input
          type="number"
          min="0"
          step="0.5"
          value={hours}
          onChange={(e) => setHours(e.target.value)}
          autoFocus
        />
      </Field>
      <Field label="Date (optional, defaults to today)">
        <input
          type="date"
          value={workDate}
          onChange={(e) => setWorkDate(e.target.value)}
        />
      </Field>
      <Field label="Reason" wide>
        <textarea
          rows={2}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </Field>
      <div className="sm-row-end">
        <button className="btn btn-ghost btn-sm" onClick={onClose}>
          Cancel
        </button>
        <button className="btn btn-primary btn-sm" onClick={go} disabled={busy}>
          {busy ? "Saving…" : "Submit"}
        </button>
      </div>
    </Dialog>
  );
}

// --------------------------------------------------------------------------- //
// Task History.
// --------------------------------------------------------------------------- //
export function WorkerHistory() {
  const { data, error, loading, reload } = useApi("/api/worker/history", [
    "tasks",
  ]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead
        title="Task history"
        sub="Every task you have worked on and its progress updates."
      />
      {data.tasks.length === 0 ? (
        <Empty>No task history yet.</Empty>
      ) : (
        data.tasks.map((t) => (
          <section className="panel" key={t.id}>
            <div className="sm-panel-head">
              <h3>{t.title}</h3>
              <Badge value={t.shown_status} />
            </div>
            <p className="muted sm-small">
              {t.order_no ? `${t.order_no} · ` : ""}
              {t.deadline ? `due ${t.deadline}` : "no deadline"}
            </p>
            {t.updates.length === 0 ? (
              <Empty>No updates recorded.</Empty>
            ) : (
              <ul className="sm-exceptions is-plain">
                {t.updates.map((u, i) => (
                  <li key={i}>
                    <Badge value={u.status} /> {u.note || ""}
                    <small className="sm-sub">{when(u.at)}</small>
                  </li>
                ))}
              </ul>
            )}
          </section>
        ))
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Notifications.
// --------------------------------------------------------------------------- //
export function WorkerNotifications() {
  const { data, error, loading, reload } = useApi("/api/worker/notifications", [
    "notifications",
    "tasks",
  ]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;

  async function markRead(id) {
    try {
      await apiFetch(`/api/worker/notifications/${id}/read`, {
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
        sub={`${data.unread} unread · new tasks and updates from your manager.`}
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
// My Profile (read-only).
// --------------------------------------------------------------------------- //
export function WorkerProfile() {
  const { data, error, loading, reload } = useApi("/api/worker/profile", [
    "wages",
  ]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead title="My profile" sub={data.note} />
      <section className="panel">
        <dl className="sm-mini">
          <div>
            <dt>Name</dt>
            <dd>{data.name}</dd>
          </div>
          <div>
            <dt>Work on floor</dt>
            <dd>{data.role_on_floor || "—"}</dd>
          </div>
          <div>
            <dt>Department</dt>
            <dd>{data.department_label}</dd>
          </div>
          <div>
            <dt>Reports to</dt>
            <dd>{data.manager?.name || "—"}</dd>
          </div>
          <div>
            <dt>Phone</dt>
            <dd>{data.phone || "—"}</dd>
          </div>
          <div>
            <dt>Login</dt>
            <dd>{data.login_email || data.login_id || "—"}</dd>
          </div>
          <div>
            <dt>Daily wage</dt>
            <dd>{rupee(data.daily_wage)}</dd>
          </div>
        </dl>
      </section>
      <section className="panel">
        <h3>Attendance this month</h3>
        <div className="sm-stats sm-stats-4">
          <Stat
            label="Present"
            value={data.attendance_this_month.present}
            tone="green"
          />
          <Stat
            label="Half days"
            value={data.attendance_this_month.half_day}
            tone={data.attendance_this_month.half_day ? "amber" : undefined}
          />
          <Stat
            label="Absent"
            value={data.attendance_this_month.absent}
            tone={data.attendance_this_month.absent ? "red" : undefined}
          />
        </div>
      </section>
    </div>
  );
}

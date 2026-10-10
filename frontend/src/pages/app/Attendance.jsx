import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";
import { isLiveRefresh, useLive } from "../../live/LiveContext.jsx";

// Attendance (accountant): mark present/absent/half_day + shift per employee/day.
export default function Attendance() {
  const [employees, setEmployees] = useState([]);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  async function load() {
    if (!isLiveRefresh()) setLoading(true);
    setError("");
    try {
      const [emps, att] = await Promise.all([
        apiFetch("/api/wages/employees"),
        apiFetch("/api/attendance"),
      ]);
      setEmployees(emps);
      setRows(att);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  // Reload quietly when something this page shows changes elsewhere.
  useLive(["wages"], load);

  async function mark(employee_id, status, shift = "morning") {
    setMsg("");
    try {
      await apiFetch("/api/attendance", {
        method: "POST",
        body: {
          employee_id,
          status,
          shift,
          hours_worked:
            status === "present" ? 8 : status === "half_day" ? 4 : 0,
        },
      });
      await load();
    } catch (err) {
      setMsg(err.message);
    }
  }

  return (
    <div className="module">
      <h2>Attendance</h2>
      {error && <div className="form-error">{error}</div>}
      {msg && <div className="form-error">{msg}</div>}

      <section className="panel">
        <h3>Mark today's attendance</h3>
        {loading ? (
          <p className="muted">Loading…</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Employee</th>
                <th>Role</th>
                <th>Today</th>
                <th>Mark</th>
              </tr>
            </thead>
            <tbody>
              {employees.map((e) => (
                <tr key={e.id}>
                  <td>{e.name}</td>
                  <td>{e.role_on_floor}</td>
                  <td>
                    {e.today_status ? (
                      <span
                        className={`status status-${e.today_status === "present" ? "pass" : e.today_status === "absent" ? "reject" : "raised"}`}
                      >
                        {e.today_status}
                      </span>
                    ) : (
                      <span className="muted">not marked</span>
                    )}
                  </td>
                  <td className="row-actions">
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => mark(e.id, "present")}
                    >
                      Present
                    </button>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => mark(e.id, "half_day")}
                    >
                      Half day
                    </button>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => mark(e.id, "absent")}
                    >
                      Absent
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="panel">
        <h3>Recent attendance</h3>
        {rows.length === 0 ? (
          <p className="muted">No attendance records.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Employee</th>
                <th>Shift</th>
                <th>Status</th>
                <th>Hours</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 40).map((a) => (
                <tr key={a.id}>
                  <td>{a.work_date}</td>
                  <td>{a.employee}</td>
                  <td>{a.shift}</td>
                  <td>{a.status}</td>
                  <td>{a.hours_worked}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

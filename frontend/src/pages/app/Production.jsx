import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";
import { isLiveRefresh, useLive } from "../../live/LiveContext.jsx";

const SHIFTS = ["morning", "evening", "night"];

// Production page (floor supervisor): idle-loss dashboard card (our USP),
// log output per machine/shift, and today's output per machine.
export default function Production() {
  const [machines, setMachines] = useState([]);
  const [orders, setOrders] = useState([]);
  const [today, setToday] = useState([]);
  const [idle, setIdle] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [form, setForm] = useState({
    machine_id: "",
    order_id: "",
    output_meters: "",
    shift: "morning",
  });
  const [formErr, setFormErr] = useState({});
  const [saveMsg, setSaveMsg] = useState("");
  const [saving, setSaving] = useState(false);

  async function load() {
    if (!isLiveRefresh()) setLoading(true);
    setError("");
    try {
      const [m, o, t, il] = await Promise.all([
        apiFetch("/api/production/machines"),
        apiFetch("/api/production/orders").catch(() => []),
        apiFetch("/api/production/output/today"),
        apiFetch("/api/production/idle-loss"),
      ]);
      setMachines(m);
      setOrders(o);
      setToday(t);
      setIdle(il);
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
  useLive(["machines", "production", "orders"], load);

  function validate() {
    const e = {};
    if (!form.machine_id) e.machine_id = "Select a machine.";
    if (!form.order_id) e.order_id = "Select an order.";
    const q = Number(form.output_meters);
    if (!form.output_meters || isNaN(q) || q <= 0)
      e.output_meters = "Output must be greater than 0.";
    setFormErr(e);
    return Object.keys(e).length === 0;
  }

  async function onLog(ev) {
    ev.preventDefault();
    setSaveMsg("");
    if (!validate()) return;
    setSaving(true);
    try {
      const res = await apiFetch("/api/production/output", {
        method: "POST",
        body: {
          machine_id: Number(form.machine_id),
          order_id: Number(form.order_id),
          output_meters: Number(form.output_meters),
          shift: form.shift,
        },
      });
      setSaveMsg(
        `Logged ${res.logged_meters} m to ${res.order_no}. Order progress now ${res.order_progress_percent}%.`,
      );
      setForm({ ...form, output_meters: "" });
      await load();
    } catch (err) {
      setSaveMsg(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="module">
      <h2>Production</h2>
      {error && <div className="form-error">{error}</div>}

      {/* Idle-loss dashboard card (USP) */}
      <section className="panel idle-card">
        <div className="toolbar">
          <h3>⏱️ Idle machine loss</h3>
          <button className="btn btn-ghost btn-sm" onClick={load}>
            Refresh
          </button>
        </div>
        {idle ? (
          <>
            <div className="idle-headline">
              <div className="idle-total">
                <span className="idle-total-value">
                  ₹{idle.total_loss_rupees.toLocaleString("en-IN")}
                </span>
                <span className="muted">
                  lost · {idle.total_lost_hours} idle/breakdown hours
                </span>
              </div>
            </div>

            <div className="idle-cols">
              <div>
                <h4>By machine</h4>
                {idle.per_machine.length === 0 ? (
                  <p className="muted">No idle or breakdown time. 🎉</p>
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Machine</th>
                        <th>Status</th>
                        <th>Idle h</th>
                        <th>Break h</th>
                        <th>₹/hr</th>
                        <th>Loss ₹</th>
                      </tr>
                    </thead>
                    <tbody>
                      {idle.per_machine.map((r) => (
                        <tr key={r.machine_id}>
                          <td>{r.machine_name}</td>
                          <td>
                            <span
                              className={`status status-${r.current_status}`}
                            >
                              {r.current_status}
                            </span>
                          </td>
                          <td>{r.idle_hours}</td>
                          <td>{r.breakdown_hours}</td>
                          <td>₹{r.hourly_cost}</td>
                          <td>
                            <strong>
                              ₹{r.loss_rupees.toLocaleString("en-IN")}
                            </strong>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
              <div>
                <h4>Top reasons</h4>
                {idle.top_reasons.length === 0 ? (
                  <p className="muted">—</p>
                ) : (
                  <ul className="reason-list">
                    {idle.top_reasons.map((r) => (
                      <li key={r.reason}>
                        <span>{r.reason}</span>
                        <strong>{r.hours} h</strong>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </>
        ) : (
          <p className="muted">Loading idle loss…</p>
        )}
      </section>

      {/* Log output */}
      <section className="panel">
        <h3>Log output</h3>
        {saveMsg && <div className="callout callout-ok">{saveMsg}</div>}
        <form className="form-grid" onSubmit={onLog} noValidate>
          <label className="field">
            <span>Machine</span>
            <select
              value={form.machine_id}
              onChange={(e) => setForm({ ...form, machine_id: e.target.value })}
              className={formErr.machine_id ? "invalid" : ""}
            >
              <option value="">Select machine…</option>
              {machines.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.type})
                </option>
              ))}
            </select>
            {formErr.machine_id && (
              <small className="field-error">{formErr.machine_id}</small>
            )}
          </label>

          <label className="field">
            <span>Order</span>
            <select
              value={form.order_id}
              onChange={(e) => setForm({ ...form, order_id: e.target.value })}
              className={formErr.order_id ? "invalid" : ""}
            >
              <option value="">Select order…</option>
              {orders.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.order_no} — {o.fabric_type}
                </option>
              ))}
            </select>
            {formErr.order_id && (
              <small className="field-error">{formErr.order_id}</small>
            )}
          </label>

          <label className="field">
            <span>Output (metres)</span>
            <input
              type="number"
              min="0"
              step="any"
              value={form.output_meters}
              onChange={(e) =>
                setForm({ ...form, output_meters: e.target.value })
              }
              className={formErr.output_meters ? "invalid" : ""}
            />
            {formErr.output_meters && (
              <small className="field-error">{formErr.output_meters}</small>
            )}
          </label>

          <label className="field">
            <span>Shift</span>
            <select
              value={form.shift}
              onChange={(e) => setForm({ ...form, shift: e.target.value })}
            >
              {SHIFTS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>

          <div className="form-actions">
            <button className="btn btn-primary" disabled={saving}>
              {saving ? "Logging…" : "Log output"}
            </button>
          </div>
        </form>
      </section>

      {/* Today's output */}
      <section className="panel">
        <h3>Today's output per machine</h3>
        {loading ? (
          <p className="muted">Loading…</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Machine</th>
                <th>Output today (m)</th>
              </tr>
            </thead>
            <tbody>
              {today.map((r) => (
                <tr key={r.machine_id}>
                  <td>{r.machine_name}</td>
                  <td>{r.output_meters_today}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

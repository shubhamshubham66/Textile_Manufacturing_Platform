import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";
import { isLiveRefresh, useLive } from "../../live/LiveContext.jsx";

const STATUS_LABELS = {
  running: "Running",
  idle: "Idle",
  breakdown: "Breakdown",
};
const STAGES = ["spinning", "weaving", "dyeing"];

// Machines page (floor supervisor): current status, assigned order + progress,
// update status (with required reason for idle/breakdown), assign order,
// and admin hourly-cost setting.
export default function Machines() {
  const [machines, setMachines] = useState([]);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // modal-ish inline editors keyed by machine id
  const [statusEdit, setStatusEdit] = useState(null); // {id, status, reason}
  const [assignEdit, setAssignEdit] = useState(null); // {id, order_id, stage}
  const [costEdit, setCostEdit] = useState(null); // {id, hourly_cost}
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function load() {
    if (!isLiveRefresh()) setLoading(true);
    setError("");
    try {
      const [m, o] = await Promise.all([
        apiFetch("/api/production/machines"),
        apiFetch("/api/production/orders").catch(() => []),
      ]);
      setMachines(m);
      setOrders(o);
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
  useLive(["machines", "production"], load);

  async function submitStatus() {
    if (
      (statusEdit.status === "idle" || statusEdit.status === "breakdown") &&
      !statusEdit.reason?.trim()
    ) {
      setMsg("A reason is required for Idle or Breakdown.");
      return;
    }
    setBusy(true);
    setMsg("");
    try {
      await apiFetch(`/api/production/machines/${statusEdit.id}/status`, {
        method: "POST",
        body: { status: statusEdit.status, reason: statusEdit.reason || null },
      });
      setStatusEdit(null);
      await load();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function submitAssign() {
    if (!assignEdit.order_id) {
      setMsg("Select an order to assign.");
      return;
    }
    setBusy(true);
    setMsg("");
    try {
      await apiFetch(`/api/production/machines/${assignEdit.id}/assign`, {
        method: "POST",
        body: {
          order_id: Number(assignEdit.order_id),
          stage: assignEdit.stage,
        },
      });
      setAssignEdit(null);
      await load();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function submitCost() {
    const val = Number(costEdit.hourly_cost);
    if (isNaN(val) || val < 0) {
      setMsg("Hourly cost must be 0 or more.");
      return;
    }
    setBusy(true);
    setMsg("");
    try {
      await apiFetch(`/api/production/machines/${costEdit.id}/hourly-cost`, {
        method: "PATCH",
        body: { hourly_cost: val },
      });
      setCostEdit(null);
      await load();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="module">
      <h2>Machines</h2>
      {msg && <div className="form-error">{msg}</div>}
      {error && <div className="form-error">{error}</div>}

      <section className="panel">
        <div className="toolbar">
          <h3>Floor status</h3>
          <button className="btn btn-ghost btn-sm" onClick={load}>
            Refresh
          </button>
        </div>

        {loading ? (
          <p className="muted">Loading machines…</p>
        ) : machines.length === 0 ? (
          <p className="muted">No machines.</p>
        ) : (
          <div className="machine-grid">
            {machines.map((m) => (
              <div key={m.id} className={`machine-card mc-${m.current_status}`}>
                <div className="mc-head">
                  <strong>{m.name}</strong>
                  <span className={`status status-${m.current_status}`}>
                    {STATUS_LABELS[m.current_status] || m.current_status}
                  </span>
                </div>
                <div className="muted mc-type">{m.type}</div>

                <div className="mc-row">
                  Order:{" "}
                  {m.current_order_no ? (
                    <strong>
                      {m.current_order_no} ({m.current_stage})
                    </strong>
                  ) : (
                    <span className="muted">unassigned</span>
                  )}
                </div>

                {m.current_order_no && (
                  <div className="progress">
                    <div
                      className="progress-bar"
                      style={{ width: `${m.progress_percent}%` }}
                    />
                    <span className="progress-label">
                      {m.progress_percent}%
                    </span>
                  </div>
                )}

                <div className="muted mc-cost">₹{m.hourly_cost}/hr</div>

                <div className="mc-actions">
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() =>
                      setStatusEdit({
                        id: m.id,
                        status: m.current_status,
                        reason: "",
                      })
                    }
                  >
                    Update status
                  </button>
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() =>
                      setAssignEdit({
                        id: m.id,
                        order_id: "",
                        stage: m.type,
                      })
                    }
                  >
                    Assign
                  </button>
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() =>
                      setCostEdit({ id: m.id, hourly_cost: m.hourly_cost })
                    }
                  >
                    Hourly cost
                  </button>
                </div>

                {/* Inline editors */}
                {statusEdit?.id === m.id && (
                  <div className="inline-edit">
                    <select
                      value={statusEdit.status}
                      onChange={(e) =>
                        setStatusEdit({ ...statusEdit, status: e.target.value })
                      }
                    >
                      <option value="running">Running</option>
                      <option value="idle">Idle</option>
                      <option value="breakdown">Breakdown</option>
                    </select>
                    {(statusEdit.status === "idle" ||
                      statusEdit.status === "breakdown") && (
                      <input
                        placeholder="Reason (required)"
                        value={statusEdit.reason}
                        onChange={(e) =>
                          setStatusEdit({
                            ...statusEdit,
                            reason: e.target.value,
                          })
                        }
                      />
                    )}
                    <div className="inline-actions">
                      <button
                        className="btn btn-primary btn-sm"
                        disabled={busy}
                        onClick={submitStatus}
                      >
                        Save
                      </button>
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => setStatusEdit(null)}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

                {assignEdit?.id === m.id && (
                  <div className="inline-edit">
                    <select
                      value={assignEdit.order_id}
                      onChange={(e) =>
                        setAssignEdit({
                          ...assignEdit,
                          order_id: e.target.value,
                        })
                      }
                    >
                      <option value="">Select order…</option>
                      {orders.map((o) => (
                        <option key={o.id} value={o.id}>
                          {o.order_no} — {o.fabric_type} ({o.colour})
                        </option>
                      ))}
                    </select>
                    <select
                      value={assignEdit.stage}
                      onChange={(e) =>
                        setAssignEdit({ ...assignEdit, stage: e.target.value })
                      }
                    >
                      {STAGES.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                    <div className="inline-actions">
                      <button
                        className="btn btn-primary btn-sm"
                        disabled={busy}
                        onClick={submitAssign}
                      >
                        Assign
                      </button>
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => setAssignEdit(null)}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

                {costEdit?.id === m.id && (
                  <div className="inline-edit">
                    <input
                      type="number"
                      min="0"
                      step="any"
                      value={costEdit.hourly_cost}
                      onChange={(e) =>
                        setCostEdit({
                          ...costEdit,
                          hourly_cost: e.target.value,
                        })
                      }
                    />
                    <div className="inline-actions">
                      <button
                        className="btn btn-primary btn-sm"
                        disabled={busy}
                        onClick={submitCost}
                      >
                        Save ₹/hr
                      </button>
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => setCostEdit(null)}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

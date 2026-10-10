import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";
import { isLiveRefresh, useLive } from "../../live/LiveContext.jsx";

// Buyer: My orders (own only) + Track order (stage stepper, progress, ETA).
export default function MyOrders() {
  const [orders, setOrders] = useState([]);
  const [tracked, setTracked] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    if (!isLiveRefresh()) setLoading(true);
    setError("");
    try {
      setOrders(await apiFetch("/api/buyer/orders"));
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
  useLive(["orders", "quality", "production", "payments"], load);

  async function track(id) {
    setError("");
    try {
      setTracked(await apiFetch(`/api/buyer/orders/${id}`));
    } catch (err) {
      setError(err.message);
    }
  }

  function askAI() {
    // Open the floating chat bubble (mini developer's widget).
    window.dispatchEvent(new Event("etm:open-chat"));
  }

  return (
    <div className="module">
      <div className="toolbar">
        <h2>My orders</h2>
        <button className="btn btn-ghost btn-sm" onClick={askAI}>
          💬 Ask AI
        </button>
      </div>
      {error && <div className="form-error">{error}</div>}

      {/* Track view */}
      {tracked && (
        <section className="panel">
          <div className="toolbar">
            <h3>
              Track {tracked.order_no} — {tracked.fabric_type} ({tracked.colour}
              )
            </h3>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setTracked(null)}
            >
              Close
            </button>
          </div>

          <div className="stepper">
            {tracked.stage_flow.map((s, i) => (
              <div
                key={s}
                className={`step-dot ${
                  i < tracked.stage_index
                    ? "done"
                    : i === tracked.stage_index
                      ? "current"
                      : ""
                }`}
              >
                <span className="step-circle">{i + 1}</span>
                <span className="step-name">{s}</span>
              </div>
            ))}
          </div>

          <div className="progress" style={{ marginTop: "1rem" }}>
            <div
              className="progress-bar"
              style={{ width: `${tracked.progress_percent}%` }}
            />
            <span className="progress-label">{tracked.progress_percent}%</span>
          </div>
          <p className="muted">
            Current stage: <strong>{tracked.stage}</strong> · Expected delivery:{" "}
            <strong>{tracked.expected_delivery || "TBD"}</strong>
          </p>
        </section>
      )}

      <section className="panel">
        <h3>Your orders</h3>
        {loading ? (
          <p className="muted">Loading…</p>
        ) : orders.length === 0 ? (
          <p className="muted">You have no orders yet.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Order</th>
                <th>Fabric</th>
                <th>Colour</th>
                <th>Qty (m)</th>
                <th>Stage</th>
                <th>Progress</th>
                <th>Expected</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td>{o.order_no}</td>
                  <td>{o.fabric_type}</td>
                  <td>{o.colour}</td>
                  <td>{o.quantity_meters}</td>
                  <td>
                    <span className="status status-in_production">
                      {o.stage}
                    </span>
                  </td>
                  <td>{o.progress_percent}%</td>
                  <td>{o.expected_delivery || "—"}</td>
                  <td>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => track(o.id)}
                    >
                      Track
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

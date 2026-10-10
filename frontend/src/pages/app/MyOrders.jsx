import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";
import { isLiveRefresh, useLive } from "../../live/LiveContext.jsx";

// Buyer: My orders (own only) + Track order (stage stepper, progress, ETA).
export default function MyOrders() {
  const [orders, setOrders] = useState([]);
  const [tracked, setTracked] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [request, setRequest] = useState(null); // null | {} (new) | order (reply)
  const [notice, setNotice] = useState("");

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
        <div className="row-actions">
          <button className="btn btn-primary btn-sm" onClick={() => setRequest({})}>
            ＋ Request an order
          </button>
          <button className="btn btn-ghost btn-sm" onClick={askAI}>
            💬 Ask AI
          </button>
        </div>
      </div>
      {error && <div className="form-error">{error}</div>}
      {notice && (
        <div className="callout callout-ok">
          {notice}{" "}
          <button className="link-btn" onClick={() => setNotice("")}>
            dismiss
          </button>
        </div>
      )}
      {request && (
        <OrderRequest
          order={request.id ? request : null}
          onClose={() => setRequest(null)}
          onSaved={(r) => {
            setRequest(null);
            setNotice(`${r.order_no} sent. The mill will review it and set the price.`);
            load();
          }}
        />
      )}

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
                    {o.review_label ? (
                      <span className={`status ${o.status === "rejected" ? "status-reject" : "status-draft"}`}>
                        {o.review_label}
                      </span>
                    ) : (
                      <span className="status status-in_production">
                        {o.stage}
                      </span>
                    )}
                    {o.review_note && (
                      <small className="buyer-review-note">
                        {o.status === "rejected" ? "Reason: " : "Question: "}
                        {o.review_note}
                      </small>
                    )}
                  </td>
                  <td>{o.progress_percent}%</td>
                  <td>{o.expected_delivery || "—"}</td>
                  <td>
                    {o.status === "clarification" ? (
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => setRequest(o)}
                      >
                        Reply
                      </button>
                    ) : o.review_label ? null : (
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => track(o.id)}
                      >
                        Track
                      </button>
                    )}
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

// New order request (or a reply to the mill's question). The mill sets the
// price and confirms; until then the order shows as "Under review".
function OrderRequest({ order, onClose, onSaved }) {
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  const [f, setF] = useState({
    fabric_type: order?.fabric_type || "",
    colour: order?.colour || "",
    quantity_meters: order?.quantity_meters || "",
    deadline: order?.expected_delivery || "",
    note: order?.buyer_note || "",
  });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    if (!f.fabric_type.trim() || !f.colour.trim()) return setErr("Enter the fabric and the colour.");
    if (!(Number(f.quantity_meters) > 0)) return setErr("Enter how many metres you need.");
    if (!f.deadline || f.deadline < tomorrow) return setErr("Choose a delivery date after today.");
    setBusy(true);
    setErr("");
    const body = {
      fabric_type: f.fabric_type.trim(),
      colour: f.colour.trim(),
      quantity_meters: Number(f.quantity_meters),
      deadline: f.deadline,
      note: f.note.trim() || null,
    };
    try {
      const r = order
        ? await apiFetch(`/api/buyer/orders/${order.id}`, { method: "PUT", body })
        : await apiFetch("/api/buyer/orders", { method: "POST", body });
      onSaved(r);
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <h3>{order ? `Reply about ${order.order_no}` : "Request an order"}</h3>
      {order?.review_note && <p className="callout callout-warn">The mill asks: {order.review_note}</p>}
      {err && <div className="form-error">{err}</div>}
      <form className="form-grid" onSubmit={submit} noValidate>
        <label className="field">
          <span>Fabric</span>
          <input value={f.fabric_type} onChange={set("fabric_type")} placeholder="Cotton Shirting" />
        </label>
        <label className="field">
          <span>Colour</span>
          <input value={f.colour} onChange={set("colour")} placeholder="White" />
        </label>
        <label className="field">
          <span>Quantity (metres)</span>
          <input type="number" min="1" value={f.quantity_meters} onChange={set("quantity_meters")} />
        </label>
        <label className="field">
          <span>Needed by</span>
          <input type="date" min={tomorrow} value={f.deadline} onChange={set("deadline")} />
        </label>
        <label className="field" style={{ gridColumn: "1 / -1" }}>
          <span>Note for the mill (optional)</span>
          <input value={f.note} onChange={set("note")} placeholder="GSM, finish, packing…" />
        </label>
        <div className="row-actions">
          <button className="btn btn-primary btn-sm" disabled={busy}>
            {busy ? "Sending…" : order ? "Send reply" : "Send request"}
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </section>
  );
}

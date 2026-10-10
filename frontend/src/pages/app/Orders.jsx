import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";

const STATUSES = [
  "draft",
  "confirmed",
  "in_production",
  "in_quality",
  "ready_to_ship",
  "dispatched",
  "closed",
];

const EMPTY_FORM = {
  buyer_id: "",
  fabric_type: "",
  colour: "",
  quantity_meters: "",
  unit_price: "",
  deadline: "",
};

// Orders module (owner): new order form + check yarn + confirm + list.
export default function Orders() {
  const [orders, setOrders] = useState([]);
  const [buyers, setBuyers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");

  const [form, setForm] = useState(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);

  const [yarnResult, setYarnResult] = useState(null); // {order, ...checkYarn}
  const [busyId, setBusyId] = useState(null);

  async function loadOrders() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.set("status", statusFilter);
      if (search.trim()) params.set("q", search.trim());
      const qs = params.toString();
      const data = await apiFetch(`/api/orders${qs ? `?${qs}` : ""}`);
      setOrders(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    apiFetch("/api/orders/_meta/buyers")
      .then(setBuyers)
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    loadOrders();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  function validate() {
    const e = {};
    if (!form.buyer_id) e.buyer_id = "Select a buyer.";
    if (!form.fabric_type.trim()) e.fabric_type = "Fabric type is required.";
    if (!form.colour.trim()) e.colour = "Colour is required.";
    const qty = Number(form.quantity_meters);
    if (!form.quantity_meters || isNaN(qty) || qty <= 0)
      e.quantity_meters = "Quantity must be greater than 0.";
    const rate = Number(form.unit_price);
    if (form.unit_price === "" || isNaN(rate) || rate < 0)
      e.unit_price = "Rate must be 0 or more.";
    setFormErrors(e);
    return Object.keys(e).length === 0;
  }

  async function onCreate(ev) {
    ev.preventDefault();
    setFormError("");
    if (!validate()) return;
    setSaving(true);
    try {
      await apiFetch("/api/orders", {
        method: "POST",
        body: {
          buyer_id: Number(form.buyer_id),
          fabric_type: form.fabric_type.trim(),
          colour: form.colour.trim(),
          quantity_meters: Number(form.quantity_meters),
          unit_price: Number(form.unit_price),
          deadline: form.deadline || null,
        },
      });
      setForm(EMPTY_FORM);
      setFormErrors({});
      await loadOrders();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function onCheckYarn(order) {
    setBusyId(order.id);
    setYarnResult(null);
    try {
      const data = await apiFetch(`/api/orders/${order.id}/check-yarn`);
      setYarnResult({ ...data, order_no: order.order_no });
    } catch (err) {
      setYarnResult({ error: err.message, order_no: order.order_no });
    } finally {
      setBusyId(null);
    }
  }

  async function onConfirm(order) {
    setBusyId(order.id);
    try {
      await apiFetch(`/api/orders/${order.id}/confirm`, { method: "POST" });
      await loadOrders();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="module">
      <h2>Orders</h2>

      {/* New order form */}
      <section className="panel">
        <h3>New order</h3>
        {formError && <div className="form-error">{formError}</div>}
        <form className="form-grid" onSubmit={onCreate} noValidate>
          <label className="field">
            <span>Buyer</span>
            <select
              value={form.buyer_id}
              onChange={(e) => setForm({ ...form, buyer_id: e.target.value })}
              className={formErrors.buyer_id ? "invalid" : ""}
            >
              <option value="">Select buyer…</option>
              {buyers.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
            {formErrors.buyer_id && (
              <small className="field-error">{formErrors.buyer_id}</small>
            )}
          </label>

          <label className="field">
            <span>Fabric type</span>
            <input
              value={form.fabric_type}
              onChange={(e) =>
                setForm({ ...form, fabric_type: e.target.value })
              }
              className={formErrors.fabric_type ? "invalid" : ""}
              placeholder="Cotton Shirting"
            />
            {formErrors.fabric_type && (
              <small className="field-error">{formErrors.fabric_type}</small>
            )}
          </label>

          <label className="field">
            <span>Colour</span>
            <input
              value={form.colour}
              onChange={(e) => setForm({ ...form, colour: e.target.value })}
              className={formErrors.colour ? "invalid" : ""}
              placeholder="White"
            />
            {formErrors.colour && (
              <small className="field-error">{formErrors.colour}</small>
            )}
          </label>

          <label className="field">
            <span>Quantity (metres)</span>
            <input
              type="number"
              min="0"
              step="any"
              value={form.quantity_meters}
              onChange={(e) =>
                setForm({ ...form, quantity_meters: e.target.value })
              }
              className={formErrors.quantity_meters ? "invalid" : ""}
            />
            {formErrors.quantity_meters && (
              <small className="field-error">
                {formErrors.quantity_meters}
              </small>
            )}
          </label>

          <label className="field">
            <span>Rate (₹/metre)</span>
            <input
              type="number"
              min="0"
              step="any"
              value={form.unit_price}
              onChange={(e) => setForm({ ...form, unit_price: e.target.value })}
              className={formErrors.unit_price ? "invalid" : ""}
            />
            {formErrors.unit_price && (
              <small className="field-error">{formErrors.unit_price}</small>
            )}
          </label>

          <label className="field">
            <span>Deadline</span>
            <input
              type="date"
              value={form.deadline}
              onChange={(e) => setForm({ ...form, deadline: e.target.value })}
            />
          </label>

          <div className="form-actions">
            <button className="btn btn-primary" disabled={saving}>
              {saving ? "Creating…" : "Create order"}
            </button>
          </div>
        </form>
      </section>

      {/* Yarn check result */}
      {yarnResult && (
        <div
          className={`callout ${yarnResult.enough ? "callout-ok" : "callout-warn"}`}
        >
          <strong>Yarn check — {yarnResult.order_no}:</strong>{" "}
          {yarnResult.error ? yarnResult.error : yarnResult.message}
          {!yarnResult.error && !yarnResult.enough && (
            <span>
              {" "}
              → Go to Yarn store › Raise purchase for ~
              {yarnResult.suggested_purchase_kg} kg.
            </span>
          )}
          <button className="link-btn" onClick={() => setYarnResult(null)}>
            dismiss
          </button>
        </div>
      )}

      {/* Filters + list */}
      <section className="panel">
        <div className="toolbar">
          <h3>Orders list</h3>
          <div className="toolbar-controls">
            <input
              placeholder="Search order / fabric / colour…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && loadOrders()}
            />
            <button className="btn btn-ghost btn-sm" onClick={loadOrders}>
              Search
            </button>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All statuses</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
        </div>

        {error && <div className="form-error">{error}</div>}
        {loading ? (
          <p className="muted">Loading orders…</p>
        ) : orders.length === 0 ? (
          <p className="muted">No orders found.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Order</th>
                <th>Buyer</th>
                <th>Fabric</th>
                <th>Colour</th>
                <th>Qty (m)</th>
                <th>Rate</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td>{o.order_no}</td>
                  <td>{o.buyer_name}</td>
                  <td>{o.fabric_type}</td>
                  <td>{o.colour}</td>
                  <td>{o.quantity_meters}</td>
                  <td>₹{o.unit_price}</td>
                  <td>
                    <span className={`status status-${o.status}`}>
                      {o.status}
                    </span>
                  </td>
                  <td className="row-actions">
                    <button
                      className="btn btn-ghost btn-sm"
                      disabled={busyId === o.id}
                      onClick={() => onCheckYarn(o)}
                    >
                      Check yarn
                    </button>
                    {(o.status === "draft" || o.status === "confirmed") && (
                      <button
                        className="btn btn-primary btn-sm"
                        disabled={busyId === o.id || o.status === "confirmed"}
                        onClick={() => onConfirm(o)}
                      >
                        {o.status === "confirmed" ? "Confirmed" : "Confirm"}
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

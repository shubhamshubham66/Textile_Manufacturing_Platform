import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";
import { isLiveRefresh, useLive } from "../../live/LiveContext.jsx";
import { inr, qty, ddmmyyyy, statusLabel } from "../../lib/format.js";
import "../../owner.css";

const STATUSES = [
  "draft",
  "confirmed",
  "in_production",
  "in_quality",
  "ready_to_ship",
  "dispatched",
  "closed",
  "cancelled",
];

const STATUS_CHIP = {
  draft: "owner-chip-grey",
  confirmed: "owner-chip-blue",
  in_production: "owner-chip-blue",
  in_quality: "owner-chip-amber",
  ready_to_ship: "owner-chip-blue",
  dispatched: "owner-chip-green",
  closed: "owner-chip-green",
  cancelled: "owner-chip-red",
};

const RESULT_CHIP = {
  pass: "owner-chip-green",
  rework: "owner-chip-amber",
  reject: "owner-chip-red",
  pending: "owner-chip-grey",
};

const EMPTY_FORM = {
  buyer_id: "",
  fabric_type: "",
  colour: "",
  quantity_meters: "",
  unit_price: "",
  deadline: "",
};

export default function Orders() {
  const [orders, setOrders] = useState([]);
  const [buyers, setBuyers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // One-shot filter handed over from the Dashboard "Orders by stage" chart.
  const initialStatus =
    typeof window !== "undefined" && window.__ownerOrdersFilter
      ? window.__ownerOrdersFilter
      : "";
  if (typeof window !== "undefined") window.__ownerOrdersFilter = undefined;

  const [statusFilter, setStatusFilter] = useState(initialStatus);
  const [search, setSearch] = useState("");

  const [form, setForm] = useState(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);

  const [yarnResult, setYarnResult] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const [track, setTrack] = useState(null); // tracker drawer data
  const [trackLoading, setTrackLoading] = useState(false);
  const [editOrder, setEditOrder] = useState(null); // order being edited

  async function loadOrders() {
    if (!isLiveRefresh()) setLoading(true);
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

  // Reload quietly when something this page shows changes elsewhere.
  useLive(["orders", "quality", "production"], loadOrders);

  function validate() {
    const e = {};
    if (!form.buyer_id) e.buyer_id = "Select a buyer.";
    if (!form.fabric_type.trim()) e.fabric_type = "Fabric type is required.";
    if (!form.colour.trim()) e.colour = "Colour is required.";
    const q = Number(form.quantity_meters);
    if (!form.quantity_meters || isNaN(q) || q <= 0)
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

  async function openTracker(order) {
    setTrack({ loading: true });
    setTrackLoading(true);
    try {
      const data = await apiFetch(`/api/orders/${order.id}/track`);
      setTrack(data);
    } catch (err) {
      setTrack({ error: err.message });
    } finally {
      setTrackLoading(false);
    }
  }

  async function onCancel(order) {
    if (
      !window.confirm(
        `Cancel ${order.order_no}? It stays on record but leaves the active pipeline.`,
      )
    )
      return;
    setBusyId(order.id);
    setError("");
    try {
      await apiFetch(`/api/orders/${order.id}/cancel`, { method: "POST" });
      await loadOrders();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="module owner-page">
      <h2>Orders</h2>

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
            <span>Deadline (dd/mm/yyyy)</span>
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
                  {statusLabel(s)}
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
                <th className="num">Qty</th>
                <th className="num">Rate</th>
                <th>Deadline</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => {
                const confirmed = o.status === "confirmed";
                return (
                  <tr key={o.id}>
                    <td>{o.order_no}</td>
                    <td>{o.buyer_name}</td>
                    <td>{o.fabric_type}</td>
                    <td>{o.colour}</td>
                    <td className="num">{qty(o.quantity_meters, "m")}</td>
                    <td className="num owner-num">{inr(o.unit_price)}</td>
                    <td>{ddmmyyyy(o.deadline)}</td>
                    <td>
                      <span
                        className={`owner-chip ${STATUS_CHIP[o.status] || "owner-chip-grey"}`}
                      >
                        {statusLabel(o.status)}
                      </span>
                    </td>
                    <td className="row-actions">
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => openTracker(o)}
                      >
                        Track
                      </button>
                      <button
                        className="btn btn-ghost btn-sm"
                        disabled={busyId === o.id}
                        onClick={() => onCheckYarn(o)}
                      >
                        Check yarn
                      </button>
                      {(o.status === "draft" || confirmed) && (
                        <button
                          className={`btn btn-sm ${confirmed ? "btn-ghost" : "btn-primary"}`}
                          disabled={busyId === o.id || confirmed}
                          onClick={() => onConfirm(o)}
                        >
                          {confirmed ? "Confirmed" : "Confirm"}
                        </button>
                      )}
                      {(o.status === "draft" || o.status === "confirmed") && (
                        <>
                          <button
                            className="btn btn-ghost btn-sm"
                            disabled={busyId === o.id}
                            onClick={() => setEditOrder(o)}
                          >
                            Edit
                          </button>
                          <button
                            className="link-btn"
                            disabled={busyId === o.id}
                            onClick={() => onCancel(o)}
                          >
                            Cancel
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      {track && (
        <TrackerDrawer
          track={track}
          loading={trackLoading}
          onClose={() => setTrack(null)}
        />
      )}

      {editOrder && (
        <OrderEditDialog
          order={editOrder}
          buyers={buyers}
          onClose={() => setEditOrder(null)}
          onSaved={() => {
            setEditOrder(null);
            loadOrders();
          }}
        />
      )}
    </div>
  );
}

function OrderEditDialog({ order, buyers, onClose, onSaved }) {
  const [f, setF] = useState({
    buyer_id: String(order.buyer_id || ""),
    fabric_type: order.fabric_type || "",
    colour: order.colour || "",
    quantity_meters: order.quantity_meters ?? "",
    unit_price: order.unit_price ?? "",
    deadline: order.deadline ? String(order.deadline).slice(0, 10) : "",
  });
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    if (!f.buyer_id) return setErr("Select a buyer.");
    if (!f.fabric_type.trim()) return setErr("Fabric type is required.");
    if (!f.colour.trim()) return setErr("Colour is required.");
    if (!(Number(f.quantity_meters) > 0))
      return setErr("Quantity must be greater than 0.");
    if (!(Number(f.unit_price) >= 0)) return setErr("Rate must be 0 or more.");
    setSaving(true);
    setErr("");
    try {
      await apiFetch(`/api/orders/${order.id}`, {
        method: "PUT",
        body: {
          buyer_id: Number(f.buyer_id),
          fabric_type: f.fabric_type.trim(),
          colour: f.colour.trim(),
          quantity_meters: Number(f.quantity_meters),
          unit_price: Number(f.unit_price),
          deadline: f.deadline || null,
        },
      });
      onSaved();
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="owner-drawer-backdrop" onClick={onClose}>
      <div
        className="owner-dialog"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Edit order"
      >
        <h3>Edit {order.order_no}</h3>
        <p className="muted">Allowed before production starts.</p>
        <form onSubmit={submit} noValidate>
          {err && <div className="form-error">{err}</div>}
          <label className="field">
            <span>Buyer</span>
            <select value={f.buyer_id} onChange={set("buyer_id")}>
              <option value="">Select buyer…</option>
              {buyers.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Fabric type</span>
            <input value={f.fabric_type} onChange={set("fabric_type")} />
          </label>
          <label className="field">
            <span>Colour</span>
            <input value={f.colour} onChange={set("colour")} />
          </label>
          <label className="field">
            <span>Quantity (metres)</span>
            <input
              type="number"
              min="0"
              step="any"
              value={f.quantity_meters}
              onChange={set("quantity_meters")}
            />
          </label>
          <label className="field">
            <span>Rate (₹/metre)</span>
            <input
              type="number"
              min="0"
              step="any"
              value={f.unit_price}
              onChange={set("unit_price")}
            />
          </label>
          <label className="field">
            <span>Deadline (dd/mm/yyyy)</span>
            <input type="date" value={f.deadline} onChange={set("deadline")} />
          </label>
          <div className="form-actions" style={{ gap: "0.5rem" }}>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={onClose}
              disabled={saving}
            >
              Cancel
            </button>
            <button className="btn btn-primary btn-sm" disabled={saving}>
              {saving ? "Saving…" : "Save changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function TrackerDrawer({ track, loading, onClose }) {
  return (
    <div className="owner-drawer-backdrop" onClick={onClose}>
      <div className="owner-drawer" onClick={(e) => e.stopPropagation()}>
        <button
          className="link-btn"
          onClick={onClose}
          style={{ float: "right" }}
        >
          close
        </button>
        {loading || track.loading ? (
          <p className="muted">Loading tracker…</p>
        ) : track.error ? (
          <div className="form-error">{track.error}</div>
        ) : (
          <>
            <h3>
              {track.order_no} — {track.fabric_type} ({track.colour})
            </h3>
            <p className="muted">
              {track.buyer_name} · {qty(track.quantity_meters, "m")} ordered
            </p>

            <div className="stepper">
              {track.stage_flow.map((s, i) => (
                <div
                  key={s}
                  className={`step-dot ${i <= track.stage_index ? "done" : ""}`}
                >
                  <span
                    className="step-circle"
                    style={{
                      background:
                        i <= track.stage_index ? "var(--brand)" : "#e5e7eb",
                      color: i <= track.stage_index ? "#fff" : "#64748b",
                    }}
                  >
                    {i + 1}
                  </span>
                  <small>{statusLabel(s)}</small>
                </div>
              ))}
            </div>

            <div style={{ margin: "1rem 0" }}>
              <div className="pl-row">
                <span>Progress</span>
                <strong className="owner-num">{track.progress_percent}%</strong>
              </div>
              <div className="pl-row">
                <span>Deadline</span>
                <strong>{ddmmyyyy(track.deadline)}</strong>
              </div>
              <div className="pl-row">
                <span>Status</span>
                <span
                  className={
                    track.late ? "owner-flag-late" : "owner-flag-ontrack"
                  }
                >
                  {track.late ? "Late" : "On track"}
                </span>
              </div>
            </div>

            <h4>Rolls ({track.rolls.length})</h4>
            {track.rolls.length === 0 ? (
              <p className="muted">No rolls made yet.</p>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Roll</th>
                    <th className="num">Length</th>
                    <th>Machine</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {track.rolls.map((r) => (
                    <tr key={r.roll_no}>
                      <td>{r.roll_no}</td>
                      <td className="num">{qty(r.length_meters, "m")}</td>
                      <td>{r.machine}</td>
                      <td>
                        <span
                          className={`owner-chip ${RESULT_CHIP[r.result] || "owner-chip-grey"}`}
                          title={
                            r.defect_type && r.defect_type !== "none"
                              ? `Defect: ${r.defect_type}`
                              : undefined
                          }
                        >
                          {statusLabel(r.result)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </div>
    </div>
  );
}

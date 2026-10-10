import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";
import { isLiveRefresh, useLive } from "../../live/LiveContext.jsx";

const EMPTY = {
  supplier_id: "",
  yarn_type: "",
  colour: "",
  quantity_kg: "",
  unit_cost: "",
};

// Raise purchase: creates a purchase order for a supplier when yarn is short.
export default function Purchase() {
  const [suppliers, setSuppliers] = useState([]);
  const [pos, setPos] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  async function loadPurchases() {
    if (!isLiveRefresh()) setLoading(true);
    try {
      setPos(await apiFetch("/api/yarn/purchase"));
    } catch (err) {
      setFormError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    apiFetch("/api/yarn/suppliers")
      .then(setSuppliers)
      .catch((e) => setFormError(e.message));
    loadPurchases();
  }, []);

  // Reload quietly when something this page shows changes elsewhere.
  useLive(["yarn"], loadPurchases);

  function validate() {
    const e = {};
    if (!form.supplier_id) e.supplier_id = "Select a supplier.";
    if (!form.yarn_type.trim()) e.yarn_type = "Yarn type is required.";
    if (!form.colour.trim()) e.colour = "Colour is required.";
    const qty = Number(form.quantity_kg);
    if (!form.quantity_kg || isNaN(qty) || qty <= 0)
      e.quantity_kg = "Quantity must be greater than 0.";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function onSubmit(ev) {
    ev.preventDefault();
    setFormError("");
    if (!validate()) return;
    setSaving(true);
    try {
      await apiFetch("/api/yarn/purchase", {
        method: "POST",
        body: {
          supplier_id: Number(form.supplier_id),
          yarn_type: form.yarn_type.trim(),
          colour: form.colour.trim(),
          quantity_kg: Number(form.quantity_kg),
          unit_cost: form.unit_cost ? Number(form.unit_cost) : 0,
        },
      });
      setForm(EMPTY);
      setErrors({});
      await loadPurchases();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="module">
      <h2>Purchase</h2>

      <section className="panel">
        <h3>Raise purchase order</h3>
        {formError && <div className="form-error">{formError}</div>}
        <form className="form-grid" onSubmit={onSubmit} noValidate>
          <label className="field">
            <span>Supplier</span>
            <select
              value={form.supplier_id}
              onChange={(e) =>
                setForm({ ...form, supplier_id: e.target.value })
              }
              className={errors.supplier_id ? "invalid" : ""}
            >
              <option value="">Select supplier…</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            {errors.supplier_id && (
              <small className="field-error">{errors.supplier_id}</small>
            )}
          </label>

          <label className="field">
            <span>Yarn type</span>
            <input
              value={form.yarn_type}
              onChange={(e) => setForm({ ...form, yarn_type: e.target.value })}
              className={errors.yarn_type ? "invalid" : ""}
              placeholder="Cotton 40s"
            />
            {errors.yarn_type && (
              <small className="field-error">{errors.yarn_type}</small>
            )}
          </label>

          <label className="field">
            <span>Colour</span>
            <input
              value={form.colour}
              onChange={(e) => setForm({ ...form, colour: e.target.value })}
              className={errors.colour ? "invalid" : ""}
              placeholder="Blue"
            />
            {errors.colour && (
              <small className="field-error">{errors.colour}</small>
            )}
          </label>

          <label className="field">
            <span>Quantity (kg)</span>
            <input
              type="number"
              min="0"
              step="any"
              value={form.quantity_kg}
              onChange={(e) =>
                setForm({ ...form, quantity_kg: e.target.value })
              }
              className={errors.quantity_kg ? "invalid" : ""}
            />
            {errors.quantity_kg && (
              <small className="field-error">{errors.quantity_kg}</small>
            )}
          </label>

          <label className="field">
            <span>Unit cost (₹/kg)</span>
            <input
              type="number"
              min="0"
              step="any"
              value={form.unit_cost}
              onChange={(e) => setForm({ ...form, unit_cost: e.target.value })}
            />
          </label>

          <div className="form-actions">
            <button className="btn btn-primary" disabled={saving}>
              {saving ? "Raising…" : "Raise purchase"}
            </button>
          </div>
        </form>
      </section>

      <section className="panel">
        <h3>Purchase orders</h3>
        {loading ? (
          <p className="muted">Loading…</p>
        ) : pos.length === 0 ? (
          <p className="muted">No purchase orders yet.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>PO</th>
                <th>Supplier</th>
                <th>Yarn</th>
                <th>Colour</th>
                <th>Qty (kg)</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {pos.map((p) => (
                <tr key={p.id}>
                  <td>{p.po_no}</td>
                  <td>{p.supplier_name}</td>
                  <td>{p.yarn_type}</td>
                  <td>{p.colour}</td>
                  <td>{p.quantity_kg}</td>
                  <td>
                    <span className={`status status-${p.status}`}>
                      {p.status}
                    </span>
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

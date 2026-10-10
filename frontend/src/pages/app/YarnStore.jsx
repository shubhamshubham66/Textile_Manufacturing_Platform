import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";

const EMPTY = {
  supplier_id: "",
  yarn_type: "",
  colour: "",
  quantity_kg: "",
  unit_cost: "",
  order_id: "",
};

// Yarn received form. On success, stock updates automatically on the backend;
// we show the resulting stock row so the user sees the new quantity.
export default function YarnStore() {
  const [suppliers, setSuppliers] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [result, setResult] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    apiFetch("/api/yarn/suppliers")
      .then(setSuppliers)
      .catch((e) => setFormError(e.message));
  }, []);

  function validate() {
    const e = {};
    if (!form.yarn_type.trim()) e.yarn_type = "Yarn type is required.";
    if (!form.colour.trim()) e.colour = "Colour is required.";
    const qty = Number(form.quantity_kg);
    if (!form.quantity_kg || isNaN(qty) || qty <= 0)
      e.quantity_kg = "Quantity must be greater than 0.";
    if (form.unit_cost !== "" && Number(form.unit_cost) < 0)
      e.unit_cost = "Cost cannot be negative.";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function onSubmit(ev) {
    ev.preventDefault();
    setFormError("");
    setResult(null);
    if (!validate()) return;
    setSaving(true);
    try {
      const stock = await apiFetch("/api/yarn/receipts", {
        method: "POST",
        body: {
          supplier_id: form.supplier_id ? Number(form.supplier_id) : null,
          yarn_type: form.yarn_type.trim(),
          colour: form.colour.trim(),
          quantity_kg: Number(form.quantity_kg),
          unit_cost: form.unit_cost ? Number(form.unit_cost) : 0,
          order_id: form.order_id ? Number(form.order_id) : null,
        },
      });
      setResult(stock);
      setForm(EMPTY);
      setErrors({});
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="module">
      <h2>Yarn store</h2>

      <section className="panel">
        <h3>Yarn received</h3>
        {formError && <div className="form-error">{formError}</div>}
        {result && (
          <div className="callout callout-ok">
            Stock updated: <strong>{result.yarn_type}</strong> ({result.colour})
            is now <strong>{result.quantity_kg} kg</strong>
            {result.low_stock && " — still below reorder level!"}
          </div>
        )}
        <form className="form-grid" onSubmit={onSubmit} noValidate>
          <label className="field">
            <span>Supplier</span>
            <select
              value={form.supplier_id}
              onChange={(e) =>
                setForm({ ...form, supplier_id: e.target.value })
              }
            >
              <option value="">(optional)</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Yarn type</span>
            <input
              value={form.yarn_type}
              onChange={(e) => setForm({ ...form, yarn_type: e.target.value })}
              className={errors.yarn_type ? "invalid" : ""}
              placeholder="Cotton 30s"
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
              placeholder="White"
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
              className={errors.unit_cost ? "invalid" : ""}
            />
            {errors.unit_cost && (
              <small className="field-error">{errors.unit_cost}</small>
            )}
          </label>

          <label className="field">
            <span>Linked order id</span>
            <input
              type="number"
              min="1"
              value={form.order_id}
              onChange={(e) => setForm({ ...form, order_id: e.target.value })}
              placeholder="(optional)"
            />
          </label>

          <div className="form-actions">
            <button className="btn btn-primary" disabled={saving}>
              {saving ? "Saving…" : "Receive yarn"}
            </button>
          </div>
        </form>
        <p className="muted">
          Receiving yarn increases live stock automatically. See the{" "}
          <strong>Stock</strong> page for current quantities and low-stock
          alerts.
        </p>
      </section>
    </div>
  );
}

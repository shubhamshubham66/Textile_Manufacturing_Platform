import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";

// Stock list with live quantity per type+colour and a low-stock alert.
export default function Stock() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setRows(await apiFetch("/api/yarn/stock"));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const lowRows = rows.filter((r) => r.low_stock);

  return (
    <div className="module">
      <h2>Stock</h2>

      {lowRows.length > 0 && (
        <div className="callout callout-warn">
          <strong>⚠ Low stock alert:</strong>{" "}
          {lowRows
            .map((r) => `${r.yarn_type} (${r.colour}) — ${r.quantity_kg} kg`)
            .join(", ")}
          . Raise a purchase to replenish.
        </div>
      )}

      <section className="panel">
        <div className="toolbar">
          <h3>Live yarn stock</h3>
          <button className="btn btn-ghost btn-sm" onClick={load}>
            Refresh
          </button>
        </div>

        {error && <div className="form-error">{error}</div>}
        {loading ? (
          <p className="muted">Loading stock…</p>
        ) : rows.length === 0 ? (
          <p className="muted">No yarn in stock yet.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Yarn type</th>
                <th>Colour</th>
                <th>Quantity (kg)</th>
                <th>Reorder level (kg)</th>
                <th>Unit cost</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className={r.low_stock ? "row-warn" : ""}>
                  <td>{r.yarn_type}</td>
                  <td>{r.colour}</td>
                  <td>{r.quantity_kg}</td>
                  <td>{r.reorder_level_kg}</td>
                  <td>₹{r.unit_cost}</td>
                  <td>
                    {r.low_stock ? (
                      <span className="status status-reject">Low</span>
                    ) : (
                      <span className="status status-pass">OK</span>
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

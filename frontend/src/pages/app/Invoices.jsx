import { useEffect, useState } from "react";
import { apiFetch, getToken } from "../../lib/api.js";
import { inr } from "../../lib/format.js";

// Buyer: list + PDF download for OWN invoices only.
export default function Invoices() {
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setInvoices(await apiFetch("/api/buyer/invoices"));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function download(invoiceId) {
    try {
      const res = await fetch(`/api/buyer/invoices/${invoiceId}/pdf`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      window.open(URL.createObjectURL(blob), "_blank");
    } catch {
      setError("Could not open invoice PDF.");
    }
  }


  return (
    <div className="module">
      <h2>Invoices</h2>
      {error && <div className="form-error">{error}</div>}

      <section className="panel">
        <h3>Your invoices</h3>
        {loading ? (
          <p className="muted">Loading…</p>
        ) : invoices.length === 0 ? (
          <p className="muted">No invoices yet.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Invoice</th>
                <th>Order</th>
                <th>Subtotal</th>
                <th>Tax</th>
                <th>Total</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((i) => (
                <tr key={i.id}>
                  <td>{i.invoice_no}</td>
                  <td>{i.order_no}</td>
                  <td>{inr(i.subtotal)}</td>
                  <td>{inr(i.tax)}</td>
                  <td>
                    <strong>{inr(i.total)}</strong>
                  </td>
                  <td>
                    <span
                      className={`status status-${i.status === "paid" ? "pass" : i.status === "part_paid" ? "raised" : "reject"}`}
                    >
                      {i.status}
                    </span>
                  </td>
                  <td>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => download(i.id)}
                    >
                      Download PDF
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

import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";

// Payments module (owner + accountant): record buyer payment, pay supplier,
// pending dues.
export default function Payments() {
  const [meta, setMeta] = useState({ invoices: [], suppliers: [] });
  const [payments, setPayments] = useState([]);
  const [dues, setDues] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const [buyerForm, setBuyerForm] = useState({
    invoice_id: "",
    amount: "",
    method: "bank",
  });
  const [supForm, setSupForm] = useState({
    supplier_id: "",
    amount: "",
    method: "bank",
  });

  async function loadAll() {
    setLoading(true);
    setError("");
    try {
      const [m, p, d] = await Promise.all([
        apiFetch("/api/payments/_meta"),
        apiFetch("/api/payments"),
        apiFetch("/api/payments/dues"),
      ]);
      setMeta(m);
      setPayments(p);
      setDues(d);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function payBuyer(ev) {
    ev.preventDefault();
    setMsg("");
    if (!buyerForm.invoice_id || !(Number(buyerForm.amount) > 0)) {
      setMsg("Select an invoice and enter an amount > 0.");
      return;
    }
    setBusy(true);
    try {
      const res = await apiFetch("/api/payments/buyer", {
        method: "POST",
        body: {
          invoice_id: Number(buyerForm.invoice_id),
          amount: Number(buyerForm.amount),
          method: buyerForm.method,
        },
      });
      setMsg(
        `Payment recorded on ${res.invoice_no}: now ${res.invoice_status}, balance ₹${res.balance.toLocaleString("en-IN")}.`,
      );
      setBuyerForm({ invoice_id: "", amount: "", method: "bank" });
      await loadAll();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function paySupplier(ev) {
    ev.preventDefault();
    setMsg("");
    if (!supForm.supplier_id || !(Number(supForm.amount) > 0)) {
      setMsg("Select a supplier and enter an amount > 0.");
      return;
    }
    setBusy(true);
    try {
      const res = await apiFetch("/api/payments/supplier", {
        method: "POST",
        body: {
          supplier_id: Number(supForm.supplier_id),
          amount: Number(supForm.amount),
          method: supForm.method,
        },
      });
      setMsg(`Paid ₹${res.amount.toLocaleString("en-IN")} to ${res.supplier}.`);
      setSupForm({ supplier_id: "", amount: "", method: "bank" });
      await loadAll();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="module">
      <h2>Payments</h2>
      {error && <div className="form-error">{error}</div>}
      {msg && <div className="callout callout-ok">{msg}</div>}

      <div className="two-col">
        <section className="panel">
          <h3>Record buyer payment</h3>
          <form onSubmit={payBuyer}>
            <label className="field">
              <span>Invoice</span>
              <select
                value={buyerForm.invoice_id}
                onChange={(e) =>
                  setBuyerForm({ ...buyerForm, invoice_id: e.target.value })
                }
              >
                <option value="">Select invoice…</option>
                {meta.invoices.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.invoice_no} — {i.buyer_name} (bal ₹{i.balance})
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Amount (₹)</span>
              <input
                type="number"
                min="0"
                step="any"
                value={buyerForm.amount}
                onChange={(e) =>
                  setBuyerForm({ ...buyerForm, amount: e.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Method</span>
              <select
                value={buyerForm.method}
                onChange={(e) =>
                  setBuyerForm({ ...buyerForm, method: e.target.value })
                }
              >
                <option value="bank">Bank</option>
                <option value="cash">Cash</option>
                <option value="upi">UPI</option>
              </select>
            </label>
            <button className="btn btn-primary" disabled={busy}>
              Record payment
            </button>
          </form>
        </section>

        <section className="panel">
          <h3>Pay supplier</h3>
          <form onSubmit={paySupplier}>
            <label className="field">
              <span>Supplier</span>
              <select
                value={supForm.supplier_id}
                onChange={(e) =>
                  setSupForm({ ...supForm, supplier_id: e.target.value })
                }
              >
                <option value="">Select supplier…</option>
                {meta.suppliers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Amount (₹)</span>
              <input
                type="number"
                min="0"
                step="any"
                value={supForm.amount}
                onChange={(e) =>
                  setSupForm({ ...supForm, amount: e.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Method</span>
              <select
                value={supForm.method}
                onChange={(e) =>
                  setSupForm({ ...supForm, method: e.target.value })
                }
              >
                <option value="bank">Bank</option>
                <option value="cash">Cash</option>
                <option value="upi">UPI</option>
              </select>
            </label>
            <button className="btn btn-primary" disabled={busy}>
              Pay supplier
            </button>
          </form>
        </section>
      </div>

      {/* Pending dues */}
      <section className="panel">
        <h3>Pending dues</h3>
        {loading || !dues ? (
          <p className="muted">Loading…</p>
        ) : (
          <div className="two-col">
            <div>
              <h4>
                Buyers owe us (₹{dues.total_receivable.toLocaleString("en-IN")})
              </h4>
              {dues.buyers_owe_us.length === 0 ? (
                <p className="muted">All settled.</p>
              ) : (
                <table className="data-table">
                  <tbody>
                    {dues.buyers_owe_us.map((b) => (
                      <tr key={b.buyer_name}>
                        <td>{b.buyer_name}</td>
                        <td>
                          <strong>₹{b.due.toLocaleString("en-IN")}</strong>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            <div>
              <h4>
                We owe suppliers (₹{dues.total_payable.toLocaleString("en-IN")})
              </h4>
              {dues.we_owe_suppliers.length === 0 ? (
                <p className="muted">All settled.</p>
              ) : (
                <table className="data-table">
                  <tbody>
                    {dues.we_owe_suppliers.map((s) => (
                      <tr key={s.supplier_name}>
                        <td>{s.supplier_name}</td>
                        <td>
                          <strong>₹{s.due.toLocaleString("en-IN")}</strong>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </section>

      {/* Payment history */}
      <section className="panel">
        <h3>Payment history</h3>
        {payments.length === 0 ? (
          <p className="muted">No payments yet.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Direction</th>
                <th>Party</th>
                <th>Amount</th>
                <th>Method</th>
              </tr>
            </thead>
            <tbody>
              {payments.map((p) => (
                <tr key={p.id}>
                  <td>
                    <span
                      className={`status status-${p.direction === "incoming" ? "pass" : "raised"}`}
                    >
                      {p.direction === "incoming" ? "In" : "Out"}
                    </span>
                  </td>
                  <td>{p.party}</td>
                  <td>₹{p.amount.toLocaleString("en-IN")}</td>
                  <td>{p.method}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

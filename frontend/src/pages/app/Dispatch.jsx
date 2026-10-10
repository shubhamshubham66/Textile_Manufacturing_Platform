import { useEffect, useState } from "react";
import { apiFetch, getToken } from "../../lib/api.js";
import { isLiveRefresh, useLive } from "../../live/LiveContext.jsx";

// Dispatch module (store manager): pick ONLY passed rolls, confirm dispatch in
// one transaction (marks rolls + creates dispatch + invoice), finished-stock
// view, and invoice print (PDF).
export default function Dispatch() {
  const [orders, setOrders] = useState([]);
  const [dispatches, setDispatches] = useState([]);
  const [finished, setFinished] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [picked, setPicked] = useState(null); // {order_id, order_no, unit_price, rolls}
  const [selected, setSelected] = useState(new Set());
  const [confirmMsg, setConfirmMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function loadAll() {
    if (!isLiveRefresh()) setLoading(true);
    setError("");
    try {
      const [o, d, f] = await Promise.all([
        apiFetch("/api/dispatch/orders"),
        apiFetch("/api/dispatch"),
        apiFetch("/api/dispatch/finished-stock"),
      ]);
      setOrders(o);
      setDispatches(d);
      setFinished(f);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  // Reload quietly when something this page shows changes elsewhere.
  useLive(["quality", "orders", "payments"], loadAll);

  async function openPicker(orderId) {
    setConfirmMsg("");
    setSelected(new Set());
    try {
      const data = await apiFetch(`/api/dispatch/orders/${orderId}/pickable`);
      setPicked(data);
    } catch (err) {
      setError(err.message);
    }
  }

  function toggle(rollId) {
    const next = new Set(selected);
    if (next.has(rollId)) next.delete(rollId);
    else next.add(rollId);
    setSelected(next);
  }

  const selectedMeters = picked
    ? picked.rolls
        .filter((r) => selected.has(r.id))
        .reduce((s, r) => s + r.length_meters, 0)
    : 0;

  async function confirmDispatch() {
    if (selected.size === 0) {
      setConfirmMsg("Select at least one passed roll.");
      return;
    }
    setBusy(true);
    setConfirmMsg("");
    try {
      const res = await apiFetch("/api/dispatch/confirm", {
        method: "POST",
        body: {
          order_id: picked.order_id,
          roll_ids: Array.from(selected),
        },
      });
      setConfirmMsg(
        `Dispatched ${res.total_rolls} rolls (${res.total_meters} m). ` +
          `Invoice ${res.invoice_no} total ₹${res.total.toLocaleString("en-IN")}.`,
      );
      setPicked(null);
      setSelected(new Set());
      await loadAll();
    } catch (err) {
      // 400/409 messages (not-passed / double dispatch) land here.
      setConfirmMsg(err.message);
    } finally {
      setBusy(false);
    }
  }

  function openInvoicePdf(invoiceId) {
    // Open the PDF with the bearer token via fetch -> blob (can't set headers on
    // a plain link). Falls back to an error message.
    apiFetch(`/api/dispatch/invoice/${invoiceId}`)
      .then(() => {
        const url = `/api/dispatch/invoice/${invoiceId}/pdf`;
        fetch(url, { headers: { Authorization: `Bearer ${getToken()}` } })
          .then((r) => r.blob())
          .then((blob) => {
            const objUrl = URL.createObjectURL(blob);
            window.open(objUrl, "_blank");
          })
          .catch(() => setError("Could not open invoice PDF."));
      })
      .catch((e) => setError(e.message));
  }

  return (
    <div className="module">
      <h2>Dispatch</h2>
      {error && <div className="form-error">{error}</div>}
      {confirmMsg && (
        <div
          className={`callout ${
            confirmMsg.toLowerCase().includes("dispatched ")
              ? "callout-ok"
              : "callout-warn"
          }`}
        >
          {confirmMsg}
        </div>
      )}

      <section className="panel">
        <div className="toolbar">
          <h3>Orders ready to dispatch (passed rolls)</h3>
          <button className="btn btn-ghost btn-sm" onClick={loadAll}>
            Refresh
          </button>
        </div>
        {loading ? (
          <p className="muted">Loading…</p>
        ) : orders.length === 0 ? (
          <p className="muted">
            No orders have passed rolls awaiting dispatch.
          </p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Order</th>
                <th>Buyer</th>
                <th>Passed rolls</th>
                <th>Pick</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.order_id}>
                  <td>{o.order_no}</td>
                  <td>{o.buyer_name}</td>
                  <td>{o.passed_rolls}</td>
                  <td>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => openPicker(o.order_id)}
                    >
                      Pick rolls
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* Picker */}
      {picked && (
        <section className="panel">
          <h3>
            Pick passed rolls — {picked.order_no} (₹{picked.unit_price}/m)
          </h3>
          {picked.rolls.length === 0 ? (
            <p className="muted">No passed rolls available for this order.</p>
          ) : (
            <>
              <table className="data-table">
                <thead>
                  <tr>
                    <th></th>
                    <th>Roll</th>
                    <th>Length (m)</th>
                  </tr>
                </thead>
                <tbody>
                  {picked.rolls.map((r) => (
                    <tr key={r.id}>
                      <td>
                        <input
                          type="checkbox"
                          checked={selected.has(r.id)}
                          onChange={() => toggle(r.id)}
                        />
                      </td>
                      <td>{r.roll_no}</td>
                      <td>{r.length_meters}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="muted">
                Selected: {selected.size} rolls, {selectedMeters} m → est.
                subtotal ₹
                {(selectedMeters * picked.unit_price).toLocaleString("en-IN")}
              </p>
              <div className="inline-actions">
                <button
                  className="btn btn-primary"
                  disabled={busy || selected.size === 0}
                  onClick={confirmDispatch}
                >
                  {busy ? "Dispatching…" : "Confirm dispatch"}
                </button>
                <button
                  className="btn btn-ghost"
                  onClick={() => setPicked(null)}
                >
                  Cancel
                </button>
              </div>
            </>
          )}
        </section>
      )}

      {/* Finished stock */}
      <section className="panel">
        <h3>Finished stock — on shelf vs dispatched</h3>
        {finished.length === 0 ? (
          <p className="muted">No finished rolls yet.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Order</th>
                <th>On shelf (rolls)</th>
                <th>On shelf (m)</th>
                <th>Dispatched (rolls)</th>
                <th>Dispatched (m)</th>
              </tr>
            </thead>
            <tbody>
              {finished.map((f) => (
                <tr key={f.order_no}>
                  <td>{f.order_no}</td>
                  <td>{f.on_shelf_rolls}</td>
                  <td>{f.on_shelf_meters}</td>
                  <td>{f.dispatched_rolls}</td>
                  <td>{f.dispatched_meters}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* Dispatches + invoices */}
      <section className="panel">
        <h3>Dispatches</h3>
        {dispatches.length === 0 ? (
          <p className="muted">No dispatches yet.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Dispatch</th>
                <th>Order</th>
                <th>Buyer</th>
                <th>Rolls</th>
                <th>Metres</th>
                <th>Invoice</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {dispatches.map((d) => (
                <tr key={d.id}>
                  <td>{d.dispatch_no}</td>
                  <td>{d.order_no}</td>
                  <td>{d.buyer_name}</td>
                  <td>{d.total_rolls}</td>
                  <td>{d.total_meters}</td>
                  <td>{d.invoice_no || "—"}</td>
                  <td>
                    {d.invoice_id && (
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => openInvoicePdf(d.invoice_id)}
                      >
                        Print invoice
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

import { useEffect, useRef, useState } from "react";
import { apiFetch, newIdempotencyKey } from "../../lib/api.js";
import { useAuth } from "../../auth/AuthContext.jsx";
import { isLiveRefresh, useLive } from "../../live/LiveContext.jsx";
import { inr, ddmmyyyy, statusLabel } from "../../lib/format.js";
import "../../owner.css";
import OwnerMoney from "./OwnerMoney.jsx";

// Payments at/above this amount get an "Unusually large" badge (₹10,00,000).
const LARGE_PAYMENT = 1000000;

// Payments module. The owner gets a read-only month view (OwnerMoney); the
// accountant records buyer payments, pays suppliers and sees the due tracker.
export default function Payments() {
  const { user } = useAuth();
  return user?.role === "owner" ? <OwnerMoney /> : <PaymentsDesk />;
}

function PaymentsDesk() {
  const { user } = useAuth();
  const isOwner = user?.role === "owner";
  const [meta, setMeta] = useState({ invoices: [], suppliers: [] });
  const [payments, setPayments] = useState([]);
  const [dues, setDues] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [msgKind, setMsgKind] = useState("ok");
  const [busy, setBusy] = useState(false);

  // Void dialog state.
  const [voidTarget, setVoidTarget] = useState(null); // the payment row
  const [voidReason, setVoidReason] = useState("");
  const [voiding, setVoiding] = useState(false);

  const [buyerForm, setBuyerForm] = useState({
    invoice_id: "",
    amount: "",
    method: "bank",
  });
  const [supForm, setSupForm] = useState({
    supplier_id: "",
    amount: "",
    method: "bank",
    is_advance: false,
  });

  // Idempotency keys: one per in-progress payment. A retry of the SAME payment
  // (e.g. a double-click or a network retry) reuses the key so the backend
  // records the payment only once; after a success we rotate to a fresh key so
  // the next genuine payment is treated as new.
  const buyerKey = useRef(newIdempotencyKey());
  const supKey = useRef(newIdempotencyKey());

  async function loadAll() {
    if (!isLiveRefresh()) setLoading(true);
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

  // Reload quietly when something this page shows changes elsewhere.
  useLive(["payments", "orders"], loadAll);

  function flash(kind, text) {
    setMsgKind(kind);
    setMsg(text);
  }

  async function payBuyer(ev) {
    ev.preventDefault();
    setMsg("");
    if (!buyerForm.invoice_id || !(Number(buyerForm.amount) > 0)) {
      flash("err", "Select an invoice and enter an amount greater than 0.");
      return;
    }
    setBusy(true);
    try {
      const res = await apiFetch("/api/payments/buyer", {
        method: "POST",
        idempotencyKey: buyerKey.current,
        body: {
          invoice_id: Number(buyerForm.invoice_id),
          amount: Number(buyerForm.amount),
          method: buyerForm.method,
        },
      });
      flash(
        "ok",
        `Payment recorded on ${res.invoice_no}: now ${statusLabel(res.invoice_status)}, balance ${inr(res.balance)}.`,
      );
      setBuyerForm({ invoice_id: "", amount: "", method: "bank" });
      buyerKey.current = newIdempotencyKey(); // next payment is a new one
      await loadAll();
    } catch (err) {
      flash("err", err.message);
    } finally {
      setBusy(false);
    }
  }

  async function paySupplier(ev) {
    ev.preventDefault();
    setMsg("");
    if (!supForm.supplier_id || !(Number(supForm.amount) > 0)) {
      flash("err", "Select a supplier and enter an amount greater than 0.");
      return;
    }
    setBusy(true);
    try {
      const res = await apiFetch("/api/payments/supplier", {
        method: "POST",
        idempotencyKey: supKey.current,
        body: {
          supplier_id: Number(supForm.supplier_id),
          amount: Number(supForm.amount),
          method: supForm.method,
          is_advance: supForm.is_advance,
        },
      });
      flash(
        "ok",
        `Paid ${inr(res.amount)} to ${res.supplier}. Outstanding now ${inr(res.outstanding_after)}.`,
      );
      setSupForm({
        supplier_id: "",
        amount: "",
        method: "bank",
        is_advance: false,
      });
      supKey.current = newIdempotencyKey(); // next payment is a new one
      await loadAll();
    } catch (err) {
      flash("err", err.message);
    } finally {
      setBusy(false);
    }
  }

  function openVoid(p) {
    setVoidReason("");
    setMsg("");
    setVoidTarget(p);
  }

  async function confirmVoid(ev) {
    ev.preventDefault();
    if (voidReason.trim().length < 3) {
      flash("err", "Please give a reason of at least 3 characters.");
      return;
    }
    setVoiding(true);
    try {
      await apiFetch(`/api/payments/${voidTarget.id}/void`, {
        method: "POST",
        body: { reason: voidReason.trim() },
      });
      flash(
        "ok",
        `Voided ${inr(voidTarget.amount)} payment to/from ${voidTarget.party || "—"}.`,
      );
      setVoidTarget(null);
      setVoidReason("");
      await loadAll();
    } catch (err) {
      flash("err", err.message);
    } finally {
      setVoiding(false);
    }
  }

  return (
    <div className="module owner-page">
      <h2>Payments</h2>
      {error && <div className="form-error">{error}</div>}
      {msg && (
        <div
          className={`callout ${msgKind === "ok" ? "callout-ok" : "callout-warn"}`}
        >
          {msg}
        </div>
      )}

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
                    {i.invoice_no} — {i.buyer_name} (bal {inr(i.balance)})
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
              {busy ? "Saving…" : "Record payment"}
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
            <label
              className="field"
              style={{
                flexDirection: "row",
                alignItems: "center",
                gap: "0.5rem",
              }}
            >
              <input
                type="checkbox"
                checked={supForm.is_advance}
                onChange={(e) =>
                  setSupForm({ ...supForm, is_advance: e.target.checked })
                }
                style={{ width: "auto" }}
              />
              <span style={{ margin: 0 }}>
                Advance (allow paying more than the outstanding bill)
              </span>
            </label>
            <button className="btn btn-primary" disabled={busy}>
              {busy ? "Saving…" : "Pay supplier"}
            </button>
          </form>
        </section>
      </div>

      {/* Due tracker */}
      <section className="panel">
        <h3>Due tracker</h3>
        {loading || !dues ? (
          <p className="muted">Loading…</p>
        ) : (
          <div className="owner-due-grid">
            <div>
              <h4>Buyers owe us ({inr(dues.total_receivable)})</h4>
              {dues.buyers_owe_us.length === 0 ? (
                <p className="muted">All settled.</p>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Buyer</th>
                      <th>Invoice</th>
                      <th>Date</th>
                      <th className="num">Due</th>
                      <th className="num">Age</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dues.buyers_owe_us.map((b, i) => (
                      <tr key={i}>
                        <td>{b.buyer_name}</td>
                        <td>{b.invoice_no}</td>
                        <td>{ddmmyyyy(b.invoice_date)}</td>
                        <td className="num owner-num">{inr(b.due)}</td>
                        <td className="num">
                          <span
                            className={`owner-chip ${b.overdue ? "owner-chip-red" : "owner-chip-grey"}`}
                          >
                            {b.days_overdue} d{b.overdue ? " · overdue" : ""}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            <div>
              <h4>We owe suppliers ({inr(dues.total_payable)})</h4>
              {dues.we_owe_suppliers.length === 0 ? (
                <p className="muted">All settled.</p>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Supplier</th>
                      <th>Bill date</th>
                      <th className="num">Due</th>
                      <th className="num">Age</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dues.we_owe_suppliers.map((s, i) => (
                      <tr key={i}>
                        <td>{s.supplier_name}</td>
                        <td>{ddmmyyyy(s.bill_date)}</td>
                        <td className="num owner-num">{inr(s.due)}</td>
                        <td className="num">
                          <span
                            className={`owner-chip ${s.overdue ? "owner-chip-red" : "owner-chip-grey"}`}
                          >
                            {s.days_overdue} d{s.overdue ? " · overdue" : ""}
                          </span>
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
                <th>Date</th>
                <th className="num">Amount</th>
                <th>Method</th>
                {isOwner && <th>Action</th>}
              </tr>
            </thead>
            <tbody>
              {payments.map((p) => {
                const large = Math.abs(Number(p.amount)) >= LARGE_PAYMENT;
                return (
                  <tr key={p.id} className={p.voided ? "owner-voided" : ""}>
                    <td>
                      <span
                        className={`owner-chip ${p.direction === "incoming" ? "owner-chip-green" : "owner-chip-amber"}`}
                      >
                        {p.direction === "incoming" ? "In" : "Out"}
                      </span>
                    </td>
                    <td>{p.party}</td>
                    <td>{ddmmyyyy(p.paid_at)}</td>
                    <td className="num owner-num">
                      {inr(p.amount)}
                      {large && !p.voided && (
                        <span
                          className="owner-chip owner-chip-red"
                          style={{ marginLeft: "0.4rem" }}
                          title="This amount is unusually large — check before trusting it"
                        >
                          Unusually large
                        </span>
                      )}
                      {p.voided && (
                        <div className="owner-void-note">
                          Voided: {p.void_reason} · {ddmmyyyy(p.voided_at)}
                          {p.voided_by ? ` · ${p.voided_by}` : ""}
                        </div>
                      )}
                    </td>
                    <td>{p.method}</td>
                    {isOwner && (
                      <td className="row-actions">
                        {p.voided ? (
                          <span className="owner-chip owner-chip-grey">
                            Voided
                          </span>
                        ) : (
                          <button
                            className="link-btn"
                            onClick={() => openVoid(p)}
                          >
                            Void
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      {/* Void dialog */}
      {voidTarget && (
        <div
          className="owner-drawer-backdrop"
          onClick={() => !voiding && setVoidTarget(null)}
        >
          <div
            className="owner-dialog"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-label="Void payment"
          >
            <h3>Void payment</h3>
            <p className="muted">
              {voidTarget.direction === "incoming" ? "Received" : "Paid"}{" "}
              {inr(voidTarget.amount)}
              {voidTarget.party ? ` · ${voidTarget.party}` : ""} ·{" "}
              {ddmmyyyy(voidTarget.paid_at)}
            </p>
            <p className="muted">
              Voiding keeps the record for the audit trail but removes it from
              all totals. This cannot be undone.
            </p>
            <form onSubmit={confirmVoid}>
              <label className="field">
                <span>Reason (required)</span>
                <input
                  autoFocus
                  value={voidReason}
                  onChange={(e) => setVoidReason(e.target.value)}
                  placeholder="e.g. duplicate test entry"
                />
              </label>
              <div className="form-actions" style={{ gap: "0.5rem" }}>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => setVoidTarget(null)}
                  disabled={voiding}
                >
                  Cancel
                </button>
                <button className="btn btn-primary btn-sm" disabled={voiding}>
                  {voiding ? "Voiding…" : "Void payment"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

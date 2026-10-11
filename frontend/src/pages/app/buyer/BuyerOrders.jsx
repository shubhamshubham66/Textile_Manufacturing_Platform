// Buyer: My Orders (+ reply to clarification, cancel/modify request, contact
// sales), Track Order, Invoices & Payments, Delivery History, Notifications,
// My Profile.
import { useState } from "react";
import { apiFetch } from "../../../lib/api.js";
import {
  Badge,
  Dialog,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Notice,
  PageHead,
  when,
  useApi,
} from "../../../components/super/kit.jsx";
import "../../../owner.css";

const n = (v) => Number(v || 0).toLocaleString("en-IN");
const rupee = (v) =>
  `₹${Number(v || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

// --------------------------------------------------------------------------- //
// My Orders.
// --------------------------------------------------------------------------- //
export function BuyerOrders() {
  const { data, error, loading, reload } = useApi("/api/buyer/orders", [
    "orders",
    "quality",
    "production",
  ]);
  const [reply, setReply] = useState(null);
  const [change, setChange] = useState(null);
  const [msg, setMsg] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const orders = data || [];
  return (
    <div className="module sm-page">
      <PageHead
        title="My orders"
        sub="Every order you have placed and its current stage."
      />
      <Notice onClose={() => setMsg("")}>{msg}</Notice>
      {orders.length === 0 ? (
        <Empty>You have no orders yet.</Empty>
      ) : (
        <section className="panel">
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Fabric</th>
                  <th className="num">Qty</th>
                  <th>Stage</th>
                  <th>Progress</th>
                  <th>Expected</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.id}>
                    <td>
                      <strong>{o.order_no}</strong>
                    </td>
                    <td>
                      {o.fabric_type} · {o.colour}
                    </td>
                    <td className="num">{n(o.quantity_meters)} m</td>
                    <td>
                      {o.review_label ? (
                        <Badge
                          value={
                            o.status === "rejected"
                              ? "rejected"
                              : "pending_review"
                          }
                          label={o.review_label}
                        />
                      ) : (
                        <Badge value="in_production" label={o.stage} />
                      )}
                      {o.review_note && (
                        <small className="sm-sub">
                          {o.status === "rejected" ? "Reason: " : "Question: "}
                          {o.review_note}
                        </small>
                      )}
                    </td>
                    <td>{o.progress_percent}%</td>
                    <td>{o.expected_delivery || "—"}</td>
                    <td>
                      <div className="sm-actions">
                        {o.status === "clarification" && (
                          <button
                            className="btn btn-primary btn-sm"
                            onClick={() => setReply(o)}
                          >
                            Reply
                          </button>
                        )}
                        {![
                          "dispatched",
                          "closed",
                          "rejected",
                          "cancelled",
                        ].includes(o.status) && (
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => setChange(o)}
                          >
                            Cancel / modify
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {reply && (
        <ReplyDialog
          order={reply}
          onClose={() => setReply(null)}
          onDone={(t) => {
            setReply(null);
            setMsg(t);
            reload();
          }}
        />
      )}
      {change && (
        <ChangeDialog
          order={change}
          onClose={() => setChange(null)}
          onDone={(t) => {
            setChange(null);
            setMsg(t);
          }}
        />
      )}
    </div>
  );
}

function ReplyDialog({ order, onClose, onDone }) {
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  const [qty, setQty] = useState(String(order.quantity_meters || ""));
  const [deadline, setDeadline] = useState(order.expected_delivery || "");
  const [note, setNote] = useState(order.buyer_note || "");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function go() {
    setBusy(true);
    setErr("");
    try {
      await apiFetch(`/api/buyer/orders/${order.id}`, {
        method: "PUT",
        body: {
          fabric_type: order.fabric_type,
          colour: order.colour,
          quantity_meters: Number(qty),
          deadline,
          note: note.trim() || null,
        },
      });
      onDone(`Reply sent for ${order.order_no}.`);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title={`Reply about ${order.order_no}`} onClose={onClose}>
      {order.review_note && (
        <p className="callout callout-warn">
          The mill asks: {order.review_note}
        </p>
      )}
      <ErrorBox error={err} />
      <Field label="Quantity (metres)">
        <input
          type="number"
          min="1"
          value={qty}
          onChange={(e) => setQty(e.target.value)}
        />
      </Field>
      <Field label="Needed by">
        <input
          type="date"
          min={tomorrow}
          value={deadline}
          onChange={(e) => setDeadline(e.target.value)}
        />
      </Field>
      <Field label="Note" wide>
        <textarea
          rows={2}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </Field>
      <div className="sm-row-end">
        <button className="btn btn-ghost btn-sm" onClick={onClose}>
          Cancel
        </button>
        <button className="btn btn-primary btn-sm" onClick={go} disabled={busy}>
          {busy ? "Sending…" : "Send reply"}
        </button>
      </div>
    </Dialog>
  );
}

function ChangeDialog({ order, onClose, onDone }) {
  const [kind, setKind] = useState("modify");
  const [message, setMessage] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function go() {
    if (message.trim().length < 3)
      return setErr("Explain what you'd like to change or cancel.");
    setBusy(true);
    setErr("");
    try {
      await apiFetch(`/api/buyer/orders/${order.id}/request-change`, {
        method: "POST",
        body: { kind, message: message.trim() },
      });
      onDone(
        `Your ${kind} request for ${order.order_no} was sent. A manager will review it.`,
      );
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title={`Request a change — ${order.order_no}`} onClose={onClose}>
      <p className="muted sm-small">
        This does not change your order automatically — a manager reviews your
        request.
      </p>
      <ErrorBox error={err} />
      <Field label="Type">
        <select
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          autoFocus
        >
          <option value="modify">Modify the order</option>
          <option value="cancel">Cancel the order</option>
        </select>
      </Field>
      <Field label="Details" wide>
        <textarea
          rows={3}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
      </Field>
      <div className="sm-row-end">
        <button className="btn btn-ghost btn-sm" onClick={onClose}>
          Cancel
        </button>
        <button className="btn btn-primary btn-sm" onClick={go} disabled={busy}>
          {busy ? "Sending…" : "Send request"}
        </button>
      </div>
    </Dialog>
  );
}

// --------------------------------------------------------------------------- //
// Track Order.
// --------------------------------------------------------------------------- //
export function BuyerTrack() {
  const { data, error, loading, reload } = useApi("/api/buyer/orders", [
    "orders",
    "quality",
    "production",
  ]);
  const [tracked, setTracked] = useState(null);
  const [terr, setTerr] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const trackable = (data || []).filter((o) => !o.review_label);

  async function track(id) {
    setTerr("");
    try {
      setTracked(await apiFetch(`/api/buyer/orders/${id}`));
    } catch (e) {
      setTerr(e.message);
    }
  }

  return (
    <div className="module sm-page">
      <PageHead
        title="Track order"
        sub="Follow an order from Confirmed through to Delivered."
      />
      <ErrorBox error={terr} />
      {tracked && (
        <section className="panel">
          <div className="sm-panel-head">
            <h3>
              {tracked.order_no} — {tracked.fabric_type} ({tracked.colour})
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
                className={`step-dot ${i < tracked.stage_index ? "done" : i === tracked.stage_index ? "current" : ""}`}
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
        {trackable.length === 0 ? (
          <Empty>No confirmed orders to track yet.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Fabric</th>
                  <th>Stage</th>
                  <th>Progress</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {trackable.map((o) => (
                  <tr key={o.id}>
                    <td>
                      <strong>{o.order_no}</strong>
                    </td>
                    <td>
                      {o.fabric_type} · {o.colour}
                    </td>
                    <td>
                      <Badge value="in_production" label={o.stage} />
                    </td>
                    <td>{o.progress_percent}%</td>
                    <td>
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => track(o.id)}
                      >
                        Track
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Invoices & Payments.
// --------------------------------------------------------------------------- //
export function BuyerInvoices() {
  const { data, error, loading, reload } = useApi("/api/buyer/invoices", [
    "payments",
    "orders",
  ]);
  const [payingId, setPayingId] = useState(null); // invoice being paid
  const [msg, setMsg] = useState(null); // {kind, text}

  async function payNow(inv) {
    setMsg(null);
    setPayingId(inv.id);
    try {
      const res = await apiFetch(`/api/buyer/invoices/${inv.id}/pay`, {
        method: "POST",
        body: { method: "bank" }, // full balance by default
      });
      setMsg({
        kind: "ok",
        text: `Payment of ${rupee(res.amount)} submitted for ${res.invoice_no}. Our accounts team will confirm it shortly.`,
      });
      await reload();
    } catch (e) {
      setMsg({ kind: "warn", text: e.message });
    } finally {
      setPayingId(null);
    }
  }

  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const invoices = data || [];
  return (
    <div className="module sm-page">
      <PageHead
        title="Invoices & payments"
        sub="Pay a confirmed order's invoice here. Your order is dispatched once the accounts team confirms full payment."
      />
      {msg && (
        <Notice kind={msg.kind} onClose={() => setMsg(null)}>
          {msg.text}
        </Notice>
      )}
      {invoices.length === 0 ? (
        <Empty>No invoices yet.</Empty>
      ) : (
        <section className="panel">
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Order</th>
                  <th className="num">Total</th>
                  <th className="num">Balance</th>
                  <th>Status</th>
                  <th>Date</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv) => (
                  <tr key={inv.id}>
                    <td>
                      <strong>{inv.invoice_no}</strong>
                    </td>
                    <td>{inv.order_no}</td>
                    <td className="num">{rupee(inv.total)}</td>
                    <td className="num">{rupee(inv.balance)}</td>
                    <td>
                      <Badge
                        value={
                          inv.status === "paid"
                            ? "ok"
                            : inv.status === "part_paid"
                              ? "waiting"
                              : "pending"
                        }
                        label={inv.status.replace("_", " ")}
                      />
                    </td>
                    <td>
                      {inv.created_at ? inv.created_at.slice(0, 10) : "—"}
                    </td>
                    <td className="row-actions">
                      {inv.payable && (
                        <button
                          className="btn btn-primary btn-sm"
                          disabled={payingId === inv.id}
                          onClick={() => payNow(inv)}
                        >
                          {payingId === inv.id ? "Submitting…" : "Pay now"}
                        </button>
                      )}
                      <a
                        className="link-btn"
                        href={`/api/buyer/invoices/${inv.id}/pdf`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        PDF
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted sm-small">
            After you pay, the mill's accounts team confirms the payment and
            then your order is dispatched.
          </p>
        </section>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Delivery History.
// --------------------------------------------------------------------------- //
export function BuyerDelivery() {
  const { data, error, loading, reload } = useApi("/api/buyer/deliveries", [
    "orders",
  ]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead
        title="Delivery history"
        sub="Your dispatches and deliveries with transport details."
      />
      {data.deliveries.length === 0 ? (
        <Empty>No dispatches yet.</Empty>
      ) : (
        <section className="panel">
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Dispatch</th>
                  <th>Order</th>
                  <th className="num">Rolls / m</th>
                  <th>Vehicle</th>
                  <th>Status</th>
                  <th>Delivered</th>
                </tr>
              </thead>
              <tbody>
                {data.deliveries.map((d, i) => (
                  <tr key={i}>
                    <td>
                      <strong>{d.dispatch_no}</strong>
                      <small className="sm-sub">{when(d.dispatched_at)}</small>
                    </td>
                    <td>{d.order_no}</td>
                    <td className="num">
                      {d.total_rolls} · {n(d.total_meters)} m
                    </td>
                    <td>
                      {d.vehicle_no || "—"}
                      <small className="sm-sub">{d.transporter || ""}</small>
                    </td>
                    <td>
                      <Badge
                        value={d.status === "Delivered" ? "ok" : "waiting"}
                        label={d.status}
                      />
                    </td>
                    <td>{d.delivered_at ? when(d.delivered_at) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Notifications.
// --------------------------------------------------------------------------- //
export function BuyerNotifications() {
  const { data, error, loading, reload } = useApi("/api/buyer/notifications", [
    "notifications",
    "orders",
    "quality",
    "payments",
  ]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;

  async function markRead(id) {
    try {
      await apiFetch(`/api/buyer/notifications/${id}/read`, { method: "POST" });
      reload();
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="module sm-page">
      <PageHead
        title="Notifications"
        sub={`${data.unread} unread · order, QC, dispatch and payment updates.`}
      />
      {data.notifications.length === 0 ? (
        <Empty>You're all caught up — no notifications.</Empty>
      ) : (
        <section className="panel">
          <ul className="sm-exceptions is-plain">
            {data.notifications.map((nt) => (
              <li key={nt.id} style={{ opacity: nt.read ? 0.6 : 1 }}>
                <strong>{nt.title}</strong>
                {nt.body ? ` — ${nt.body}` : ""}
                <small className="sm-sub">
                  {when(nt.created_at)}
                  {!nt.read && (
                    <button
                      className="link-btn"
                      onClick={() => markRead(nt.id)}
                      style={{ marginLeft: 8 }}
                    >
                      mark read
                    </button>
                  )}
                </small>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// My Profile (+ contact Sales & Dispatch).
// --------------------------------------------------------------------------- //
export function BuyerProfile() {
  const { data, error, loading, reload } = useApi("/api/buyer/profile", []);
  const [contact, setContact] = useState(false);
  const [msg, setMsg] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead title="My profile" sub="Your account and contact details.">
        <button
          className="btn btn-primary btn-sm"
          onClick={() => setContact(true)}
        >
          Contact Sales
        </button>
      </PageHead>
      <Notice onClose={() => setMsg("")}>{msg}</Notice>
      <section className="panel">
        <dl className="sm-mini">
          <div>
            <dt>Company</dt>
            <dd>{data.name}</dd>
          </div>
          <div>
            <dt>Contact person</dt>
            <dd>{data.contact_person || "—"}</dd>
          </div>
          <div>
            <dt>Phone</dt>
            <dd>{data.phone || "—"}</dd>
          </div>
          <div>
            <dt>Email</dt>
            <dd>{data.email || "—"}</dd>
          </div>
          <div>
            <dt>Login</dt>
            <dd>{data.login_email}</dd>
          </div>
          <div>
            <dt>Credit limit</dt>
            <dd>{rupee(data.credit_limit)}</dd>
          </div>
          <div>
            <dt>Total orders</dt>
            <dd>{data.total_orders}</dd>
          </div>
        </dl>
        {data.address && <p className="muted sm-small">{data.address}</p>}
      </section>
      {contact && (
        <ContactDialog
          onClose={() => setContact(false)}
          onDone={(t) => {
            setContact(false);
            setMsg(t);
          }}
        />
      )}
    </div>
  );
}

function ContactDialog({ onClose, onDone }) {
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function go() {
    if (subject.trim().length < 2) return setErr("Add a subject.");
    if (message.trim().length < 3) return setErr("Write your message.");
    setBusy(true);
    setErr("");
    try {
      await apiFetch("/api/buyer/inquiries", {
        method: "POST",
        body: { subject: subject.trim(), message: message.trim() },
      });
      onDone("Your message was sent to the Sales & Dispatch team.");
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title="Contact Sales & Dispatch" onClose={onClose}>
      <ErrorBox error={err} />
      <Field label="Subject">
        <input
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          autoFocus
        />
      </Field>
      <Field label="Message" wide>
        <textarea
          rows={3}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
      </Field>
      <div className="sm-row-end">
        <button className="btn btn-ghost btn-sm" onClick={onClose}>
          Cancel
        </button>
        <button className="btn btn-primary btn-sm" onClick={go} disabled={busy}>
          {busy ? "Sending…" : "Send message"}
        </button>
      </div>
    </Dialog>
  );
}

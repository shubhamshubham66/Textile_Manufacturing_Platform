import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../../lib/api.js";
import { inr, statusLabel } from "../../../lib/format.js";
import { Badge, Dialog, Empty, ErrorBox, Field, Loading, Notice, PageHead, day, useApi } from "../../../components/super/kit.jsx";
import "../../../owner.css";

// Order management: review buyer orders (yarn, capacity, deadline), confirm /
// reject / ask for clarification, create orders taken by phone, and track
// confirmed orders through production, QC and dispatch.
const TABS = [
  ["decide", "Needs decision", ["pending_review", "draft", "clarification"]],
  ["confirmed", "Confirmed", ["confirmed"]],
  ["production", "In production", ["in_production"]],
  ["qc", "QC", ["in_quality"]],
  ["ship", "Ready to ship", ["ready_to_ship"]],
  ["done", "Dispatched", ["dispatched", "closed"]],
  ["closed", "Rejected / cancelled", ["rejected", "cancelled"]],
  ["all", "All", null],
];
const DECIDABLE = ["pending_review", "draft", "clarification"];
const EDITABLE = ["draft", "pending_review", "clarification", "confirmed"];

export default function SuperOrders() {
  const { data: orders, error, loading, reload } = useApi("/api/orders", ["orders", "production", "quality"]);
  const [tab, setTab] = useState("decide");
  const [q, setQ] = useState("");
  const [review, setReview] = useState(null);
  const [track, setTrack] = useState(null);
  const [form, setForm] = useState(null); // {mode:'new'|'edit', order?}
  const [msg, setMsg] = useState(null);

  const rows = useMemo(() => {
    const list = orders || [];
    const t = TABS.find((x) => x[0] === tab);
    const s = q.trim().toLowerCase();
    return list.filter(
      (o) =>
        (!t[2] || t[2].includes(o.status)) &&
        (!s || `${o.order_no} ${o.buyer_name} ${o.fabric_type} ${o.colour}`.toLowerCase().includes(s)),
    );
  }, [orders, tab, q]);

  const count = (statuses) => (orders || []).filter((o) => !statuses || statuses.includes(o.status)).length;

  async function cancelOrder(o) {
    if (!window.confirm(`Cancel ${o.order_no}? It stays on record but leaves the pipeline.`)) return;
    try {
      await apiFetch(`/api/orders/${o.id}/cancel`, { method: "POST" });
      setMsg({ kind: "ok", text: `${o.order_no} cancelled.` });
      reload();
    } catch (err) {
      setMsg({ kind: "err", text: err.message });
    }
  }

  return (
    <div className="module sm-page">
      <PageHead title="Order management" sub="Review buyer orders, then confirm, reject or ask the buyer a question.">
        <button className="btn btn-primary" onClick={() => setForm({ mode: "new" })}>
          ＋ New order
        </button>
      </PageHead>
      <Notice kind={msg?.kind} onClose={() => setMsg(null)}>
        {msg?.text}
      </Notice>
      <ErrorBox error={error} onRetry={reload} />

      <section className="panel">
        <div className="sm-toolbar">
          <div className="sm-tabs" role="tablist">
            {TABS.map(([k, label, st]) => (
              <button
                key={k}
                role="tab"
                aria-selected={tab === k}
                className={tab === k ? "is-active" : ""}
                onClick={() => setTab(k)}
              >
                {label} <span className="sm-count">{count(st)}</span>
              </button>
            ))}
          </div>
          <input
            className="sm-search"
            type="search"
            placeholder="Search order, buyer, fabric…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Search orders"
          />
        </div>

        {loading && !orders ? (
          <Loading />
        ) : rows.length === 0 ? (
          <Empty>{tab === "decide" ? "No orders are waiting for a decision." : "No orders here."}</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Buyer</th>
                  <th>Fabric · colour</th>
                  <th className="num">Metres</th>
                  <th className="num">Rate</th>
                  <th>Deadline</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((o) => (
                  <tr key={o.id}>
                    <td className="sm-nowrap">
                      <strong>{o.order_no}</strong>
                    </td>
                    <td>{o.buyer_name}</td>
                    <td>
                      {o.fabric_type} · {o.colour}
                      {o.buyer_note && <small className="sm-sub">Buyer: {o.buyer_note}</small>}
                    </td>
                    <td className="num">{o.quantity_meters.toLocaleString("en-IN")}</td>
                    <td className="num">{o.unit_price ? inr(o.unit_price) : <span className="muted">not set</span>}</td>
                    <td>{day(o.deadline)}</td>
                    <td>
                      <Badge value={o.status} />
                      {o.review_note && ["rejected", "clarification"].includes(o.status) && (
                        <small className="sm-sub">{o.review_note}</small>
                      )}
                    </td>
                    <td>
                      <div className="sm-actions">
                        {DECIDABLE.includes(o.status) && (
                          <button className="btn btn-primary btn-sm" onClick={() => setReview(o)}>
                            Review
                          </button>
                        )}
                        <button className="btn btn-ghost btn-sm" onClick={() => setTrack(o)}>
                          Track
                        </button>
                        {EDITABLE.includes(o.status) && (
                          <>
                            <button className="btn btn-ghost btn-sm" onClick={() => setForm({ mode: "edit", order: o })}>
                              Edit
                            </button>
                            <button className="link-btn" onClick={() => cancelOrder(o)}>
                              Cancel
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {review && (
        <ReviewDialog
          order={review}
          onClose={() => setReview(null)}
          onDone={(text) => {
            setReview(null);
            setMsg({ kind: "ok", text });
            reload();
          }}
        />
      )}
      {track && <TrackDialog order={track} onClose={() => setTrack(null)} />}
      {form && (
        <OrderForm
          mode={form.mode}
          order={form.order}
          onClose={() => setForm(null)}
          onSaved={(o, mode) => {
            setForm(null);
            setMsg({ kind: "ok", text: mode === "new" ? `${o.order_no} created as a draft — review it to confirm.` : `${o.order_no} updated.` });
            reload();
          }}
        />
      )}
    </div>
  );
}

function ReviewDialog({ order, onClose, onDone }) {
  const [r, setR] = useState(null);
  const [err, setErr] = useState("");
  const [rate, setRate] = useState(order.unit_price || "");
  const [deadline, setDeadline] = useState(order.deadline || "");
  const [mode, setMode] = useState(null); // 'reject' | 'clarify'
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiFetch(`/api/orders/${order.id}/review`).then(setR).catch((e) => setErr(e.message));
  }, [order.id]);

  async function confirm() {
    setBusy(true);
    setErr("");
    try {
      const body = {};
      if (Number(rate) > 0) body.unit_price = Number(rate);
      if (deadline) body.deadline = deadline;
      const o = await apiFetch(`/api/orders/${order.id}/confirm`, { method: "POST", body });
      onDone(`${o.order_no} confirmed. Each department has its instruction.`);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function decide() {
    if (reason.trim().length < 3) {
      setErr(mode === "reject" ? "Give a reason for rejecting (at least 3 characters)." : "Write the question for the buyer.");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      const o = await apiFetch(`/api/orders/${order.id}/${mode}`, { method: "POST", body: { reason: reason.trim() } });
      onDone(mode === "reject" ? `${o.order_no} rejected.` : `${o.order_no} sent back to the buyer for clarification.`);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  // Missing info the form fields here can fill.
  const stillMissing = r
    ? r.missing.filter(
        (m) => !(m.startsWith("rate") && Number(rate) > 0) && !(m.includes("deadline") && deadline && deadline > new Date().toISOString().slice(0, 10)),
      )
    : [];

  return (
    <Dialog title={`Review ${order.order_no}`} onClose={onClose} wide>
      {!r && !err && <Loading text="Checking yarn, capacity and the deadline…" />}
      <ErrorBox error={err} />
      {r && (
        <>
          <dl className="sm-facts">
            <div>
              <dt>Buyer</dt>
              <dd>{r.order.buyer_name}</dd>
            </div>
            <div>
              <dt>Fabric</dt>
              <dd>
                {r.order.fabric_type} · {r.order.colour}
              </dd>
            </div>
            <div>
              <dt>Quantity</dt>
              <dd>{r.order.quantity_meters.toLocaleString("en-IN")} m</dd>
            </div>
            <div>
              <dt>Deadline</dt>
              <dd>{day(r.order.deadline)}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>
                <Badge value={r.order.status} />
              </dd>
            </div>
          </dl>
          {r.order.buyer_note && <p className="sm-quote">Buyer's note: {r.order.buyer_note}</p>}

          <div className="sm-checks">
            <Check ok={r.yarn.enough} title="Raw material (yarn)">
              {r.yarn.message}
              {!r.yarn.enough && " Confirming will send Purchase an urgent instruction."}
            </Check>
            <Check ok={r.capacity.ok} title="Production capacity">
              {r.capacity.message}
            </Check>
            <Check ok={stillMissing.length === 0} title="Required information">
              {stillMissing.length === 0 ? "Everything needed to confirm is filled in." : `Missing: ${stillMissing.join(", ")}.`}
            </Check>
          </div>

          {r.can_decide ? (
            <>
              <div className="form-grid sm-form">
                <Field label="Rate (₹ per metre)">
                  <input type="number" min="0" step="0.5" value={rate} onChange={(e) => setRate(e.target.value)} />
                </Field>
                <Field label="Delivery deadline">
                  <input type="date" value={deadline || ""} onChange={(e) => setDeadline(e.target.value)} />
                </Field>
              </div>

              {mode ? (
                <div className="sm-decide">
                  <Field label={mode === "reject" ? "Reason for rejecting (the buyer sees this)" : "Question for the buyer"} wide>
                    <textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
                  </Field>
                  <div className="sm-row-end">
                    <button className="btn btn-ghost btn-sm" onClick={() => setMode(null)} disabled={busy}>
                      Back
                    </button>
                    <button className={`btn btn-sm ${mode === "reject" ? "btn-danger" : "btn-primary"}`} onClick={decide} disabled={busy}>
                      {mode === "reject" ? "Reject order" : "Send question"}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="sm-row-end">
                  <button className="btn btn-ghost btn-sm" onClick={() => setMode("clarify")} disabled={busy || order.status === "clarification"}>
                    Ask for clarification
                  </button>
                  <button className="btn btn-ghost btn-sm sm-danger-text" onClick={() => setMode("reject")} disabled={busy}>
                    Reject
                  </button>
                  <button className="btn btn-primary btn-sm" onClick={confirm} disabled={busy || stillMissing.length > 0}>
                    {busy ? "Confirming…" : "Confirm order"}
                  </button>
                </div>
              )}
              {order.status === "clarification" && (
                <p className="muted sm-small">Waiting for the buyer's reply to: “{order.review_note}”.</p>
              )}
            </>
          ) : (
            <p className="muted">This order is {statusLabel(r.order.status).toLowerCase()} — no decision is needed.</p>
          )}
        </>
      )}
    </Dialog>
  );
}

function Check({ ok, title, children }) {
  return (
    <div className={`sm-check ${ok ? "is-ok" : "is-warn"}`}>
      <span aria-hidden>{ok ? "✓" : "!"}</span>
      <div>
        <strong>{title}</strong>
        <p>{children}</p>
      </div>
    </div>
  );
}

function TrackDialog({ order, onClose }) {
  const [t, setT] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    apiFetch(`/api/orders/${order.id}/track`).then(setT).catch((e) => setErr(e.message));
  }, [order.id]);
  const flow = ["confirmed", "in_production", "in_quality", "ready_to_ship", "dispatched", "closed"];
  const at = t ? flow.indexOf(t.status) : -1;
  return (
    <Dialog title={`Track ${order.order_no}`} onClose={onClose} wide>
      <ErrorBox error={err} />
      {!t && !err && <Loading />}
      {t && (
        <>
          <ol className="sm-stepper">
            {flow.map((s, i) => (
              <li key={s} className={i < at ? "is-done" : i === at ? "is-now" : ""}>
                {statusLabel(s)}
              </li>
            ))}
          </ol>
          <p>
            {t.progress_percent}% made · due {day(t.deadline)} {t.late && <Badge value="delayed" label="Late" />}
          </p>
          {t.rolls.length === 0 ? (
            <Empty>No rolls made yet.</Empty>
          ) : (
            <div className="owner-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Roll</th>
                    <th className="num">Metres</th>
                    <th>Machine</th>
                    <th>QC</th>
                    <th>Defect</th>
                  </tr>
                </thead>
                <tbody>
                  {t.rolls.map((r) => (
                    <tr key={r.roll_no}>
                      <td>{r.roll_no}</td>
                      <td className="num">{r.length_meters}</td>
                      <td>{r.machine}</td>
                      <td>
                        <Badge value={r.result} />
                      </td>
                      <td>{r.defect_type === "none" ? "—" : r.defect_type}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </Dialog>
  );
}

function OrderForm({ mode, order, onClose, onSaved }) {
  const [buyers, setBuyers] = useState([]);
  const [f, setF] = useState({
    buyer_id: order?.buyer_id || "",
    fabric_type: order?.fabric_type || "",
    colour: order?.colour || "",
    quantity_meters: order?.quantity_meters || "",
    unit_price: order?.unit_price || "",
    deadline: order?.deadline || "",
  });
  const [errs, setErrs] = useState({});
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    apiFetch("/api/orders/_meta/buyers").then(setBuyers).catch((e) => setErr(e.message));
  }, []);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    const x = {};
    if (!f.buyer_id) x.buyer_id = "Choose a buyer.";
    if (!f.fabric_type.trim()) x.fabric_type = "Enter the fabric.";
    if (!f.colour.trim()) x.colour = "Enter the colour.";
    if (!(Number(f.quantity_meters) > 0)) x.quantity_meters = "Enter metres above 0.";
    if (f.unit_price !== "" && Number(f.unit_price) < 0) x.unit_price = "Rate cannot be negative.";
    setErrs(x);
    if (Object.keys(x).length) return;
    setBusy(true);
    setErr("");
    try {
      const body = {
        buyer_id: Number(f.buyer_id),
        fabric_type: f.fabric_type.trim(),
        colour: f.colour.trim(),
        quantity_meters: Number(f.quantity_meters),
        unit_price: Number(f.unit_price || 0),
        deadline: f.deadline || null,
      };
      const o =
        mode === "new"
          ? await apiFetch("/api/orders", { method: "POST", body })
          : await apiFetch(`/api/orders/${order.id}`, { method: "PUT", body });
      onSaved(o, mode);
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog title={mode === "new" ? "New order" : `Edit ${order.order_no}`} onClose={onClose}>
      <ErrorBox error={err} />
      <form className="form-grid sm-form" onSubmit={submit} noValidate>
        <Field label="Buyer" error={errs.buyer_id}>
          <select value={f.buyer_id} onChange={set("buyer_id")}>
            <option value="">Choose a buyer…</option>
            {buyers.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Fabric type" error={errs.fabric_type}>
          <input value={f.fabric_type} onChange={set("fabric_type")} placeholder="Cotton Shirting" />
        </Field>
        <Field label="Colour" error={errs.colour}>
          <input value={f.colour} onChange={set("colour")} placeholder="White" />
        </Field>
        <Field label="Quantity (metres)" error={errs.quantity_meters}>
          <input type="number" min="0" value={f.quantity_meters} onChange={set("quantity_meters")} />
        </Field>
        <Field label="Rate (₹/metre)" error={errs.unit_price}>
          <input type="number" min="0" step="0.5" value={f.unit_price} onChange={set("unit_price")} />
        </Field>
        <Field label="Delivery deadline">
          <input type="date" value={f.deadline || ""} onChange={set("deadline")} />
        </Field>
        <div className="sm-row-end sm-wide">
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary btn-sm" disabled={busy}>
            {busy ? "Saving…" : mode === "new" ? "Create order" : "Save changes"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

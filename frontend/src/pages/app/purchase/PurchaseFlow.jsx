// Purchase requests → purchase orders → material receiving.
import { useMemo, useState } from "react";
import { apiFetch } from "../../../lib/api.js";
import { inr } from "../../../lib/format.js";
import { Badge, Dialog, Empty, ErrorBox, Field, Loading, Notice, PageHead, Stat, day, when, useApi } from "../../../components/super/kit.jsx";
import "../../../owner.css";

const kg = (v) => `${Number(v || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })} kg`;
const today = () => new Date().toISOString().slice(0, 10);

const PR_TONE = { pending: "waiting", approved: "info", rejected: "critical", ordered: "ok", received: "ok", cancelled: "inactive" };
const PR_LABEL = { pending: "Waiting approval", approved: "Approved", rejected: "Rejected", ordered: "Ordered", received: "Received", cancelled: "Cancelled" };
export const PrBadge = ({ s }) => <Badge value={PR_TONE[s] || "info"} label={PR_LABEL[s] || s} />;
const PO_TONE = { raised: "info", partial: "waiting", received: "ok", cancelled: "inactive" };
const PO_LABEL = { raised: "Ordered", partial: "Part delivered", received: "Received", cancelled: "Cancelled" };
const PoBadge = ({ s }) => <Badge value={PO_TONE[s] || "info"} label={PO_LABEL[s] || s} />;
const RC_TONE = { recorded: "waiting", validated: "ok", rejected: "critical" };
const RC_LABEL = { recorded: "To validate", validated: "Validated", rejected: "Rejected" };

// --------------------------------------------------------------------------- //
export function PurchaseRequests() {
  const [status, setStatus] = useState("");
  const { data, error, loading, reload } = useApi(`/api/purchase/requests${status ? `?status=${status}` : ""}`, ["purchase", "tasks"]);
  const [form, setForm] = useState(null);
  const [msg, setMsg] = useState(null);

  async function cancel(r) {
    if (!window.confirm(`Cancel ${r.pr_no}? It stays on record.`)) return;
    try {
      await apiFetch(`/api/purchase/requests/${r.id}/cancel`, { method: "POST" });
      setMsg({ kind: "ok", text: `${r.pr_no} cancelled.` });
      reload();
    } catch (e) {
      setMsg({ kind: "err", text: e.message });
    }
  }

  return (
    <div className="module sm-page">
      <PageHead title="Purchase requests" sub={data?.workflow}>
        <button className="btn btn-primary" onClick={() => setForm({ source: "manual" })}>
          ＋ New request
        </button>
      </PageHead>
      <Notice kind={msg?.kind} onClose={() => setMsg(null)}>
        {msg?.text}
      </Notice>
      <ErrorBox error={error} onRetry={reload} />

      <section className="panel">
        <h3>Instructions from the Supermanager</h3>
        {!data ? (
          <Loading />
        ) : data.instructions.length === 0 ? (
          <Empty>No open purchase instructions.</Empty>
        ) : (
          <ul className="sm-tasklist">
            {data.instructions.map((t) => (
              <li key={t.id} className={`is-${t.status}`}>
                <div>
                  <strong>{t.title}</strong>
                  {t.details && <p className="muted">{t.details}</p>}
                  <small className="muted">Due {day(t.deadline)}</small>
                </div>
                <div className="sm-task-side">
                  <Badge value={t.priority} />
                  <Badge value={t.status} />
                  {t.has_request ? (
                    <Badge value="ok" label="Request made" />
                  ) : (
                    <button className="btn btn-primary btn-sm" onClick={() => setForm({ source: "instruction", task: t })}>
                      Create request
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel">
        <div className="sm-toolbar">
          <h3>Requests</h3>
          <select className="sm-select" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">
            <option value="">All statuses</option>
            {Object.entries(PR_LABEL).map(([k, l]) => (
              <option key={k} value={k}>
                {l}
              </option>
            ))}
          </select>
        </div>
        {loading && !data ? (
          <Loading />
        ) : data.requests.length === 0 ? (
          <Empty>No purchase requests yet.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Request</th>
                  <th>Yarn</th>
                  <th className="num">Quantity</th>
                  <th>Needed by</th>
                  <th>Why</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.requests.map((r) => (
                  <tr key={r.id}>
                    <td className="sm-nowrap">
                      <strong>{r.pr_no}</strong>
                      <small className="sm-sub">{when(r.created_at)}</small>
                    </td>
                    <td>
                      {r.yarn_type} · {r.colour}
                    </td>
                    <td className="num">{kg(r.quantity_kg)}</td>
                    <td>{day(r.required_date)}</td>
                    <td>
                      {r.reason || <span className="muted">—</span>}
                      <small className="sm-sub">
                        {{ low_stock: "From a low-stock alert", instruction: "From a Supermanager instruction", order: "For an order", manual: "Manual" }[r.source]}
                        {r.order_no ? ` · ${r.order_no}` : ""}
                      </small>
                    </td>
                    <td>
                      <PrBadge s={r.status} />
                      {r.decision_note && <small className="sm-sub">{r.decided_by ? `${r.decided_by}: ` : ""}{r.decision_note}</small>}
                      {r.po_no && <small className="sm-sub">{r.po_no}</small>}
                    </td>
                    <td>
                      {["pending", "approved"].includes(r.status) && (
                        <button className="link-btn" onClick={() => cancel(r)}>
                          Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {form && (
        <RequestForm
          preset={form}
          onClose={() => setForm(null)}
          onSaved={(r) => {
            setForm(null);
            setMsg({ kind: "ok", text: r.status === "approved" ? `${r.pr_no} approved automatically — raise the purchase order.` : `${r.pr_no} sent to the Supermanager for approval.` });
            reload();
          }}
        />
      )}
    </div>
  );
}

export function RequestForm({ preset, onClose, onSaved }) {
  const [f, setF] = useState({
    yarn_type: preset.yarn_type || "",
    colour: preset.colour || "",
    quantity_kg: preset.quantity_kg || "",
    required_date: preset.required_date || preset.task?.deadline || "",
    reason: preset.reason || preset.task?.title || "",
  });
  const [errs, setErrs] = useState({});
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  async function submit(e) {
    e.preventDefault();
    const x = {};
    if (!f.yarn_type.trim()) x.yarn_type = "Enter the yarn type.";
    if (!f.colour.trim()) x.colour = "Enter the colour.";
    if (!(Number(f.quantity_kg) > 0)) x.quantity_kg = "Enter kg above 0.";
    if (f.required_date && f.required_date < today()) x.required_date = "Cannot be in the past.";
    setErrs(x);
    if (Object.keys(x).length) return;
    setBusy(true);
    setErr("");
    try {
      const r = await apiFetch("/api/purchase/requests", {
        method: "POST",
        body: {
          yarn_type: f.yarn_type.trim(),
          colour: f.colour.trim(),
          quantity_kg: Number(f.quantity_kg),
          required_date: f.required_date || null,
          reason: f.reason.trim() || null,
          source: preset.source || "manual",
          task_id: preset.task?.id || null,
          order_id: preset.task?.order_id || preset.order_id || null,
        },
      });
      onSaved(r);
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title="New purchase request" onClose={onClose}>
      {preset.task && <p className="sm-quote">Instruction: {preset.task.title}</p>}
      <ErrorBox error={err} />
      <form className="form-grid sm-form" onSubmit={submit} noValidate>
        <Field label="Yarn type" error={errs.yarn_type}>
          <input value={f.yarn_type} onChange={set("yarn_type")} placeholder="Cotton 40s" />
        </Field>
        <Field label="Colour" error={errs.colour}>
          <input value={f.colour} onChange={set("colour")} placeholder="Blue" />
        </Field>
        <Field label="Quantity (kg)" error={errs.quantity_kg}>
          <input type="number" min="0" value={f.quantity_kg} onChange={set("quantity_kg")} />
        </Field>
        <Field label="Needed by" error={errs.required_date}>
          <input type="date" min={today()} value={f.required_date} onChange={set("required_date")} />
        </Field>
        <Field label="Reason" wide>
          <input value={f.reason} onChange={set("reason")} placeholder="Why this yarn is needed" />
        </Field>
        <div className="sm-row-end sm-wide">
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary btn-sm" disabled={busy}>
            {busy ? "Sending…" : "Send for approval"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

// --------------------------------------------------------------------------- //
export function PurchaseOrders() {
  const [status, setStatus] = useState("");
  const { data, error, loading, reload } = useApi(`/api/purchase/orders${status ? `?status=${status}` : ""}`, ["purchase"]);
  const [form, setForm] = useState(null);
  const [msg, setMsg] = useState(null);
  const orders = data?.orders || [];

  async function cancel(p) {
    if (!window.confirm(`Cancel ${p.po_no}? The request goes back to approved so it can be ordered again.`)) return;
    try {
      await apiFetch(`/api/purchase/orders/${p.id}/cancel`, { method: "POST" });
      setMsg({ kind: "ok", text: `${p.po_no} cancelled.` });
      reload();
    } catch (e) {
      setMsg({ kind: "err", text: e.message });
    }
  }

  return (
    <div className="module sm-page">
      <PageHead title="Purchase orders" sub="Only approved purchase requests can become purchase orders." />
      <Notice kind={msg?.kind} onClose={() => setMsg(null)}>
        {msg?.text}
      </Notice>
      <ErrorBox error={error} onRetry={reload} />
      <section className="panel">
        <h3>Approved requests ready to order</h3>
        {!data ? (
          <Loading />
        ) : data.approved_requests.length === 0 ? (
          <Empty>No approved requests waiting. New requests need Supermanager approval first.</Empty>
        ) : (
          <ul className="sm-tasklist">
            {data.approved_requests.map((r) => (
              <li key={r.id}>
                <div>
                  <strong>
                    {r.pr_no} · {kg(r.quantity_kg)} {r.yarn_type} {r.colour}
                  </strong>
                  <small className="muted">
                    Needed by {day(r.required_date)} · approved by {r.decided_by || "auto-approval"}
                  </small>
                </div>
                <div className="sm-task-side">
                  <button className="btn btn-primary btn-sm" onClick={() => setForm(r)}>
                    Create purchase order
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="panel">
        <div className="sm-toolbar">
          <h3>Purchase orders</h3>
          <select className="sm-select" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">
            <option value="">All</option>
            <option value="open">Open (ordered or part delivered)</option>
            <option value="received">Received</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>
        {loading && !data ? (
          <Loading />
        ) : orders.length === 0 ? (
          <Empty>No purchase orders.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>PO</th>
                  <th>Supplier</th>
                  <th>Yarn</th>
                  <th className="num">Rate · tax</th>
                  <th className="num">Total</th>
                  <th>Delivery</th>
                  <th>Received</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {orders.map((p) => (
                  <tr key={p.id}>
                    <td className="sm-nowrap">
                      <strong>{p.po_no}</strong>
                      <small className="sm-sub">{p.pr_no || "before requests"}</small>
                    </td>
                    <td>{p.supplier}</td>
                    <td>
                      {p.yarn_type} · {p.colour}
                    </td>
                    <td className="num">
                      {inr(p.unit_cost)}/kg
                      <small className="sm-sub">{p.tax_percent}% tax</small>
                    </td>
                    <td className="num">{inr(p.total)}</td>
                    <td>
                      {day(p.expected_date)} {p.late && <Badge value="delayed" label="Late" />}
                    </td>
                    <td>
                      <span className="sm-progress" title={`${p.received_kg} of ${p.quantity_kg} kg`}>
                        <i style={{ width: `${Math.min(100, (p.received_kg / p.quantity_kg) * 100)}%` }} />
                      </span>
                      <small className="sm-sub">
                        {kg(p.received_kg)} of {kg(p.quantity_kg)}
                      </small>
                    </td>
                    <td>
                      <PoBadge s={p.status} />
                      {p.receipts_waiting > 0 && <small className="sm-sub">{p.receipts_waiting} delivery to validate</small>}
                    </td>
                    <td>
                      {p.status === "raised" && p.received_kg === 0 && (
                        <button className="link-btn" onClick={() => cancel(p)}>
                          Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {form && (
        <PoForm
          pr={form}
          suppliers={data?.suppliers || []}
          onClose={() => setForm(null)}
          onSaved={(p) => {
            setForm(null);
            setMsg({ kind: "ok", text: `${p.po_no} sent to ${p.supplier} — ${inr(p.total)}.` });
            reload();
          }}
        />
      )}
    </div>
  );
}

function PoForm({ pr, suppliers, onClose, onSaved }) {
  const match = suppliers.filter((s) => (s.yarn_types || "").toLowerCase().includes(pr.yarn_type.toLowerCase()));
  const [f, setF] = useState({ supplier_id: match[0]?.id || "", quantity_kg: pr.quantity_kg, unit_cost: "", tax_percent: "5", expected_date: pr.required_date || "" });
  const [errs, setErrs] = useState({});
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const sub = Number(f.quantity_kg || 0) * Number(f.unit_cost || 0);
  const total = sub * (1 + Number(f.tax_percent || 0) / 100);
  async function submit(e) {
    e.preventDefault();
    const x = {};
    if (!f.supplier_id) x.supplier_id = "Choose a supplier.";
    if (!(Number(f.quantity_kg) > 0)) x.quantity_kg = "Enter kg above 0.";
    else if (Number(f.quantity_kg) > pr.quantity_kg * 1.1) x.quantity_kg = `At most ${kg(pr.quantity_kg * 1.1)} (approved + 10%).`;
    if (!(Number(f.unit_cost) > 0)) x.unit_cost = "Enter the price per kg.";
    if (Number(f.tax_percent) < 0 || Number(f.tax_percent) > 40) x.tax_percent = "0–40%.";
    if (!f.expected_date || f.expected_date < today()) x.expected_date = "Choose a delivery date from today.";
    setErrs(x);
    if (Object.keys(x).length) return;
    setBusy(true);
    setErr("");
    try {
      const p = await apiFetch("/api/purchase/orders", {
        method: "POST",
        body: {
          purchase_request_id: pr.id,
          supplier_id: Number(f.supplier_id),
          quantity_kg: Number(f.quantity_kg),
          unit_cost: Number(f.unit_cost),
          tax_percent: Number(f.tax_percent || 0),
          expected_date: f.expected_date,
        },
      });
      onSaved(p);
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title={`Purchase order for ${pr.pr_no}`} onClose={onClose}>
      <p className="muted">
        {kg(pr.quantity_kg)} {pr.yarn_type} {pr.colour} approved.
      </p>
      <ErrorBox error={err} />
      <form className="form-grid sm-form" onSubmit={submit} noValidate>
        <Field label="Supplier" error={errs.supplier_id} wide>
          <select value={f.supplier_id} onChange={set("supplier_id")}>
            <option value="">Choose…</option>
            {suppliers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
                {s.yarn_types ? ` — ${s.yarn_types}` : ""}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Quantity (kg)" error={errs.quantity_kg}>
          <input type="number" min="0" value={f.quantity_kg} onChange={set("quantity_kg")} />
        </Field>
        <Field label="Price (₹ per kg)" error={errs.unit_cost}>
          <input type="number" min="0" step="0.5" value={f.unit_cost} onChange={set("unit_cost")} />
        </Field>
        <Field label="Tax (%)" error={errs.tax_percent}>
          <input type="number" min="0" max="40" step="0.5" value={f.tax_percent} onChange={set("tax_percent")} />
        </Field>
        <Field label="Delivery date" error={errs.expected_date}>
          <input type="date" min={today()} value={f.expected_date} onChange={set("expected_date")} />
        </Field>
        <p className="sm-wide sm-total">
          Subtotal {inr(sub)} · tax {inr(total - sub)} · <strong>Total {inr(total)}</strong>
        </p>
        <div className="sm-row-end sm-wide">
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary btn-sm" disabled={busy}>
            {busy ? "Sending…" : "Create purchase order"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

// --------------------------------------------------------------------------- //
export function MaterialReceiving() {
  const [status, setStatus] = useState("");
  const { data, error, loading, reload } = useApi(`/api/purchase/receipts${status ? `?status=${status}` : ""}`, ["purchase", "yarn"]);
  const [form, setForm] = useState(null);
  const [check, setCheck] = useState(null);
  const [msg, setMsg] = useState(null);
  const rows = data?.receipts || [];
  const waiting = useMemo(() => rows.filter((r) => r.status === "recorded"), [rows]);
  const flagged = rows.filter((r) => r.discrepancy);

  return (
    <div className="module sm-page">
      <PageHead title="Material receiving" sub="Record what actually arrived. Stock goes up only after the delivery is validated.">
        <button className="btn btn-primary" onClick={() => setForm({})}>
          ＋ Record delivery
        </button>
      </PageHead>
      <Notice kind={msg?.kind} onClose={() => setMsg(null)}>
        {msg?.text}
      </Notice>
      <ErrorBox error={error} onRetry={reload} />
      {data && (
        <div className="sm-stats sm-stats-4">
          <Stat label="Waiting for validation" value={waiting.length} tone={waiting.length ? "amber" : undefined} />
          <Stat label="Deliveries with discrepancies" value={flagged.length} tone={flagged.length ? "red" : undefined} />
          <Stat label="Open purchase orders" value={data.open_pos.length} />
          <Stat label="Deliveries shown" value={rows.length} />
        </div>
      )}
      <section className="panel">
        <div className="sm-toolbar">
          <h3>Deliveries</h3>
          <select className="sm-select" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">
            <option value="">All</option>
            <option value="recorded">To validate</option>
            <option value="validated">Validated</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>
        {loading && !data ? (
          <Loading />
        ) : rows.length === 0 ? (
          <Empty>No deliveries recorded.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Received</th>
                  <th>PO · supplier</th>
                  <th>Yarn · batch</th>
                  <th className="num">Qty (damaged)</th>
                  <th>Discrepancy</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className={r.discrepancy && r.status === "recorded" ? "row-warn" : ""}>
                    <td className="sm-nowrap">
                      {when(r.received_at)}
                      <small className="sm-sub">#{r.id}</small>
                    </td>
                    <td>
                      {r.po_no || <span className="muted">no PO</span>}
                      <small className="sm-sub">{r.supplier || "—"}</small>
                    </td>
                    <td>
                      {r.yarn_type} · {r.colour}
                      <small className="sm-sub">{r.batch_no ? `Batch ${r.batch_no}` : "No batch"}</small>
                    </td>
                    <td className="num">
                      {kg(r.quantity_kg)}
                      {r.damaged_kg > 0 && <small className="sm-sub sm-neg">{kg(r.damaged_kg)} damaged</small>}
                    </td>
                    <td>
                      {r.discrepancy ? (
                        <>
                          {r.discrepancy.split(",").map((d) => (
                            <Badge key={d} value={d === "excess" ? "warning" : "critical"} label={d} />
                          ))}
                          <small className="sm-sub">{r.discrepancy_note}</small>
                        </>
                      ) : (
                        <span className="muted">{r.discrepancy_note || "Matches"}</span>
                      )}
                    </td>
                    <td>
                      <Badge value={RC_TONE[r.status]} label={RC_LABEL[r.status] || r.status} />
                      {r.validated_by && <small className="sm-sub">{r.validated_by}</small>}
                    </td>
                    <td>
                      {r.status === "recorded" && (
                        <button className="btn btn-primary btn-sm" onClick={() => setCheck(r)}>
                          Review
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {form && (
        <ReceiptForm
          data={data}
          onClose={() => setForm(null)}
          onSaved={(r) => {
            setForm(null);
            setMsg({ kind: r.discrepancy ? "err" : "ok", text: r.discrepancy ? `Delivery #${r.id} recorded and flagged: ${r.discrepancy_note}. Review it before it enters stock.` : `Delivery #${r.id} recorded — validate it to add it to stock.` });
            reload();
          }}
        />
      )}
      {check && (
        <ValidateDialog
          r={check}
          onClose={() => setCheck(null)}
          onDone={(text) => {
            setCheck(null);
            setMsg({ kind: "ok", text });
            reload();
          }}
        />
      )}
    </div>
  );
}

function ReceiptForm({ data, onClose, onSaved }) {
  const [f, setF] = useState({ purchase_order_id: "", supplier_id: "", yarn_type: "", colour: "", quantity_kg: "", damaged_kg: "0", batch_no: "", received_date: today(), note: "" });
  const [errs, setErrs] = useState({});
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const po = data.open_pos.find((p) => String(p.id) === String(f.purchase_order_id));
  function pickPo(e) {
    const p = data.open_pos.find((x) => String(x.id) === e.target.value);
    setF({ ...f, purchase_order_id: e.target.value, yarn_type: p?.yarn_type || f.yarn_type, colour: p?.colour || f.colour, quantity_kg: p ? String(p.outstanding_kg) : f.quantity_kg });
  }
  async function submit(e) {
    e.preventDefault();
    const x = {};
    if (!f.yarn_type.trim()) x.yarn_type = "Enter the yarn type.";
    if (!f.colour.trim()) x.colour = "Enter the colour.";
    if (!(Number(f.quantity_kg) > 0)) x.quantity_kg = "Enter the kg received.";
    if (Number(f.damaged_kg) < 0 || Number(f.damaged_kg) > Number(f.quantity_kg)) x.damaged_kg = "0 up to the quantity received.";
    if (!f.batch_no.trim()) x.batch_no = "Enter the batch number on the bags.";
    if (!f.received_date || f.received_date > today()) x.received_date = "Today or earlier.";
    setErrs(x);
    if (Object.keys(x).length) return;
    setBusy(true);
    setErr("");
    try {
      const r = await apiFetch("/api/purchase/receipts", {
        method: "POST",
        body: {
          purchase_order_id: f.purchase_order_id ? Number(f.purchase_order_id) : null,
          supplier_id: !f.purchase_order_id && f.supplier_id ? Number(f.supplier_id) : null,
          yarn_type: f.yarn_type.trim(),
          colour: f.colour.trim(),
          quantity_kg: Number(f.quantity_kg),
          damaged_kg: Number(f.damaged_kg || 0),
          batch_no: f.batch_no.trim(),
          received_date: f.received_date,
          note: f.note.trim() || null,
        },
      });
      onSaved(r);
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title="Record a delivery" onClose={onClose} wide>
      <ErrorBox error={err} />
      <form className="form-grid sm-form" onSubmit={submit} noValidate>
        <Field label="Against purchase order" wide>
          <select value={f.purchase_order_id} onChange={pickPo}>
            <option value="">No purchase order</option>
            {data.open_pos.map((p) => (
              <option key={p.id} value={p.id}>
                {p.po_no} · {p.supplier} · {p.yarn_type} {p.colour} · {kg(p.outstanding_kg)} still due
              </option>
            ))}
          </select>
        </Field>
        {!f.purchase_order_id && (
          <Field label="Supplier" wide>
            <select value={f.supplier_id} onChange={set("supplier_id")}>
              <option value="">Not known</option>
              {data.suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </Field>
        )}
        <Field label="Yarn type" error={errs.yarn_type}>
          <input value={f.yarn_type} onChange={set("yarn_type")} />
        </Field>
        <Field label="Colour" error={errs.colour}>
          <input value={f.colour} onChange={set("colour")} />
        </Field>
        <Field label="Quantity received (kg)" error={errs.quantity_kg}>
          <input type="number" min="0" value={f.quantity_kg} onChange={set("quantity_kg")} />
        </Field>
        <Field label="Damaged (kg)" error={errs.damaged_kg}>
          <input type="number" min="0" value={f.damaged_kg} onChange={set("damaged_kg")} />
        </Field>
        <Field label="Batch number" error={errs.batch_no}>
          <input value={f.batch_no} onChange={set("batch_no")} placeholder="B-2026-114" />
        </Field>
        <Field label="Received on" error={errs.received_date}>
          <input type="date" max={today()} value={f.received_date} onChange={set("received_date")} />
        </Field>
        <Field label="Note" wide>
          <input value={f.note} onChange={set("note")} placeholder="Truck no., condition of bags…" />
        </Field>
        {po && (
          <p className="sm-wide muted sm-small">
            {po.po_no} still expects {kg(po.outstanding_kg)} of {po.yarn_type} {po.colour}. Shortages, extra quantity, wrong yarn and damage are flagged automatically.
          </p>
        )}
        <div className="sm-row-end sm-wide">
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary btn-sm" disabled={busy}>
            {busy ? "Saving…" : "Record delivery"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

function ValidateDialog({ r, onClose, onDone }) {
  const [note, setNote] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function decide(accept) {
    if (!accept && note.trim().length < 3) return setErr("Write why the delivery is rejected.");
    if (accept && r.discrepancy && !window.confirm(`This delivery is flagged (${r.discrepancy}). Accept ${kg(r.accepted_kg)} into stock anyway?`)) return;
    setBusy(true);
    setErr("");
    try {
      await apiFetch(`/api/purchase/receipts/${r.id}/validate`, { method: "POST", body: { accept, note: note.trim() || null } });
      onDone(accept ? `${kg(r.accepted_kg)} ${r.yarn_type} ${r.colour} added to stock.` : `Delivery #${r.id} rejected — nothing added to stock.`);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title={`Validate delivery #${r.id}`} onClose={onClose}>
      <dl className="sm-facts">
        <div>
          <dt>Yarn</dt>
          <dd>
            {r.yarn_type} · {r.colour}
          </dd>
        </div>
        <div>
          <dt>Received</dt>
          <dd>{kg(r.quantity_kg)}</dd>
        </div>
        <div>
          <dt>Damaged</dt>
          <dd>{kg(r.damaged_kg)}</dd>
        </div>
        <div>
          <dt>Goes into stock</dt>
          <dd>{kg(r.accepted_kg)}</dd>
        </div>
        <div>
          <dt>PO · batch</dt>
          <dd>
            {r.po_no || "—"} · {r.batch_no || "—"}
          </dd>
        </div>
      </dl>
      {r.discrepancy ? (
        <div className="sm-check is-warn">
          <span aria-hidden>!</span>
          <div>
            <strong>Discrepancy: {r.discrepancy.replace(/,/g, ", ")}</strong>
            <p>{r.discrepancy_note}</p>
          </div>
        </div>
      ) : (
        <div className="sm-check is-ok">
          <span aria-hidden>✓</span>
          <div>
            <strong>Matches the purchase order</strong>
            <p>{r.discrepancy_note || "No shortage, excess or damage recorded."}</p>
          </div>
        </div>
      )}
      <ErrorBox error={err} />
      <Field label="Review note (required to reject)">
        <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
      </Field>
      <div className="sm-row-end">
        <button className="btn btn-ghost btn-sm sm-danger-text" onClick={() => decide(false)} disabled={busy}>
          Reject delivery
        </button>
        <button className="btn btn-primary btn-sm" onClick={() => decide(true)} disabled={busy}>
          {busy ? "Saving…" : "Validate & add to stock"}
        </button>
      </div>
    </Dialog>
  );
}

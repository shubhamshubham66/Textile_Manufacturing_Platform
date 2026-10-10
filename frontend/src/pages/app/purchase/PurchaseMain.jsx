// Purchase & raw material desk: dashboard, suppliers, raw material inventory.
import { useState } from "react";
import { apiFetch } from "../../../lib/api.js";
import { HBars } from "../../../components/owner/Charts.jsx";
import { Badge, Dialog, Empty, ErrorBox, Field, Loading, Notice, PageHead, Stat, day, go, when, useApi } from "../../../components/super/kit.jsx";
import "../../../owner.css";

const TOPICS = ["yarn", "purchase", "tasks", "orders", "notifications"];
const kg = (v) => `${Number(v || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })} kg`;
const MOVE_LABEL = { receipt: "Received", issue: "Issued", adjustment: "Adjusted", correction: "Corrected", opening: "Opening" };

export function MoveBadge({ kind, change }) {
  const tone = change > 0 ? "ok" : change < 0 ? "warning" : "info";
  return <Badge value={tone} label={MOVE_LABEL[kind] || kind} />;
}

// --------------------------------------------------------------------------- //
export function PurchaseDashboard() {
  const { data, error, loading, reload } = useApi("/api/purchase/overview", TOPICS);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const c = data.cards;
  return (
    <div className="module sm-page">
      <PageHead title="Purchase & raw material" sub="Yarn buying, suppliers, deliveries and stock — all from live records." />
      <div className="sm-stats">
        <Stat label="Suppliers (active)" value={c.suppliers} onClick={() => go("/app/suppliers")} />
        <Stat label="Purchase orders" value={c.purchase_orders} onClick={() => go("/app/purchase")} />
        <Stat label="Pending purchase orders" value={c.pending_pos} tone={c.pending_pos ? "amber" : undefined} onClick={() => go("/app/purchase")} />
        <Stat label="Raw material stock" value={kg(c.stock_kg)} onClick={() => go("/app/stock")} />
        <Stat label="Low-stock items" value={c.low_stock} tone={c.low_stock ? "red" : "green"} onClick={() => go("/app/low-stock")} />
        <Stat label="Today's receipts" value={c.receipts_today} hint={kg(c.receipts_today_kg)} onClick={() => go("/app/yarn")} />
      </div>

      {(data.requests_waiting > 0 || data.approved_to_order > 0 || data.receipts_to_validate > 0) && (
        <div className="sm-todo">
          {data.receipts_to_validate > 0 && (
            <button onClick={() => go("/app/yarn")}>
              <b>{data.receipts_to_validate}</b> {data.receipts_to_validate === 1 ? "delivery" : "deliveries"} waiting for validation ›
            </button>
          )}
          {data.approved_to_order > 0 && (
            <button onClick={() => go("/app/purchase")}>
              <b>{data.approved_to_order}</b> approved {data.approved_to_order === 1 ? "request" : "requests"} to turn into purchase orders ›
            </button>
          )}
          {data.requests_waiting > 0 && (
            <button onClick={() => go("/app/purchase-requests")}>
              <b>{data.requests_waiting}</b> {data.requests_waiting === 1 ? "request" : "requests"} waiting for Supermanager approval ›
            </button>
          )}
        </div>
      )}

      <div className="sm-grid-2">
        <section className="panel">
          <HBars title="Yarn in stock by colour (kg)" data={data.stock_by_colour} unit="kg" />
        </section>
        <section className="panel">
          <div className="sm-panel-head">
            <h3>Low-stock alerts</h3>
            <button className="link-btn" onClick={() => go("/app/low-stock")}>
              All alerts
            </button>
          </div>
          {data.low_stock.length === 0 ? (
            <Empty>Every yarn line is above its minimum level.</Empty>
          ) : (
            <ul className="sm-alerts">
              {data.low_stock.map((s) => (
                <li key={s.id} className="sm-alert is-warning">
                  <button type="button" onClick={() => go("/app/low-stock")}>
                    <Badge value="warning" label="Low" />
                    <span>
                      <strong>
                        {s.yarn_type} · {s.colour}
                      </strong>
                      <small className="muted">
                        {kg(s.available_kg)} available · minimum {kg(s.minimum_kg)} · {kg(s.on_order_kg)} on order
                      </small>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <h3 className="sm-mt">Instructions from the Supermanager</h3>
          {data.instructions.length === 0 ? (
            <Empty>No open instructions.</Empty>
          ) : (
            <ul className="sm-list">
              {data.instructions.map((t) => (
                <li key={t.id}>
                  <button type="button" onClick={() => go("/app/purchase-requests")}>
                    <span>
                      <span>{t.title}</span>
                      <small className="muted">Due {day(t.deadline)}</small>
                    </span>
                    <span className="sm-actions">
                      <Badge value={t.priority} />
                      <Badge value={t.status} />
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <div className="sm-grid-2">
        <section className="panel">
          <div className="sm-panel-head">
            <h3>Pending purchase orders</h3>
            <button className="link-btn" onClick={() => go("/app/purchase")}>
              All orders
            </button>
          </div>
          {data.pending_pos.length === 0 ? (
            <Empty>No purchase orders are open.</Empty>
          ) : (
            <div className="owner-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>PO</th>
                    <th>Supplier</th>
                    <th className="num">Received / ordered</th>
                    <th>Expected</th>
                  </tr>
                </thead>
                <tbody>
                  {data.pending_pos.map((p) => (
                    <tr key={p.id}>
                      <td className="sm-nowrap">
                        {p.po_no}
                        <small className="sm-sub">
                          {p.yarn_type} {p.colour}
                        </small>
                      </td>
                      <td>{p.supplier}</td>
                      <td className="num">
                        {kg(p.received_kg)} / {kg(p.quantity_kg)}
                      </td>
                      <td>
                        {day(p.expected_date)} {p.late && <Badge value="delayed" label="Late" />}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
        <section className="panel">
          <div className="sm-panel-head">
            <h3>Recent receipts</h3>
            <button className="link-btn" onClick={() => go("/app/yarn")}>
              Material receiving
            </button>
          </div>
          {data.recent_receipts.length === 0 ? (
            <Empty>No deliveries recorded yet.</Empty>
          ) : (
            <ul className="sm-list">
              {data.recent_receipts.map((r) => (
                <li key={r.id}>
                  <button type="button" onClick={() => go("/app/yarn")}>
                    <span>
                      <span>
                        {kg(r.quantity_kg)} {r.yarn_type} {r.colour}
                      </span>
                      <small className="muted">
                        {r.supplier || "—"} {r.po_no ? `· ${r.po_no}` : ""} · {when(r.received_at)}
                      </small>
                    </span>
                    <Badge value={r.status === "recorded" ? "waiting" : r.status === "validated" ? "ok" : "critical"} label={r.status === "recorded" ? "To validate" : r.status === "validated" ? "Validated" : "Rejected"} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="panel">
        <h3>Stock activity</h3>
        {data.activity.length === 0 ? (
          <Empty>No stock movements yet.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Yarn</th>
                  <th>Type</th>
                  <th className="num">Change</th>
                  <th className="num">Balance</th>
                  <th>Reference</th>
                </tr>
              </thead>
              <tbody>
                {data.activity.map((m) => (
                  <tr key={m.id}>
                    <td className="sm-nowrap">{when(m.at)}</td>
                    <td>{m.what}</td>
                    <td>
                      <MoveBadge kind={m.kind} change={m.change_kg} />
                    </td>
                    <td className={`num ${m.change_kg < 0 ? "sm-neg" : "sm-pos"}`}>
                      {m.change_kg > 0 ? "+" : ""}
                      {kg(m.change_kg)}
                    </td>
                    <td className="num">{kg(m.balance_kg)}</td>
                    <td>
                      {m.reference || "—"}
                      {m.user && <small className="sm-sub">{m.user}</small>}
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
export function SuppliersDesk() {
  const [f, setF] = useState({ q: "", status: "" });
  const qs = new URLSearchParams(Object.entries(f).filter(([, v]) => v)).toString();
  const { data, error, loading, reload } = useApi(`/api/purchase/suppliers${qs ? `?${qs}` : ""}`, ["purchase"]);
  const [form, setForm] = useState(null);
  const [hist, setHist] = useState(null);
  const [msg, setMsg] = useState(null);

  async function toggle(s) {
    if (!window.confirm(`${s.is_active ? "Deactivate" : "Activate"} ${s.name}?${s.is_active ? " No new purchase orders can go to them." : ""}`)) return;
    try {
      await apiFetch(`/api/purchase/suppliers/${s.id}/active`, { method: "POST", body: { active: !s.is_active } });
      setMsg({ kind: "ok", text: `${s.name} ${s.is_active ? "deactivated" : "activated"}.` });
      reload();
    } catch (e) {
      setMsg({ kind: "err", text: e.message });
    }
  }

  return (
    <div className="module sm-page">
      <PageHead title="Supplier management" sub="Yarn suppliers, what they supply and their order history.">
        <button className="btn btn-primary" onClick={() => setForm({})}>
          ＋ Add supplier
        </button>
      </PageHead>
      <Notice kind={msg?.kind} onClose={() => setMsg(null)}>
        {msg?.text}
      </Notice>
      <ErrorBox error={error} onRetry={reload} />
      <section className="panel">
        <div className="sm-toolbar">
          <input className="sm-search" type="search" placeholder="Search name, contact or yarn…" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} aria-label="Search suppliers" />
          <select className="sm-select" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })} aria-label="Status">
            <option value="">Active and inactive</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
        {loading && !data ? (
          <Loading />
        ) : data.length === 0 ? (
          <Empty>No suppliers match.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Supplier</th>
                  <th>Contact</th>
                  <th>Yarn supplied</th>
                  <th className="num">POs (open)</th>
                  <th className="num">Ordered</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.map((s) => (
                  <tr key={s.id} className={s.is_active ? "" : "sm-row-off"}>
                    <td>
                      <strong>{s.name}</strong>
                      {s.address && <small className="sm-sub">{s.address}</small>}
                    </td>
                    <td>
                      {s.contact_person || "—"}
                      <small className="sm-sub">{[s.phone, s.email].filter(Boolean).join(" · ") || "—"}</small>
                    </td>
                    <td>{s.yarn_types || <span className="muted">—</span>}</td>
                    <td className="num">
                      {s.po_count} ({s.open_pos})
                    </td>
                    <td className="num">{kg(s.ordered_kg)}</td>
                    <td>
                      <Badge value={s.is_active ? "active" : "inactive"} label={s.is_active ? "Active" : "Inactive"} />
                    </td>
                    <td>
                      <div className="sm-actions">
                        <button className="btn btn-ghost btn-sm" onClick={() => setHist(s)}>
                          History
                        </button>
                        <button className="btn btn-ghost btn-sm" onClick={() => setForm(s)}>
                          Edit
                        </button>
                        <button className="link-btn" onClick={() => toggle(s)}>
                          {s.is_active ? "Deactivate" : "Activate"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {form && (
        <SupplierForm
          s={form.id ? form : null}
          onClose={() => setForm(null)}
          onSaved={(text) => {
            setForm(null);
            setMsg({ kind: "ok", text });
            reload();
          }}
        />
      )}
      {hist && <SupplierHistory s={hist} onClose={() => setHist(null)} />}
    </div>
  );
}

function SupplierForm({ s, onClose, onSaved }) {
  const [f, setF] = useState({
    name: s?.name || "",
    contact_person: s?.contact_person || "",
    phone: s?.phone || "",
    email: s?.email || "",
    address: s?.address || "",
    yarn_types: s?.yarn_types || "",
  });
  const [errs, setErrs] = useState({});
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  async function submit(e) {
    e.preventDefault();
    const x = {};
    if (f.name.trim().length < 2) x.name = "Enter the supplier name.";
    if (f.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.email.trim())) x.email = "Enter a valid email.";
    if (f.phone && !/^[0-9+\-\s]{6,20}$/.test(f.phone.trim())) x.phone = "Digits, spaces, + and - only.";
    setErrs(x);
    if (Object.keys(x).length) return;
    setBusy(true);
    setErr("");
    try {
      const body = Object.fromEntries(Object.entries(f).map(([k, v]) => [k, v.trim() || null]));
      if (s) await apiFetch(`/api/purchase/suppliers/${s.id}`, { method: "PUT", body });
      else await apiFetch("/api/purchase/suppliers", { method: "POST", body });
      onSaved(s ? `${f.name.trim()} updated.` : `${f.name.trim()} added.`);
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title={s ? `Edit ${s.name}` : "Add supplier"} onClose={onClose}>
      <ErrorBox error={err} />
      <form className="form-grid sm-form" onSubmit={submit} noValidate>
        <Field label="Supplier name" error={errs.name}>
          <input value={f.name} onChange={set("name")} />
        </Field>
        <Field label="Contact person">
          <input value={f.contact_person} onChange={set("contact_person")} />
        </Field>
        <Field label="Phone" error={errs.phone}>
          <input value={f.phone} onChange={set("phone")} inputMode="tel" />
        </Field>
        <Field label="Email" error={errs.email}>
          <input type="email" value={f.email} onChange={set("email")} />
        </Field>
        <Field label="Address" wide>
          <input value={f.address} onChange={set("address")} />
        </Field>
        <Field label="Yarn types supplied (comma-separated)" wide>
          <input value={f.yarn_types} onChange={set("yarn_types")} placeholder="Cotton 30s, Cotton 40s, Polyester 150D" />
        </Field>
        <div className="sm-row-end sm-wide">
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary btn-sm" disabled={busy}>
            {busy ? "Saving…" : s ? "Save changes" : "Add supplier"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

function SupplierHistory({ s, onClose }) {
  const { data, error, loading } = useApi(`/api/purchase/suppliers/${s.id}/history`);
  return (
    <Dialog title={`${s.name} — purchase history`} onClose={onClose} wide>
      <ErrorBox error={error} />
      {loading && !data ? (
        <Loading />
      ) : (
        data && (
          <>
            <h4>Purchase orders</h4>
            {data.purchase_orders.length === 0 ? (
              <Empty>No purchase orders yet.</Empty>
            ) : (
              <div className="owner-table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>PO</th>
                      <th>Yarn</th>
                      <th className="num">Received / ordered</th>
                      <th className="num">Value</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.purchase_orders.map((p) => (
                      <tr key={p.id}>
                        <td>
                          {p.po_no}
                          <small className="sm-sub">{day(p.created_at)}</small>
                        </td>
                        <td>
                          {p.yarn_type} {p.colour}
                        </td>
                        <td className="num">
                          {kg(p.received_kg)} / {kg(p.quantity_kg)}
                        </td>
                        <td className="num">₹{p.total.toLocaleString("en-IN")}</td>
                        <td>
                          <Badge value={p.status === "received" ? "ok" : p.status === "cancelled" ? "inactive" : "waiting"} label={p.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <h4>Deliveries</h4>
            {data.receipts.length === 0 ? (
              <Empty>No deliveries recorded.</Empty>
            ) : (
              <ul className="sm-exceptions is-plain">
                {data.receipts.map((r) => (
                  <li key={r.id}>
                    {when(r.received_at)} · {kg(r.quantity_kg)} {r.yarn_type} {r.colour} {r.batch_no ? `· batch ${r.batch_no}` : ""} · {r.status}
                    {r.discrepancy && ` · flagged ${r.discrepancy}`}
                  </li>
                ))}
              </ul>
            )}
          </>
        )
      )}
    </Dialog>
  );
}

// --------------------------------------------------------------------------- //
export function RawInventory() {
  const [f, setF] = useState({ q: "", colour: "", low: false });
  const qs = new URLSearchParams({ ...(f.q && { q: f.q }), ...(f.colour && { colour: f.colour }), ...(f.low && { low: "true" }) }).toString();
  const { data, error, loading, reload } = useApi(`/api/purchase/inventory${qs ? `?${qs}` : ""}`, ["yarn", "purchase", "orders"]);
  const [edit, setEdit] = useState(null);
  const [moves, setMoves] = useState(null);
  const [msg, setMsg] = useState("");

  return (
    <div className="module sm-page">
      <PageHead title="Raw material inventory" sub="Yarn in the store: available, reserved for orders, where it is kept and its minimum level." />
      <Notice onClose={() => setMsg("")}>{msg}</Notice>
      <ErrorBox error={error} onRetry={reload} />
      {data && (
        <div className="sm-stats sm-stats-4">
          <Stat label="In stock" value={kg(data.totals.kg)} />
          <Stat label="Reserved for orders" value={kg(data.totals.reserved)} />
          <Stat label="Available" value={kg(data.totals.available)} tone="green" />
          <Stat label="Lines shown" value={data.rows.length} />
        </div>
      )}
      <section className="panel">
        <div className="sm-toolbar">
          <input className="sm-search" type="search" placeholder="Search yarn, colour or location…" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} aria-label="Search stock" />
          <div className="sm-filters">
            <select className="sm-select" value={f.colour} onChange={(e) => setF({ ...f, colour: e.target.value })} aria-label="Colour">
              <option value="">All colours</option>
              {(data?.colours || []).map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <label className="sm-check-inline">
              <input type="checkbox" checked={f.low} onChange={(e) => setF({ ...f, low: e.target.checked })} /> Low stock only
            </label>
            <button className="btn btn-ghost btn-sm" onClick={() => setMoves({})}>
              All stock movements
            </button>
          </div>
        </div>
        {loading && !data ? (
          <Loading />
        ) : data.rows.length === 0 ? (
          <Empty>No yarn lines match.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Yarn type</th>
                  <th>Colour</th>
                  <th className="num">In stock</th>
                  <th className="num">Reserved</th>
                  <th className="num">Available</th>
                  <th className="num">Minimum</th>
                  <th>Location</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.id} className={r.low ? "row-warn" : ""}>
                    <td>
                      <strong>{r.yarn_type}</strong>
                    </td>
                    <td>{r.colour}</td>
                    <td className="num">{kg(r.quantity_kg)}</td>
                    <td className="num">{kg(r.reserved_kg)}</td>
                    <td className="num">
                      <strong>{kg(r.available_kg)}</strong> {r.low && <Badge value="critical" label="Low" />}
                    </td>
                    <td className="num">{kg(r.reorder_level_kg)}</td>
                    <td>{r.location || <span className="muted">not set</span>}</td>
                    <td>
                      <div className="sm-actions">
                        <button className="btn btn-ghost btn-sm" onClick={() => setMoves(r)}>
                          Movements
                        </button>
                        <button className="btn btn-ghost btn-sm" onClick={() => setEdit(r)}>
                          Edit
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && <p className="muted sm-small">{data.reserved_note} Quantities change only through validated deliveries, so every change has a record.</p>}
      </section>
      {edit && (
        <StockEdit
          row={edit}
          onClose={() => setEdit(null)}
          onSaved={() => {
            setEdit(null);
            setMsg(`${edit.yarn_type} ${edit.colour} updated.`);
            reload();
          }}
        />
      )}
      {moves && <Movements row={moves.id ? moves : null} onClose={() => setMoves(null)} />}
    </div>
  );
}

function StockEdit({ row, onClose, onSaved }) {
  const [loc, setLoc] = useState(row.location || "");
  const [min, setMin] = useState(String(row.reorder_level_kg));
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    if (!(Number(min) >= 0)) return setErr("Minimum level must be 0 or more.");
    setBusy(true);
    try {
      await apiFetch(`/api/purchase/inventory/${row.id}`, { method: "PUT", body: { location: loc.trim() || null, reorder_level_kg: Number(min) } });
      onSaved();
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title={`${row.yarn_type} · ${row.colour}`} onClose={onClose}>
      <p className="muted sm-small">Stock quantity is changed only by validated deliveries.</p>
      <ErrorBox error={err} />
      <form className="form-grid sm-form" onSubmit={submit} noValidate>
        <Field label="Storage location">
          <input value={loc} onChange={(e) => setLoc(e.target.value)} placeholder="Rack A-2" />
        </Field>
        <Field label="Minimum stock (kg)">
          <input type="number" min="0" value={min} onChange={(e) => setMin(e.target.value)} />
        </Field>
        <div className="sm-row-end sm-wide">
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary btn-sm" disabled={busy}>
            {busy ? "Saving…" : "Save"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

function Movements({ row, onClose }) {
  const { data, error, loading } = useApi(`/api/purchase/movements${row ? `?stock_id=${row.id}` : ""}`, ["yarn"]);
  return (
    <Dialog title={row ? `Movements — ${row.yarn_type} ${row.colour}` : "Stock movements"} onClose={onClose} wide>
      <ErrorBox error={error} />
      {loading && !data ? (
        <Loading />
      ) : data.length === 0 ? (
        <Empty>No movements recorded.</Empty>
      ) : (
        <div className="owner-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>When</th>
                {!row && <th>Yarn</th>}
                <th>Type</th>
                <th className="num">Change</th>
                <th className="num">Balance</th>
                <th>Reference · by</th>
              </tr>
            </thead>
            <tbody>
              {data.map((m) => (
                <tr key={m.id}>
                  <td className="sm-nowrap">{when(m.at)}</td>
                  {!row && (
                    <td>
                      {m.yarn_type} {m.colour}
                    </td>
                  )}
                  <td>
                    <MoveBadge kind={m.kind} change={m.change_kg} />
                  </td>
                  <td className={`num ${m.change_kg < 0 ? "sm-neg" : "sm-pos"}`}>
                    {m.change_kg > 0 ? "+" : ""}
                    {kg(m.change_kg)}
                  </td>
                  <td className="num">{kg(m.balance_kg)}</td>
                  <td>
                    {m.reference || "—"}
                    <small className="sm-sub">{m.user || "System"}</small>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Dialog>
  );
}

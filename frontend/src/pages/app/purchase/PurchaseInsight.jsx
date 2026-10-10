// Low-stock alerts, production material requirements, reports, notifications.
import { useState } from "react";
import { apiFetch } from "../../../lib/api.js";
import { inr } from "../../../lib/format.js";
import { HBars } from "../../../components/owner/Charts.jsx";
import { Badge, Dialog, Empty, ErrorBox, Field, Loading, Notice, PageHead, Stat, day, go, when, useApi } from "../../../components/super/kit.jsx";
import { RequestForm } from "./PurchaseFlow.jsx";
import "../../../owner.css";

const kg = (v) => `${Number(v || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })} kg`;

// --------------------------------------------------------------------------- //
export function LowStockAlerts() {
  const { data, error, loading, reload } = useApi("/api/purchase/low-stock", ["yarn", "purchase"]);
  const [form, setForm] = useState(null);
  const [msg, setMsg] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead title="Low-stock alerts" sub={data.rule} />
      <Notice onClose={() => setMsg("")}>{msg}</Notice>
      <section className="panel">
        {data.rows.length === 0 ? (
          <Empty>Every yarn line is above its minimum level.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Yarn</th>
                  <th className="num">Available</th>
                  <th className="num">Minimum</th>
                  <th className="num">Required to minimum</th>
                  <th className="num">Already on order</th>
                  <th className="num">Suggested reorder</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((s) => (
                  <tr key={s.id} className="row-warn">
                    <td>
                      <strong>
                        {s.yarn_type} · {s.colour}
                      </strong>
                      <small className="sm-sub">{s.location ? `Kept at ${s.location}` : "Location not set"}</small>
                    </td>
                    <td className="num">{kg(s.available_kg)}</td>
                    <td className="num">{kg(s.minimum_kg)}</td>
                    <td className="num">{kg(s.required_kg)}</td>
                    <td className="num">{kg(s.on_order_kg)}</td>
                    <td className="num">
                      <strong>{kg(s.suggested_kg)}</strong>
                    </td>
                    <td>
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() =>
                          setForm({
                            source: "low_stock",
                            yarn_type: s.yarn_type,
                            colour: s.colour,
                            quantity_kg: s.suggested_kg || s.required_kg,
                            reason: `Below minimum: ${kg(s.available_kg)} available, minimum ${kg(s.minimum_kg)}`,
                          })
                        }
                      >
                        Create request
                      </button>
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
            setMsg(`${r.pr_no} ${r.status === "approved" ? "approved automatically" : "sent for Supermanager approval"}.`);
            reload();
          }}
        />
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
export function MaterialRequirements() {
  const { data, error, loading, reload } = useApi("/api/purchase/requirements", ["orders", "yarn", "production", "purchase"]);
  const [form, setForm] = useState(null);
  const [share, setShare] = useState(false);
  const [msg, setMsg] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const t = data.totals;
  return (
    <div className="module sm-page">
      <PageHead title="Production material requirements" sub={data.basis}>
        <button className="btn btn-primary" onClick={() => setShare(true)}>
          Share availability
        </button>
      </PageHead>
      <Notice onClose={() => setMsg("")}>{msg}</Notice>
      <div className="sm-stats sm-stats-4">
        <Stat label="Yarn needed (confirmed orders)" value={kg(t.need_kg)} />
        <Stat label="Short" value={kg(t.short_kg)} tone={t.short_kg ? "red" : "green"} />
        <Stat label="Orders short of yarn" value={t.orders_short} tone={t.orders_short ? "red" : undefined} />
        <Stat label="May delay production" value={t.delay_risk} tone={t.delay_risk ? "red" : undefined} hint="short and due within 10 days" />
      </div>
      <section className="panel">
        {data.rows.length === 0 ? (
          <Empty>No confirmed or upcoming orders need yarn.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Fabric</th>
                  <th>Deadline</th>
                  <th className="num">Yarn still needed</th>
                  <th className="num">Covered by stock</th>
                  <th className="num">Short</th>
                  <th>Availability</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.order_id} className={r.delay_risk ? "row-warn" : ""}>
                    <td className="sm-nowrap">
                      <strong>{r.order_no}</strong>
                      <small className="sm-sub">{r.buyer}</small>
                    </td>
                    <td>
                      {r.fabric}
                      <small className="sm-sub">
                        <Badge value={r.status} />
                      </small>
                    </td>
                    <td>
                      {day(r.deadline)}
                      {r.days_left != null && <small className="sm-sub">{r.days_left} days left</small>}
                    </td>
                    <td className="num">{kg(r.need_kg)}</td>
                    <td className="num">{kg(r.covered_kg)}</td>
                    <td className={`num ${r.short_kg ? "sm-neg" : ""}`}>{kg(r.short_kg)}</td>
                    <td>
                      {r.risk === "ok" ? (
                        <Badge value="ok" label="Enough yarn" />
                      ) : r.risk === "short" ? (
                        <Badge value="critical" label={r.delay_risk ? "Short — may delay" : "Short"} />
                      ) : (
                        <Badge value="warning" label="Short if confirmed" />
                      )}
                    </td>
                    <td>
                      {r.short_kg > 0 && (
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() =>
                            setForm({ source: "order", order_id: r.order_id, colour: r.colour, quantity_kg: Math.ceil(r.short_kg), required_date: "", reason: `Yarn for ${r.order_no} (${r.fabric})` })
                          }
                        >
                          Request yarn
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
            setMsg(`${r.pr_no} ${r.status === "approved" ? "approved automatically" : "sent for Supermanager approval"}.`);
            reload();
          }}
        />
      )}
      {share && (
        <ShareDialog
          onClose={() => setShare(false)}
          onSent={(r) => {
            setShare(false);
            setMsg(`Sent to ${r.sent_to.join(" and ")}: ${r.message}`);
          }}
        />
      )}
    </div>
  );
}

function ShareDialog({ onClose, onSent }) {
  const [note, setNote] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function send() {
    setBusy(true);
    setErr("");
    try {
      onSent(await apiFetch("/api/purchase/requirements/share", { method: "POST", body: { note: note.trim() || null } }));
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title="Share material availability" onClose={onClose}>
      <p className="muted">The Supermanager and the production (floor) manager get the current shortages for confirmed orders, with your note.</p>
      <ErrorBox error={err} />
      <Field label="Note (optional)">
        <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Blue yarn arrives Monday" />
      </Field>
      <div className="sm-row-end">
        <button className="btn btn-ghost btn-sm" onClick={onClose}>
          Cancel
        </button>
        <button className="btn btn-primary btn-sm" onClick={send} disabled={busy}>
          {busy ? "Sending…" : "Send"}
        </button>
      </div>
    </Dialog>
  );
}

// --------------------------------------------------------------------------- //
export function PurchaseReports() {
  const end0 = new Date().toISOString().slice(0, 10);
  const start0 = new Date(Date.now() - 89 * 864e5).toISOString().slice(0, 10);
  const [range, setRange] = useState({ start: start0, end: end0 });
  const [tab, setTab] = useState("history");
  const { data, error, loading, reload } = useApi(`/api/purchase/reports?start=${range.start}&end=${range.end}`, ["purchase", "yarn"]);
  return (
    <div className="module sm-page">
      <PageHead title="Purchase reports" sub="Purchases, supplier performance, consumption and stock value.">
        <div className="sm-range">
          <label className="owner-month">
            <span>From</span>
            <input type="date" value={range.start} onChange={(e) => e.target.value && setRange({ ...range, start: e.target.value })} />
          </label>
          <label className="owner-month">
            <span>To</span>
            <input type="date" value={range.end} onChange={(e) => e.target.value && setRange({ ...range, end: e.target.value })} />
          </label>
        </div>
      </PageHead>
      <ErrorBox error={error} onRetry={reload} />
      {loading && !data ? (
        <Loading />
      ) : (
        data && (
          <section className="panel">
            <div className="sm-tabs" role="tablist">
              {[
                ["history", "Purchase history"],
                ["suppliers", "Supplier performance"],
                ["consumption", "Consumption"],
                ["valuation", "Stock valuation"],
                ["monthly", "Monthly summary"],
              ].map(([k, l]) => (
                <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "is-active" : ""} onClick={() => setTab(k)}>
                  {l}
                </button>
              ))}
            </div>
            {tab === "history" &&
              (data.history.length === 0 ? (
                <Empty>No purchase orders in this period.</Empty>
              ) : (
                <div className="owner-table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>PO</th>
                        <th>Date</th>
                        <th>Supplier</th>
                        <th>Yarn</th>
                        <th className="num">Kg (received)</th>
                        <th className="num">Total</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.history.map((p) => (
                        <tr key={p.id}>
                          <td>{p.po_no}</td>
                          <td>{day(p.created_at)}</td>
                          <td>{p.supplier}</td>
                          <td>
                            {p.yarn_type} {p.colour}
                          </td>
                          <td className="num">
                            {kg(p.quantity_kg)} <small className="muted">({kg(p.received_kg)})</small>
                          </td>
                          <td className="num">{inr(p.total)}</td>
                          <td>{p.status}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            {tab === "suppliers" &&
              (data.suppliers.length === 0 ? (
                <Empty>No supplier orders yet.</Empty>
              ) : (
                <div className="owner-table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Supplier</th>
                        <th className="num">Orders</th>
                        <th className="num">Ordered</th>
                        <th className="num">Delivered</th>
                        <th className="num">Fill rate</th>
                        <th className="num">On time</th>
                        <th className="num">Avg delay</th>
                        <th className="num">Damaged</th>
                        <th className="num">Late now</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.suppliers.map((s) => (
                        <tr key={s.supplier}>
                          <td>{s.supplier}</td>
                          <td className="num">{s.orders}</td>
                          <td className="num">{kg(s.ordered_kg)}</td>
                          <td className="num">{kg(s.received_kg)}</td>
                          <td className="num">{s.fill_rate}%</td>
                          <td className="num">{s.on_time_rate == null ? <span className="muted">no dated orders</span> : `${s.on_time_rate}%`}</td>
                          <td className="num">{s.avg_delay_days ? `${s.avg_delay_days} d` : "—"}</td>
                          <td className="num">{kg(s.damaged_kg)}</td>
                          <td className="num">{s.late_open || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            {tab === "consumption" && (
              <div className="sm-grid-2">
                <div>
                  <HBars title="Yarn used by production (kg, estimate)" data={data.consumption.map((c) => ({ label: c.colour, value: c.kg }))} unit="kg" />
                  <p className="muted sm-small">{data.consumption_basis}</p>
                </div>
                <div>
                  <h4>Stock issued (recorded movements)</h4>
                  {data.issued.length === 0 ? (
                    <Empty>No stock was issued out in this period.</Empty>
                  ) : (
                    <ul className="sm-exceptions is-plain">
                      {data.issued.map((i) => (
                        <li key={i.item}>
                          {i.item}: {kg(i.kg)}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}
            {tab === "valuation" && (
              <>
                <div className="owner-table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Yarn</th>
                        <th className="num">In stock</th>
                        <th className="num">Rate</th>
                        <th className="num">Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.valuation.rows.map((v) => (
                        <tr key={v.item}>
                          <td>{v.item}</td>
                          <td className="num">{kg(v.kg)}</td>
                          <td className="num">{v.has_cost ? `${inr(v.rate)}/kg` : <span className="muted">no cost data</span>}</td>
                          <td className="num">{v.has_cost ? inr(v.value) : "—"}</td>
                        </tr>
                      ))}
                      <tr className="sm-total-row">
                        <td>Total</td>
                        <td></td>
                        <td></td>
                        <td className="num">{inr(data.valuation.total)}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                {data.valuation.missing_cost > 0 && <p className="muted sm-small">{data.valuation.missing_cost} lines have no purchase rate yet and are not valued.</p>}
              </>
            )}
            {tab === "monthly" &&
              (data.monthly.length === 0 ? (
                <Empty>No purchases in this period.</Empty>
              ) : (
                <div className="owner-table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Month</th>
                        <th className="num">Purchase orders</th>
                        <th className="num">Kg ordered</th>
                        <th className="num">Value (incl. tax)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.monthly.map((m) => (
                        <tr key={m.month}>
                          <td>{new Date(`${m.month}-01`).toLocaleDateString("en-IN", { month: "long", year: "numeric" })}</td>
                          <td className="num">{m.orders}</td>
                          <td className="num">{kg(m.kg)}</td>
                          <td className="num">{inr(m.value)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
          </section>
        )
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
const KIND_LABEL = {
  instruction: "Instruction", approval: "Approved", rejection: "Rejected", delivery: "Delivery",
  low_stock: "Low stock", discrepancy: "Discrepancy", availability: "Availability", approval_needed: "Approval",
};

export function PurchaseNotifications() {
  const { data, error, loading, reload } = useApi("/api/purchase/notifications", ["purchase", "tasks", "yarn", "notifications"]);
  const [kind, setKind] = useState("");
  async function markRead() {
    await apiFetch("/api/purchase/notifications/read", { method: "POST" }).catch(() => {});
    reload();
  }
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const kinds = [...new Set(data.items.map((i) => i.kind))];
  const list = data.items.filter((i) => !kind || i.kind === kind);
  return (
    <div className="module sm-page">
      <PageHead title="Notifications" sub="Instructions, approvals, deliveries due, low stock and receiving problems.">
        {data.unread > 0 && (
          <button className="btn btn-ghost" onClick={markRead}>
            Mark {data.unread} as read
          </button>
        )}
      </PageHead>
      <div className="sm-chips">
        <button className={!kind ? "is-active" : ""} onClick={() => setKind("")}>
          All <b>{data.items.length}</b>
        </button>
        {kinds.map((k) => (
          <button key={k} className={kind === k ? "is-active" : ""} onClick={() => setKind(k)}>
            {KIND_LABEL[k] || k} <b>{data.items.filter((i) => i.kind === k).length}</b>
          </button>
        ))}
      </div>
      <section className="panel">
        {list.length === 0 ? (
          <Empty>Nothing needs your attention.</Empty>
        ) : (
          <ul className="sm-alerts">
            {list.map((n, i) => (
              <li key={i} className={`sm-alert is-${n.level === "warning" || n.level === "urgent" ? "warning" : "info"}`}>
                <button type="button" onClick={() => go(n.page)}>
                  <Badge value={n.kind === "rejection" ? "critical" : n.kind === "approval" ? "ok" : n.level === "warning" ? "warning" : "info"} label={KIND_LABEL[n.kind] || n.kind} />
                  <span>
                    <strong>
                      {n.title} {n.unread && <span className="sm-new">new</span>}
                    </strong>
                    <small className="muted">
                      {n.detail}
                      {n.at ? ` · ${when(n.at)}` : ""}
                    </small>
                  </span>
                  <span className="sm-go" aria-hidden>
                    ›
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

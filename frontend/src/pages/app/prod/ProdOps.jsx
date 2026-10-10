// Material Requests, QC Handover, Production Reports, Notifications and
// Activity Logs for the Production Manager.
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
  Stat,
  when,
  useApi,
} from "../../../components/super/kit.jsx";
import "../../../owner.css";

const n = (v) => Number(v || 0).toLocaleString("en-IN");
const rupee = (v) =>
  `₹${Number(v || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

// --------------------------------------------------------------------------- //
// Material Requests — raise shortage requests to the Purchase/Store desk.
// --------------------------------------------------------------------------- //
export function ProdMaterials() {
  const { data, error, loading, reload } = useApi("/api/prod/materials", [
    "yarn",
    "purchase",
    "orders",
  ]);
  const [form, setForm] = useState(null); // prefill from a shortage, or {}
  const [msg, setMsg] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead title="Material requests" sub={data.note}>
        <button className="btn btn-primary btn-sm" onClick={() => setForm({})}>
          ＋ New request
        </button>
      </PageHead>
      <Notice onClose={() => setMsg("")}>{msg}</Notice>

      <section
        className={`panel ${data.shortages.length ? "sm-attention" : ""}`}
      >
        <h3>Shortages against active orders</h3>
        {data.shortages.length === 0 ? (
          <Empty>Every active order has enough yarn in the store.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Yarn</th>
                  <th className="num">Need</th>
                  <th className="num">Short</th>
                  <th>Deadline</th>
                  <th>Request</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.shortages.map((s) => (
                  <tr key={s.order_id} className={s.urgent ? "row-warn" : ""}>
                    <td>
                      <strong>{s.order_no}</strong>
                      <small className="sm-sub">{s.buyer}</small>
                    </td>
                    <td>
                      {s.fabric_type} · {s.colour}
                    </td>
                    <td className="num">{n(s.need_kg)} kg</td>
                    <td className="num">{n(s.short_kg)} kg</td>
                    <td>
                      {s.deadline || "—"}
                      {s.days_left != null && (
                        <small className="sm-sub">{s.days_left} days</small>
                      )}
                    </td>
                    <td>
                      {s.request ? (
                        <Badge
                          value={
                            s.request.status === "rejected" ? "critical" : "ok"
                          }
                          label={`${s.request.pr_no} · ${s.request.status}`}
                        />
                      ) : (
                        <span className="muted">none</span>
                      )}
                    </td>
                    <td>
                      {!s.request && (
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() =>
                            setForm({
                              yarn_type: s.fabric_type,
                              colour: s.colour,
                              quantity_kg: s.short_kg,
                              order_id: s.order_id,
                              order_no: s.order_no,
                            })
                          }
                        >
                          Request
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

      <section className="panel">
        <h3>My requests</h3>
        {data.requests.length === 0 ? (
          <Empty>You have not raised any material requests yet.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Request</th>
                  <th>Yarn</th>
                  <th className="num">Quantity</th>
                  <th>Order</th>
                  <th>Status</th>
                  <th>Raised</th>
                </tr>
              </thead>
              <tbody>
                {data.requests.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <strong>{r.pr_no}</strong>
                    </td>
                    <td>
                      {r.yarn_type} · {r.colour}
                    </td>
                    <td className="num">{n(r.quantity_kg)} kg</td>
                    <td>{r.order_no || "—"}</td>
                    <td>
                      <Badge
                        value={
                          r.status === "rejected"
                            ? "critical"
                            : r.status === "pending"
                              ? "waiting"
                              : "ok"
                        }
                        label={r.status}
                      />
                    </td>
                    <td>{when(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {form && (
        <MaterialDialog
          prefill={form}
          orders={data.shortages}
          onClose={() => setForm(null)}
          onDone={(t) => {
            setForm(null);
            setMsg(t);
            reload();
          }}
        />
      )}
    </div>
  );
}

function MaterialDialog({ prefill, onClose, onDone }) {
  const [yarn, setYarn] = useState(prefill.yarn_type || "");
  const [colour, setColour] = useState(prefill.colour || "");
  const [qty, setQty] = useState(prefill.quantity_kg || "");
  const [reqDate, setReqDate] = useState("");
  const [reason, setReason] = useState(
    prefill.order_no ? `For order ${prefill.order_no}` : "",
  );
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function go() {
    if (!yarn.trim() || !colour.trim())
      return setErr("Enter the yarn type and colour.");
    if (!qty || Number(qty) <= 0) return setErr("Enter the quantity in kg.");
    setBusy(true);
    setErr("");
    try {
      const res = await apiFetch("/api/prod/materials", {
        method: "POST",
        body: {
          yarn_type: yarn.trim(),
          colour: colour.trim(),
          quantity_kg: Number(qty),
          order_id: prefill.order_id || null,
          required_date: reqDate || null,
          reason: reason.trim() || null,
        },
      });
      onDone(`Request ${res.pr_no} raised (${res.status}).`);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog title="Request material" onClose={onClose}>
      <ErrorBox error={err} />
      <Field label="Yarn type">
        <input
          value={yarn}
          onChange={(e) => setYarn(e.target.value)}
          autoFocus
        />
      </Field>
      <Field label="Colour">
        <input value={colour} onChange={(e) => setColour(e.target.value)} />
      </Field>
      <Field label="Quantity (kg)">
        <input
          type="number"
          min="0"
          value={qty}
          onChange={(e) => setQty(e.target.value)}
        />
      </Field>
      <Field label="Needed by (optional)">
        <input
          type="date"
          value={reqDate}
          onChange={(e) => setReqDate(e.target.value)}
        />
      </Field>
      <Field label="Reason (optional)">
        <textarea
          rows={2}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
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
// QC Handover — submit finished rolls to QC; assign rework for rejects.
// --------------------------------------------------------------------------- //
export function ProdQc() {
  const { data, error, loading, reload } = useApi("/api/prod/qc", [
    "quality",
    "production",
    "orders",
  ]);
  const [form, setForm] = useState(false);
  const [msg, setMsg] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;

  async function rework(roll) {
    try {
      await apiFetch(`/api/prod/qc/rework/${roll.roll_id}`, {
        method: "POST",
        body: { note: null },
      });
      setMsg(`Rework assigned for roll ${roll.roll_no}.`);
      reload();
    } catch (e) {
      setMsg(e.message);
    }
  }

  return (
    <div className="module sm-page">
      <PageHead title="QC handover" sub={data.rule}>
        <button
          className="btn btn-primary btn-sm"
          onClick={() => setForm(true)}
        >
          ＋ Submit batch to QC
        </button>
      </PageHead>
      <Notice onClose={() => setMsg("")}>{msg}</Notice>

      <section className="panel">
        <h3>Awaiting QC inspection</h3>
        {data.pending.length === 0 ? (
          <Empty>No batches waiting for QC.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Fabric</th>
                  <th className="num">Rolls</th>
                  <th className="num">Metres</th>
                </tr>
              </thead>
              <tbody>
                {data.pending.map((b) => (
                  <tr key={b.order_id}>
                    <td>
                      <strong>{b.order_no}</strong>
                    </td>
                    <td>{b.fabric}</td>
                    <td className="num">{b.rolls}</td>
                    <td className="num">{n(b.meters)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section
        className={`panel ${data.rework_rejects.length ? "sm-attention" : ""}`}
      >
        <h3>Returned by QC (rework / reject)</h3>
        {data.rework_rejects.length === 0 ? (
          <Empty>No rework or rejected rolls.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Roll</th>
                  <th>Order</th>
                  <th>Result</th>
                  <th>Defect</th>
                  <th className="num">Metres</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.rework_rejects.map((r) => (
                  <tr key={r.roll_id}>
                    <td>
                      <code>{r.roll_no}</code>
                    </td>
                    <td>{r.order_no}</td>
                    <td>
                      <Badge value={r.result} />
                    </td>
                    <td>
                      {r.defect && r.defect !== "none"
                        ? r.defect.replace(/_/g, " ")
                        : "—"}
                    </td>
                    <td className="num">{n(r.length_meters)}</td>
                    <td>
                      {r.result === "rework" && (
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => rework(r)}
                        >
                          Assign rework
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
        <HandoverDialog
          orders={data.orders}
          machines={data.machines}
          onClose={() => setForm(false)}
          onDone={(t) => {
            setForm(false);
            setMsg(t);
            reload();
          }}
        />
      )}
    </div>
  );
}

function HandoverDialog({ orders, machines, onClose, onDone }) {
  const [orderId, setOrderId] = useState("");
  const [machineId, setMachineId] = useState("");
  const [rolls, setRolls] = useState("");
  const [meters, setMeters] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function go() {
    if (!orderId || !machineId) return setErr("Pick an order and a machine.");
    if (!rolls || Number(rolls) <= 0)
      return setErr("Enter the number of rolls.");
    if (!meters || Number(meters) <= 0)
      return setErr("Enter the total metres.");
    setBusy(true);
    setErr("");
    try {
      const res = await apiFetch("/api/prod/qc/handover", {
        method: "POST",
        body: {
          order_id: Number(orderId),
          machine_id: Number(machineId),
          rolls: Number(rolls),
          length_meters: Number(meters),
        },
      });
      onDone(
        `${res.rolls_created.length} roll(s) of ${res.order_no} handed to QC.`,
      );
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog title="Submit batch to QC" onClose={onClose}>
      <ErrorBox error={err} />
      <p className="muted sm-small">
        QC inspects every roll. You cannot pass or reject — only the QC Manager
        can.
      </p>
      <Field label="Order">
        <select
          value={orderId}
          onChange={(e) => setOrderId(e.target.value)}
          autoFocus
        >
          <option value="">Select…</option>
          {orders.map((o) => (
            <option key={o.id} value={o.id}>
              {o.order_no} — {o.fabric_type}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Machine">
        <select
          value={machineId}
          onChange={(e) => setMachineId(e.target.value)}
        >
          <option value="">Select…</option>
          {machines.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Number of rolls">
        <input
          type="number"
          min="1"
          value={rolls}
          onChange={(e) => setRolls(e.target.value)}
        />
      </Field>
      <Field label="Total metres">
        <input
          type="number"
          min="0"
          value={meters}
          onChange={(e) => setMeters(e.target.value)}
        />
      </Field>
      <div className="sm-row-end">
        <button className="btn btn-ghost btn-sm" onClick={onClose}>
          Cancel
        </button>
        <button className="btn btn-primary btn-sm" onClick={go} disabled={busy}>
          {busy ? "Submitting…" : "Submit to QC"}
        </button>
      </div>
    </Dialog>
  );
}

// --------------------------------------------------------------------------- //
// Production Reports.
// --------------------------------------------------------------------------- //
export function ProdReports() {
  const { data, error, loading, reload } = useApi("/api/prod/reports", [
    "production",
  ]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const maxMachine = Math.max(
    1,
    ...data.per_machine.map((r) => r.output_meters),
  );
  return (
    <div className="module sm-page">
      <PageHead
        title="Production reports"
        sub={`Output, waste and downtime from ${data.start} to ${data.end}.`}
      />
      <div className="sm-stats sm-stats-4">
        <Stat
          label="Total output"
          value={`${n(data.total_output)} m`}
          tone="green"
        />
        <Stat
          label="Lost hours"
          value={`${n(data.total_lost_hours)} h`}
          tone={data.total_lost_hours ? "amber" : undefined}
        />
        <Stat
          label="Downtime loss"
          value={rupee(data.total_loss_rupees)}
          tone={data.total_loss_rupees ? "red" : undefined}
        />
        <Stat
          label="Stages"
          value={`${n(data.per_stage.spinning)}/${n(data.per_stage.weaving)}/${n(data.per_stage.dyeing)}`}
          hint="spin / weave / dye (m)"
        />
      </div>

      <section className="panel">
        <h3>Output per machine</h3>
        {data.per_machine.length === 0 ? (
          <Empty>No output in this period.</Empty>
        ) : (
          <ul className="sm-bars">
            {data.per_machine.map((r) => (
              <li key={r.machine}>
                <span>
                  {r.machine} ({r.type})
                </span>
                <i
                  style={{ width: `${(r.output_meters / maxMachine) * 100}%` }}
                />
                <b>{n(r.output_meters)} m</b>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel">
        <h3>Output per order</h3>
        {data.per_order.length === 0 ? (
          <Empty>No order output in this period.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Fabric</th>
                  <th className="num">Ordered</th>
                  <th className="num">Produced</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.per_order.map((r) => (
                  <tr key={r.order_no}>
                    <td>
                      <strong>{r.order_no}</strong>
                    </td>
                    <td>{r.fabric}</td>
                    <td className="num">{n(r.ordered_meters)} m</td>
                    <td className="num">{n(r.output_meters)} m</td>
                    <td>
                      <Badge value={r.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel">
        <h3>Daily output</h3>
        {data.daily.length === 0 ? (
          <Empty>No daily output recorded.</Empty>
        ) : (
          <ul className="sm-bars">
            {data.daily.map((d) => {
              const max = Math.max(1, ...data.daily.map((x) => x.meters));
              return (
                <li key={d.day}>
                  <span>{d.day}</span>
                  <i style={{ width: `${(d.meters / max) * 100}%` }} />
                  <b>{n(d.meters)} m</b>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Notifications — bell list + "report a delay to the Supermanager".
// --------------------------------------------------------------------------- //
export function ProdNotifications() {
  const { data, error, loading, reload } = useApi("/api/prod/notifications", [
    "notifications",
    "purchase",
    "orders",
  ]);
  const [delay, setDelay] = useState(false);
  const [msg, setMsg] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;

  async function markRead(id) {
    try {
      await apiFetch(`/api/prod/notifications/${id}/read`, { method: "POST" });
      reload();
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="module sm-page">
      <PageHead
        title="Notifications"
        sub={`${data.unread} unread · approvals, QC results and material decisions.`}
      >
        <button
          className="btn btn-primary btn-sm"
          onClick={() => setDelay(true)}
        >
          Report a delay
        </button>
      </PageHead>
      <Notice onClose={() => setMsg("")}>{msg}</Notice>
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
                  {nt.from || "System"} · {when(nt.created_at)}
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

      {delay && (
        <DelayDialog
          onClose={() => setDelay(false)}
          onDone={(t) => {
            setDelay(false);
            setMsg(t);
          }}
        />
      )}
    </div>
  );
}

function DelayDialog({ onClose, onDone }) {
  const { data } = useApi("/api/prod/orders", []);
  const [orderId, setOrderId] = useState("");
  const [message, setMessage] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const orders = data?.orders || [];

  async function go() {
    if (!orderId) return setErr("Pick the delayed order.");
    if (message.trim().length < 3) return setErr("Explain the delay.");
    setBusy(true);
    setErr("");
    try {
      const res = await apiFetch("/api/prod/notify-delay", {
        method: "POST",
        body: { order_id: Number(orderId), message: message.trim() },
      });
      onDone(`Supermanager notified about ${res.order_no}.`);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog title="Report a delay to the Supermanager" onClose={onClose}>
      <ErrorBox error={err} />
      <Field label="Order">
        <select
          value={orderId}
          onChange={(e) => setOrderId(e.target.value)}
          autoFocus
        >
          <option value="">Select…</option>
          {orders.map((o) => (
            <option key={o.id} value={o.id}>
              {o.order_no}
            </option>
          ))}
        </select>
      </Field>
      <Field label="What's the delay?">
        <textarea
          rows={3}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="e.g. Dye-01 broke down; ORD-2003 will slip 2 days."
        />
      </Field>
      <div className="sm-row-end">
        <button className="btn btn-ghost btn-sm" onClick={onClose}>
          Cancel
        </button>
        <button className="btn btn-primary btn-sm" onClick={go} disabled={busy}>
          {busy ? "Sending…" : "Notify Supermanager"}
        </button>
      </div>
    </Dialog>
  );
}

// --------------------------------------------------------------------------- //
// Activity Logs.
// --------------------------------------------------------------------------- //
export function ProdActivity() {
  const { data, error, loading, reload } = useApi("/api/prod/activity", [
    "production",
    "tasks",
    "quality",
    "orders",
  ]);
  const [cat, setCat] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const rows = cat ? data.rows.filter((r) => r.category === cat) : data.rows;
  return (
    <div className="module sm-page">
      <PageHead
        title="Activity logs"
        sub="A trail of production, task, QC, order and material actions."
      />
      <div className="sm-tabs" role="tablist">
        <button
          role="tab"
          aria-selected={cat === ""}
          className={cat === "" ? "is-active" : ""}
          onClick={() => setCat("")}
        >
          All
        </button>
        {data.categories.map((c) => (
          <button
            key={c}
            role="tab"
            aria-selected={cat === c}
            className={cat === c ? "is-active" : ""}
            onClick={() => setCat(c)}
          >
            {c}
          </button>
        ))}
      </div>
      {rows.length === 0 ? (
        <Empty>No activity recorded.</Empty>
      ) : (
        <section className="panel">
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Who</th>
                  <th>Category</th>
                  <th>Action</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((a) => (
                  <tr key={a.id}>
                    <td>{when(a.at)}</td>
                    <td>{a.user}</td>
                    <td>
                      <Badge value="info" label={a.category} />
                    </td>
                    <td>{a.action.replace(/_/g, " ")}</td>
                    <td>{a.details}</td>
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

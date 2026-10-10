// Dispatch Planning + Create Delivery Challan, Dispatch History, and Delivery
// Confirmation for the Sales & Dispatch Manager. Dispatch creation reuses the
// existing atomic confirm (QC-approved only, no double dispatch).
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

// --------------------------------------------------------------------------- //
// Dispatch Planning + Create Delivery Challan (one action).
// --------------------------------------------------------------------------- //
export function SalesPlanning() {
  const { data, error, loading, reload } = useApi("/api/sales/planning", [
    "quality",
    "orders",
  ]);
  const [pick, setPick] = useState(null);
  const [msg, setMsg] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead title="Dispatch planning" sub={data.note} />
      <Notice onClose={() => setMsg("")}>{msg}</Notice>
      {data.orders.length === 0 ? (
        <Empty>No orders have QC-approved stock ready to dispatch.</Empty>
      ) : (
        <section className="panel">
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Buyer</th>
                  <th className="num">Ordered</th>
                  <th className="num">Ready</th>
                  <th>Deadline</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.orders.map((o) => (
                  <tr key={o.id} className={o.late ? "row-warn" : ""}>
                    <td>
                      <strong>{o.order_no}</strong>
                      <small className="sm-sub">
                        {o.fabric_type} {o.colour}
                      </small>
                    </td>
                    <td>{o.buyer}</td>
                    <td className="num">{n(o.quantity_meters)} m</td>
                    <td className="num">
                      {o.rolls_ready} · {n(o.meters_ready)} m
                    </td>
                    <td>
                      {o.deadline || "—"}{" "}
                      {o.late && <Badge value="delayed" label="Late" />}
                    </td>
                    <td>
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => setPick(o)}
                      >
                        Plan dispatch
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {pick && (
        <DispatchDialog
          order={pick}
          onClose={() => setPick(null)}
          onDone={(t) => {
            setPick(null);
            setMsg(t);
            reload();
          }}
        />
      )}
    </div>
  );
}

// Shared challan/dispatch dialog, used by Planning and Create Challan pages.
function DispatchDialog({ order, onClose, onDone }) {
  const { data, error } = useApi(`/api/sales/orders/${order.id}/pickable`, []);
  const [sel, setSel] = useState({});
  const [vehicle, setVehicle] = useState("");
  const [transporter, setTransporter] = useState("");
  const [driver, setDriver] = useState("");
  const [address, setAddress] = useState("");
  const [note, setNote] = useState("");
  const [partial, setPartial] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  if (error)
    return (
      <Dialog title="Plan dispatch" onClose={onClose}>
        <ErrorBox error={error} />
      </Dialog>
    );
  if (!data)
    return (
      <Dialog title="Plan dispatch" onClose={onClose}>
        <Loading />
      </Dialog>
    );

  const rolls = data.rolls;
  const chosen = rolls.filter((r) => sel[r.id]);
  const chosenMeters = chosen.reduce((s, r) => s + r.length_meters, 0);
  const isPartial = chosen.length > 0 && chosen.length < rolls.length;

  function toggle(id) {
    setSel((s) => ({ ...s, [id]: !s[id] }));
  }
  function all() {
    const everything = {};
    rolls.forEach((r) => (everything[r.id] = true));
    setSel(everything);
  }

  async function go() {
    if (chosen.length === 0)
      return setErr("Select at least one QC-approved roll.");
    if (isPartial && !partial)
      return setErr(
        "Not all approved rolls are selected — tick 'partial dispatch' to proceed.",
      );
    setBusy(true);
    setErr("");
    try {
      const res = await apiFetch("/api/sales/dispatch", {
        method: "POST",
        body: {
          order_id: order.id,
          roll_ids: chosen.map((r) => r.id),
          vehicle_no: vehicle.trim() || null,
          transporter: transporter.trim() || null,
          driver_phone: driver.trim() || null,
          delivery_address: address.trim() || null,
          delivery_note: note.trim() || null,
          partial: isPartial,
        },
      });
      onDone(
        `Dispatch ${res.dispatch_no} + challan ${res.challan_no} created (invoice ${res.invoice_no}).`,
      );
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog title={`Plan dispatch — ${order.order_no}`} onClose={onClose} wide>
      <p className="muted">
        {data.buyer} · ordered {n(data.quantity_meters)} m · already dispatched{" "}
        {n(data.dispatched_meters)} m
      </p>
      <ErrorBox error={err} />
      <div className="sm-row-end" style={{ justifyContent: "space-between" }}>
        <strong>QC-approved rolls ({rolls.length})</strong>
        <button className="link-btn" onClick={all}>
          Select all
        </button>
      </div>
      <div
        className="owner-table-wrap"
        style={{ maxHeight: 220, overflow: "auto" }}
      >
        <table className="data-table">
          <thead>
            <tr>
              <th></th>
              <th>Roll</th>
              <th className="num">Metres</th>
            </tr>
          </thead>
          <tbody>
            {rolls.map((r) => (
              <tr key={r.id}>
                <td>
                  <input
                    type="checkbox"
                    checked={!!sel[r.id]}
                    onChange={() => toggle(r.id)}
                  />
                </td>
                <td>
                  <code>{r.roll_no}</code>
                </td>
                <td className="num">{n(r.length_meters)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted sm-small">
        Selected: {chosen.length} rolls · {n(chosenMeters)} m
      </p>

      <Field label="Vehicle number">
        <input
          value={vehicle}
          onChange={(e) => setVehicle(e.target.value)}
          placeholder="e.g. GJ-05-AB-1234"
        />
      </Field>
      <Field label="Transporter">
        <input
          value={transporter}
          onChange={(e) => setTransporter(e.target.value)}
        />
      </Field>
      <Field label="Driver phone">
        <input value={driver} onChange={(e) => setDriver(e.target.value)} />
      </Field>
      <Field label="Delivery address" wide>
        <textarea
          rows={2}
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          placeholder={data.buyer_address || "Buyer address"}
        />
      </Field>
      <Field label="Note (optional)" wide>
        <input value={note} onChange={(e) => setNote(e.target.value)} />
      </Field>
      {isPartial && (
        <label
          className="field sm-wide"
          style={{ flexDirection: "row", gap: 8, alignItems: "center" }}
        >
          <input
            type="checkbox"
            checked={partial}
            onChange={(e) => setPartial(e.target.checked)}
          />
          <span>
            This is a partial dispatch — remaining rolls stay on the shelf.
          </span>
        </label>
      )}
      <div className="sm-row-end">
        <button className="btn btn-ghost btn-sm" onClick={onClose}>
          Cancel
        </button>
        <button className="btn btn-primary btn-sm" onClick={go} disabled={busy}>
          {busy ? "Creating…" : "Create dispatch + challan"}
        </button>
      </div>
    </Dialog>
  );
}

// --------------------------------------------------------------------------- //
// Create Delivery Challan — same workflow, entry point focused on challan.
// --------------------------------------------------------------------------- //
export function SalesChallan() {
  return (
    <div className="module sm-page">
      <PageHead
        title="Create delivery challan"
        sub="Select an order with approved stock, pick rolls and record logistics — a dispatch, challan and invoice are created together."
      />
      <ChallanPicker />
    </div>
  );
}

function ChallanPicker() {
  const { data, error, loading, reload } = useApi("/api/sales/planning", [
    "quality",
    "orders",
  ]);
  const [pick, setPick] = useState(null);
  const [msg, setMsg] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <>
      <Notice onClose={() => setMsg("")}>{msg}</Notice>
      {data.orders.length === 0 ? (
        <Empty>No orders with approved stock to raise a challan for.</Empty>
      ) : (
        <section className="panel">
          <div className="sm-cards">
            {data.orders.map((o) => (
              <article key={o.id} className="sm-person">
                <header>
                  <div>
                    <strong>{o.order_no}</strong>
                    <small className="muted">{o.buyer}</small>
                  </div>
                  <Badge
                    value="ready_to_ship"
                    label={`${o.rolls_ready} rolls`}
                  />
                </header>
                <p className="muted sm-small">
                  {o.fabric_type} {o.colour} · {n(o.meters_ready)} m ready · due{" "}
                  {o.deadline || "—"}
                </p>
                <div className="sm-row-end">
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => setPick(o)}
                  >
                    Create challan
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}
      {pick && (
        <DispatchDialog
          order={pick}
          onClose={() => setPick(null)}
          onDone={(t) => {
            setPick(null);
            setMsg(t);
            reload();
          }}
        />
      )}
    </>
  );
}

// --------------------------------------------------------------------------- //
// Dispatch History.
// --------------------------------------------------------------------------- //
export function SalesHistory() {
  const { data, error, loading, reload } = useApi("/api/sales/history", [
    "orders",
    "quality",
  ]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead
        title="Dispatch history"
        sub="Every dispatch with its challan, logistics, rolls and invoice."
      />
      {data.dispatches.length === 0 ? (
        <Empty>No dispatches recorded yet.</Empty>
      ) : (
        <section className="panel">
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Dispatch</th>
                  <th>Challan</th>
                  <th>Order · buyer</th>
                  <th className="num">Rolls / m</th>
                  <th>Vehicle · transporter</th>
                  <th>Invoice</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.dispatches.map((d) => (
                  <tr key={d.id}>
                    <td>
                      <strong>{d.dispatch_no}</strong>
                      <small className="sm-sub">{when(d.dispatched_at)}</small>
                    </td>
                    <td>{d.challan_no || "—"}</td>
                    <td>
                      {d.order_no}
                      <small className="sm-sub">{d.buyer}</small>
                    </td>
                    <td className="num">
                      {d.total_rolls} · {n(d.total_meters)} m
                    </td>
                    <td>
                      {d.vehicle_no || "—"}
                      <small className="sm-sub">{d.transporter || ""}</small>
                    </td>
                    <td>{d.invoice_no || <span className="muted">—</span>}</td>
                    <td>
                      <Badge
                        value={d.delivered_at ? "shipped" : "packed"}
                        label={d.delivered_at ? "Delivered" : d.status}
                      />
                    </td>
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
// Delivery Confirmation.
// --------------------------------------------------------------------------- //
export function SalesDelivery() {
  const { data, error, loading, reload } = useApi("/api/sales/deliveries", [
    "orders",
  ]);
  const [confirm, setConfirm] = useState(null);
  const [msg, setMsg] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;

  async function setStatus(d, status) {
    try {
      await apiFetch(`/api/sales/dispatch/${d.id}/status`, {
        method: "POST",
        body: { status },
      });
      setMsg(`${d.dispatch_no} marked ${status}.`);
      reload();
    } catch (e) {
      setMsg(e.message);
    }
  }

  return (
    <div className="module sm-page">
      <PageHead
        title="Delivery confirmation"
        sub="Mark dispatches loaded/shipped and confirm delivery. Delivery notifies the Supermanager and Accounts for payment follow-up."
      />
      <Notice onClose={() => setMsg("")}>{msg}</Notice>

      <section className={`panel ${data.pending.length ? "sm-attention" : ""}`}>
        <h3>In transit / awaiting delivery</h3>
        {data.pending.length === 0 ? (
          <Empty>No dispatches awaiting delivery.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Dispatch</th>
                  <th>Order · buyer</th>
                  <th className="num">Rolls / m</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.pending.map((d) => (
                  <tr key={d.id}>
                    <td>
                      <strong>{d.dispatch_no}</strong>
                      <small className="sm-sub">{d.challan_no}</small>
                    </td>
                    <td>
                      {d.order_no}
                      <small className="sm-sub">{d.buyer}</small>
                    </td>
                    <td className="num">
                      {d.total_rolls} · {n(d.total_meters)} m
                    </td>
                    <td>
                      <Badge
                        value={d.status === "loaded" ? "loaded" : "packed"}
                        label={d.status}
                      />
                    </td>
                    <td>
                      <div className="sm-actions">
                        {d.status !== "loaded" && (
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => setStatus(d, "loaded")}
                          >
                            Loaded
                          </button>
                        )}
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => setConfirm(d)}
                        >
                          Confirm delivery
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

      <section className="panel">
        <h3>Delivered</h3>
        {data.delivered.length === 0 ? (
          <Empty>No deliveries confirmed yet.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Dispatch</th>
                  <th>Order · buyer</th>
                  <th className="num">Metres</th>
                  <th>Delivered</th>
                </tr>
              </thead>
              <tbody>
                {data.delivered.map((d) => (
                  <tr key={d.id}>
                    <td>{d.dispatch_no}</td>
                    <td>
                      {d.order_no}
                      <small className="sm-sub">{d.buyer}</small>
                    </td>
                    <td className="num">{n(d.total_meters)} m</td>
                    <td>{when(d.delivered_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {confirm && (
        <DeliverDialog
          dispatch={confirm}
          onClose={() => setConfirm(null)}
          onDone={(t) => {
            setConfirm(null);
            setMsg(t);
            reload();
          }}
        />
      )}
    </div>
  );
}

function DeliverDialog({ dispatch, onClose, onDone }) {
  const [receivedBy, setReceivedBy] = useState("");
  const [note, setNote] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function go() {
    setBusy(true);
    setErr("");
    try {
      await apiFetch(`/api/sales/dispatch/${dispatch.id}/deliver`, {
        method: "POST",
        body: {
          received_by: receivedBy.trim() || null,
          note: note.trim() || null,
        },
      });
      onDone(
        `${dispatch.dispatch_no} delivered. Supermanager and Accounts notified.`,
      );
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title={`Confirm delivery — ${dispatch.dispatch_no}`}
      onClose={onClose}
    >
      <p className="muted">
        {dispatch.order_no} · {dispatch.buyer} · {n(dispatch.total_meters)} m
      </p>
      <ErrorBox error={err} />
      <Field label="Received by (optional)">
        <input
          value={receivedBy}
          onChange={(e) => setReceivedBy(e.target.value)}
        />
      </Field>
      <Field label="Note (optional)">
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
          {busy ? "Saving…" : "Confirm delivery"}
        </button>
      </div>
    </Dialog>
  );
}

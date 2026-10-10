// Production Orders, Production Planning and Production Stages for the
// Production Manager. All read the live tables; planning assigns a machine +
// stage + target to a confirmed order.
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
  useApi,
} from "../../../components/super/kit.jsx";
import "../../../owner.css";

const n = (v) => Number(v || 0).toLocaleString("en-IN");

// --------------------------------------------------------------------------- //
// Production Orders — confirmed work handed down by the Supermanager.
// --------------------------------------------------------------------------- //
export function ProdOrders() {
  const { data, error, loading, reload } = useApi("/api/prod/orders", [
    "orders",
    "production",
  ]);
  const [status, setStatus] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const rows = status
    ? data.orders.filter((o) => o.status === status)
    : data.orders;
  return (
    <div className="module sm-page">
      <PageHead title="Production orders" sub={data.note} />
      <div className="sm-tabs" role="tablist">
        {[
          ["", "All"],
          ["confirmed", "Confirmed"],
          ["in_production", "In production"],
          ["in_quality", "In QC"],
          ["ready_to_ship", "Ready to ship"],
        ].map(([k, l]) => (
          <button
            key={k || "all"}
            role="tab"
            aria-selected={status === k}
            className={status === k ? "is-active" : ""}
            onClick={() => setStatus(k)}
          >
            {l}
          </button>
        ))}
      </div>
      {rows.length === 0 ? (
        <Empty>No orders in this view.</Empty>
      ) : (
        <section className="panel">
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Buyer</th>
                  <th>Fabric</th>
                  <th className="num">Ordered</th>
                  <th className="num">Made</th>
                  <th>Progress</th>
                  <th>Deadline</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((o) => (
                  <tr key={o.id} className={o.late ? "row-warn" : ""}>
                    <td>
                      <strong>{o.order_no}</strong>
                    </td>
                    <td>{o.buyer}</td>
                    <td>
                      {o.fabric_type} · {o.colour}
                    </td>
                    <td className="num">{n(o.quantity_meters)} m</td>
                    <td className="num">{n(o.produced_meters)} m</td>
                    <td>
                      <span className="sm-progress" title={`${o.progress}%`}>
                        <i style={{ width: `${o.progress}%` }} />
                      </span>{" "}
                      <small>{o.progress}%</small>
                    </td>
                    <td>
                      {o.deadline || "—"}{" "}
                      {o.delay && (
                        <Badge
                          value={o.delay === "late" ? "delayed" : "warning"}
                          label={o.delay === "late" ? "Late" : "At risk"}
                        />
                      )}
                    </td>
                    <td>
                      <Badge value={o.status} />
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
// Production Planning — assign machine + stage + target.
// --------------------------------------------------------------------------- //
export function ProdPlanning() {
  const { data, error, loading, reload } = useApi("/api/prod/planning", [
    "orders",
    "production",
    "machines",
    "yarn",
  ]);
  const [plan, setPlan] = useState(null); // order being planned
  const [msg, setMsg] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;

  const shortageFor = (orderNo) =>
    data.shortages.find((s) => s.order_no === orderNo);

  return (
    <div className="module sm-page">
      <PageHead
        title="Production planning"
        sub="Check materials, machines and deadlines, then assign a machine, stage and target to each order."
      />
      <Notice onClose={() => setMsg("")}>{msg}</Notice>

      <div className="sm-grid-2">
        <section className="panel">
          <h3>Machine capacity</h3>
          <div className="sm-machines">
            {data.machines.map((m) => (
              <article
                key={m.id}
                className={`sm-machine is-${m.status === "maintenance" ? "breakdown" : m.status}`}
              >
                <header>
                  <strong>{m.name}</strong>
                  <Badge value={m.status} />
                </header>
                <small className="muted">{m.type}</small>
                <p>
                  {m.order_no
                    ? `On ${m.order_no}${m.stage ? ` (${m.stage})` : ""}`
                    : "Free"}
                </p>
              </article>
            ))}
          </div>
        </section>

        <section className="panel">
          <h3>Orders to plan</h3>
          {data.orders.length === 0 ? (
            <Empty>No confirmed orders waiting for a plan.</Empty>
          ) : (
            <div className="owner-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Order</th>
                    <th className="num">Ordered</th>
                    <th>Deadline</th>
                    <th>Material</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {data.orders.map((o) => {
                    const short = shortageFor(o.order_no);
                    return (
                      <tr key={o.id} className={o.late ? "row-warn" : ""}>
                        <td>
                          <strong>{o.order_no}</strong>
                          <small className="sm-sub">
                            {o.buyer} · {o.fabric_type} {o.colour}
                          </small>
                        </td>
                        <td className="num">{n(o.quantity_meters)} m</td>
                        <td>
                          {o.deadline || "—"}
                          {o.days_left != null && (
                            <small className="sm-sub">
                              {o.days_left} days left
                            </small>
                          )}
                        </td>
                        <td>
                          {short ? (
                            <Badge
                              value="critical"
                              label={`Short ${n(short.short_kg)} kg`}
                            />
                          ) : (
                            <Badge value="ok" label="Covered" />
                          )}
                        </td>
                        <td>
                          <button
                            className="btn btn-primary btn-sm"
                            onClick={() => setPlan(o)}
                          >
                            Plan
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {plan && (
        <PlanDialog
          order={plan}
          machines={data.machines}
          stages={data.stages}
          onClose={() => setPlan(null)}
          onDone={(t) => {
            setPlan(null);
            setMsg(t);
            reload();
          }}
        />
      )}
    </div>
  );
}

function PlanDialog({ order, machines, stages, onClose, onDone }) {
  const [stage, setStage] = useState(stages[0]);
  const [machineId, setMachineId] = useState("");
  const [target, setTarget] = useState("");
  const [shift, setShift] = useState("morning");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const fit = machines.filter((m) => m.type === stage);

  async function go() {
    if (!machineId) return setErr("Pick a machine for this stage.");
    setBusy(true);
    setErr("");
    try {
      await apiFetch("/api/prod/plan", {
        method: "POST",
        body: {
          order_id: order.id,
          machine_id: Number(machineId),
          stage,
          target_meters: target ? Number(target) : null,
          shift,
        },
      });
      onDone(`Plan saved: ${order.order_no} → ${stage}.`);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog title={`Plan ${order.order_no}`} onClose={onClose}>
      <p className="muted">
        {order.fabric_type} {order.colour} · {n(order.quantity_meters)} m · due{" "}
        {order.deadline || "—"}
      </p>
      <ErrorBox error={err} />
      <Field label="Stage">
        <select
          value={stage}
          onChange={(e) => {
            setStage(e.target.value);
            setMachineId("");
          }}
        >
          {stages.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Machine">
        <select
          value={machineId}
          onChange={(e) => setMachineId(e.target.value)}
          autoFocus
        >
          <option value="">Select a {stage} machine…</option>
          {fit.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name} ({m.status})
              {m.order_no ? ` — busy with ${m.order_no}` : ""}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Target (metres this shift, optional)">
        <input
          type="number"
          min="0"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
        />
      </Field>
      <Field label="Shift">
        <select value={shift} onChange={(e) => setShift(e.target.value)}>
          <option value="morning">Morning</option>
          <option value="evening">Evening</option>
          <option value="night">Night</option>
        </select>
      </Field>
      <div className="sm-row-end">
        <button className="btn btn-ghost btn-sm" onClick={onClose}>
          Cancel
        </button>
        <button className="btn btn-primary btn-sm" onClick={go} disabled={busy}>
          {busy ? "Saving…" : "Save plan"}
        </button>
      </div>
    </Dialog>
  );
}

// --------------------------------------------------------------------------- //
// Production Stages — spinning / weaving / dyeing.
// --------------------------------------------------------------------------- //
export function ProdStages() {
  const { data, error, loading, reload } = useApi("/api/prod/stages", [
    "production",
    "machines",
    "orders",
  ]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const order = ["spinning", "weaving", "dyeing"];
  return (
    <div className="module sm-page">
      <PageHead
        title="Production stages"
        sub="Spinning → weaving → dyeing. Output and running machines at each stage."
      />
      <div className="sm-stats sm-stats-4">
        {order.map((s) => (
          <Stat
            key={s}
            label={s[0].toUpperCase() + s.slice(1)}
            value={`${n(data.stages[s].total_meters)} m`}
            hint={`${data.stages[s].running} running · ${n(data.stages[s].today_meters)} m today`}
            tone={data.stages[s].running ? "green" : undefined}
          />
        ))}
      </div>
      {order.map((s) => (
        <section className="panel" key={s}>
          <h3>{s[0].toUpperCase() + s.slice(1)}</h3>
          <div className="sm-machines">
            {data.stages[s].machines.map((m) => (
              <article
                key={m.id}
                className={`sm-machine is-${m.status === "maintenance" ? "breakdown" : m.status}`}
              >
                <header>
                  <strong>{m.name}</strong>
                  <Badge value={m.status} />
                </header>
                <p>{m.order_no ? `On ${m.order_no}` : "No order loaded"}</p>
                <small>{n(m.total_meters)} m made in total</small>
              </article>
            ))}
          </div>
          {data.stages[s].orders.length > 0 && (
            <div className="owner-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Order</th>
                    <th className="num">{s} metres</th>
                    <th className="num">Ordered</th>
                  </tr>
                </thead>
                <tbody>
                  {data.stages[s].orders.map((o) => (
                    <tr key={o.order_no}>
                      <td>{o.order_no}</td>
                      <td className="num">{n(o.stage_meters)}</td>
                      <td className="num">{n(o.quantity_meters)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ))}
    </div>
  );
}

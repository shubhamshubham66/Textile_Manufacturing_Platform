// Read-only monitoring pages for the Supermanager: production, inventory,
// quality control and dispatch. Data is live; changes are made by the
// department screens.
import { useState } from "react";
import { Badge, Empty, ErrorBox, Loading, PageHead, Stat, day, when, useApi } from "../../../components/super/kit.jsx";
import "../../../owner.css";

const n = (v) => Number(v || 0).toLocaleString("en-IN");

function Exceptions({ rows, empty }) {
  if (!rows.length) return <Empty>{empty}</Empty>;
  return (
    <ul className="sm-exceptions">
      {rows.map((e, i) => (
        <li key={i}>
          <span aria-hidden>!</span> {e.detail || e.notes}
        </li>
      ))}
    </ul>
  );
}

// --------------------------------------------------------------------------- //
export function SuperProduction() {
  const { data, error, loading, reload } = useApi("/api/super/production", ["production", "machines", "orders"]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const mc = data.machine_counts;
  return (
    <div className="module sm-page">
      <PageHead title="Production monitoring" sub="Progress of every confirmed order and the state of each machine." />
      <div className="sm-stats sm-stats-4">
        <Stat label="Machines running" value={mc.running} tone="green" />
        <Stat label="Idle" value={mc.idle} tone={mc.idle ? "amber" : undefined} />
        <Stat label="Maintenance / breakdown" value={mc.maintenance} tone={mc.maintenance ? "red" : undefined} />
        <Stat label="Orders delayed or at risk" value={data.delays.length} tone={data.delays.length ? "red" : undefined} />
      </div>

      {(data.delays.length > 0 || data.breakdowns.length > 0) && (
        <section className="panel sm-attention">
          <h3>Needs attention</h3>
          <ul className="sm-exceptions">
            {data.breakdowns.map((m) => (
              <li key={`m${m.id}`}>
                <span aria-hidden>!</span> <strong>{m.name}</strong> is down since {when(m.since)}
                {m.last_breakdown_reason ? ` — ${m.last_breakdown_reason}` : ""}.
              </li>
            ))}
            {data.delays.map((o) => (
              <li key={`o${o.id}`}>
                <span aria-hidden>!</span> <strong>{o.order_no}</strong>{" "}
                {o.delay === "late" ? `is past its deadline (${day(o.deadline)})` : `is due in ${o.days_left} days`} with {o.progress}% made.
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="panel">
        <h3>Orders by stage</h3>
        {data.orders.length === 0 ? (
          <Empty>No confirmed orders in the pipeline.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Order</th>
                  <th className="num">Ordered</th>
                  <th className="num">Spinning</th>
                  <th className="num">Weaving</th>
                  <th className="num">Dyeing</th>
                  <th>Progress</th>
                  <th>Deadline</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.orders.map((o) => (
                  <tr key={o.id} className={o.delay === "late" ? "row-warn" : ""}>
                    <td>
                      <strong>{o.order_no}</strong>
                      <small className="sm-sub">
                        {o.buyer} · {o.fabric_type} {o.colour}
                      </small>
                    </td>
                    <td className="num">{n(o.quantity_meters)} m</td>
                    <td className="num">{n(o.stages.spinning)}</td>
                    <td className="num">{n(o.stages.weaving)}</td>
                    <td className="num">{n(o.stages.dyeing)}</td>
                    <td>
                      <span className="sm-progress" title={`${o.progress}%`}>
                        <i style={{ width: `${o.progress}%` }} />
                      </span>{" "}
                      <small>{o.progress}%</small>
                    </td>
                    <td>
                      {day(o.deadline)} {o.delay && <Badge value={o.delay === "late" ? "delayed" : "warning"} label={o.delay === "late" ? "Late" : "At risk"} />}
                    </td>
                    <td>
                      <Badge value={o.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="muted sm-small">Metres logged at each stage by the floor supervisor.</p>
      </section>

      <section className="panel">
        <h3>Machines</h3>
        <div className="sm-machines">
          {data.machines.map((m) => (
            <article key={m.id} className={`sm-machine is-${m.status}`}>
              <header>
                <strong>{m.name}</strong>
                <Badge value={m.status} />
              </header>
              <small className="muted">
                {m.type} · since {when(m.since)}
              </small>
              <p>{m.order_no ? `On ${m.order_no}${m.stage ? ` (${m.stage})` : ""}` : "No order loaded"}</p>
              <small>{n(m.total_meters)} m made in total</small>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

// --------------------------------------------------------------------------- //
export function SuperInventory() {
  const { data, error, loading, reload } = useApi("/api/super/inventory", ["yarn", "quality", "orders"]);
  const [tab, setTab] = useState("yarn");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead title="Inventory monitoring" sub="Yarn in the store, finished rolls, stock movements and anything that does not add up." />
      <div className="sm-stats sm-stats-4">
        <Stat label="Yarn in stock" value={`${n(data.totals.yarn_kg)} kg`} hint={`${data.totals.lines} lines`} />
        <Stat label="Low-stock lines" value={data.low_stock.length} tone={data.low_stock.length ? "red" : undefined} />
        <Stat label="Finished rolls ready" value={data.totals.rolls_ready} hint={`${n(data.finished_meters)} m passed QC`} />
        <Stat label="Stock exceptions" value={data.exceptions.length} tone={data.exceptions.length ? "amber" : undefined} />
      </div>

      {data.low_stock.length > 0 && (
        <div className="callout callout-warn">
          <strong>Low stock:</strong>{" "}
          {data.low_stock.map((s) => `${s.yarn_type} ${s.colour} (${n(s.quantity_kg)} kg)`).join(", ")}
        </div>
      )}

      <section className="panel">
        <div className="sm-tabs" role="tablist">
          {[
            ["yarn", "Raw material (yarn)"],
            ["rolls", "Finished fabric rolls"],
            ["moves", "Stock movements"],
            ["dispatch", "Dispatch history"],
            ["exceptions", `Exceptions (${data.exceptions.length})`],
          ].map(([k, l]) => (
            <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "is-active" : ""} onClick={() => setTab(k)}>
              {l}
            </button>
          ))}
        </div>

        {tab === "yarn" && (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Yarn</th>
                  <th>Colour</th>
                  <th className="num">In stock</th>
                  <th className="num">Reorder at</th>
                  <th>Level</th>
                </tr>
              </thead>
              <tbody>
                {data.yarn.map((s) => (
                  <tr key={s.id} className={s.low ? "row-warn" : ""}>
                    <td>{s.yarn_type}</td>
                    <td>{s.colour}</td>
                    <td className="num">{n(s.quantity_kg)} kg</td>
                    <td className="num">{n(s.reorder_level_kg)} kg</td>
                    <td>{s.low ? <Badge value="critical" label="Low" /> : <Badge value="ok" />}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {tab === "rolls" &&
          (data.rolls.length === 0 ? (
            <Empty>No finished rolls in the store.</Empty>
          ) : (
            <div className="owner-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Roll ID</th>
                    <th>Order</th>
                    <th>Fabric</th>
                    <th className="num">Metres</th>
                    <th>QC</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rolls.map((r) => (
                    <tr key={r.roll_no}>
                      <td>
                        <code>{r.roll_no}</code>
                      </td>
                      <td>{r.order_no}</td>
                      <td>{r.fabric}</td>
                      <td className="num">{n(r.length_meters)}</td>
                      <td>
                        <Badge value={r.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        {(tab === "moves" || tab === "dispatch") && (
          <Movements rows={tab === "moves" ? data.movements : data.dispatch_history} />
        )}
        {tab === "exceptions" && <Exceptions rows={data.exceptions} empty="Stock, receipts and dispatched rolls all add up." />}
      </section>
    </div>
  );
}

function Movements({ rows }) {
  if (!rows.length) return <Empty>No movements recorded yet.</Empty>;
  return (
    <div className="owner-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>When</th>
            <th>Type</th>
            <th>What</th>
            <th>Quantity</th>
            <th>Party / by</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((m, i) => (
            <tr key={i}>
              <td>{when(m.at)}</td>
              <td>
                <Badge value={m.kind === "in" ? "ok" : m.kind === "out" ? "info" : "warning"} label={m.kind === "in" ? "In" : m.kind === "out" ? "Out" : "Adjusted"} />
              </td>
              <td>{m.what}</td>
              <td>{m.qty}</td>
              <td>{m.party}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --------------------------------------------------------------------------- //
export function SuperQuality() {
  const { data, error, loading, reload } = useApi("/api/super/quality", ["quality", "production"]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const r = data.results;
  return (
    <div className="module sm-page">
      <PageHead title="Quality control" sub="Rolls waiting for inspection, results, defects and quality status per order." />
      <div className="sm-stats sm-stats-4">
        <Stat label="Awaiting inspection" value={data.pending.length} tone={data.pending.length ? "amber" : undefined} />
        <Stat label="Passed" value={r.pass.rolls} hint={`${n(r.pass.meters)} m`} tone="green" />
        <Stat label="Rework" value={r.rework.rolls} hint={`${n(r.rework.meters)} m`} tone={r.rework.rolls ? "amber" : undefined} />
        <Stat label="Rejected" value={r.reject.rolls} hint={`${n(r.reject.meters)} m`} tone={r.reject.rolls ? "red" : undefined} />
      </div>
      <p className="callout callout-ok sm-small">
        {data.rule} {data.dispatch_eligible} rolls are approved for dispatch now.
      </p>

      <div className="sm-grid-2">
        <section className="panel">
          <h3>Rolls awaiting inspection</h3>
          {data.pending.length === 0 ? (
            <Empty>Nothing waiting — every roll has been checked.</Empty>
          ) : (
            <div className="owner-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Roll</th>
                    <th>Order</th>
                    <th className="num">Metres</th>
                    <th>Machine</th>
                  </tr>
                </thead>
                <tbody>
                  {data.pending.map((p) => (
                    <tr key={p.roll_no}>
                      <td>
                        <code>{p.roll_no}</code>
                      </td>
                      <td>{p.order_no}</td>
                      <td className="num">{n(p.length_meters)}</td>
                      <td>{p.machine}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
        <section className="panel">
          <h3>Defects found</h3>
          {data.defects.length === 0 ? (
            <Empty>No defects recorded.</Empty>
          ) : (
            <ul className="sm-bars">
              {data.defects.map((d) => (
                <li key={d.defect}>
                  <span>{d.defect.replace(/_/g, " ")}</span>
                  <i style={{ width: `${(d.count / data.defects[0].count) * 100}%` }} />
                  <b>{d.count}</b>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="panel">
        <h3>Quality status by order</h3>
        {data.orders.length === 0 ? (
          <Empty>No rolls inspected yet.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Order</th>
                  <th className="num">Pass</th>
                  <th className="num">Rework</th>
                  <th className="num">Reject</th>
                  <th className="num">Waiting</th>
                  <th>Quality</th>
                </tr>
              </thead>
              <tbody>
                {data.orders.map((o) => (
                  <tr key={o.order_no}>
                    <td>{o.order_no}</td>
                    <td className="num">{o.pass}</td>
                    <td className="num">{o.rework}</td>
                    <td className="num">{o.reject}</td>
                    <td className="num">{o.waiting}</td>
                    <td>
                      <Badge value={o.quality} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel">
        <h3>QC exceptions</h3>
        {data.exceptions.length === 0 ? (
          <Empty>No rework, rejects or unapproved dispatches.</Empty>
        ) : (
          <ul className="sm-exceptions">
            {data.exceptions.map((e, i) => (
              <li key={i}>
                <span aria-hidden>!</span>
                {e.roll_no ? (
                  <>
                    Roll <code>{e.roll_no}</code> ({e.order_no}) — <Badge value={e.result} />
                    {e.defect && e.defect !== "none" ? ` ${e.defect.replace(/_/g, " ")}` : ""}
                    {e.notes ? ` · ${e.notes}` : ""}
                  </>
                ) : (
                  e.notes
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

// --------------------------------------------------------------------------- //
export function SuperDispatch() {
  const { data, error, loading, reload } = useApi("/api/super/dispatch", ["orders", "quality"]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead title="Dispatch monitoring" sub="Orders ready to ship, loading progress, and checks on buyer, rolls, quantity and invoice." />
      <div className="sm-stats sm-stats-4">
        <Stat label="Ready for dispatch" value={data.ready.length} />
        <Stat label="Packed" value={data.progress.packed} />
        <Stat label="Loaded" value={data.progress.loaded} />
        <Stat label="Exceptions" value={data.exceptions.length} tone={data.exceptions.length ? "red" : undefined} />
      </div>

      <section className={`panel ${data.exceptions.length ? "sm-attention" : ""}`}>
        <h3>Dispatch exceptions</h3>
        <Exceptions rows={data.exceptions} empty="Buyer, roll IDs, quantities and invoices all match. No duplicate dispatches." />
      </section>

      <section className="panel">
        <h3>Ready for dispatch</h3>
        {data.ready.length === 0 ? (
          <Empty>No orders are waiting to ship.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Buyer</th>
                  <th className="num">Ordered</th>
                  <th className="num">Passed rolls</th>
                  <th>Deadline</th>
                </tr>
              </thead>
              <tbody>
                {data.ready.map((o) => (
                  <tr key={o.id}>
                    <td>{o.order_no}</td>
                    <td>{o.buyer}</td>
                    <td className="num">{n(o.quantity_meters)} m</td>
                    <td className="num">
                      {o.rolls_ready} · {n(o.meters_ready)} m
                    </td>
                    <td>{day(o.deadline)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel">
        <h3>Dispatches</h3>
        {data.dispatches.length === 0 ? (
          <Empty>No dispatches yet.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Dispatch</th>
                  <th>Order · buyer</th>
                  <th>Roll IDs</th>
                  <th className="num">Metres (ordered)</th>
                  <th>Invoice</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.dispatches.map((d) => (
                  <tr key={d.dispatch_no}>
                    <td>
                      {d.dispatch_no}
                      <small className="sm-sub">{when(d.at)}</small>
                    </td>
                    <td>
                      {d.order_no}
                      <small className="sm-sub">{d.buyer}</small>
                    </td>
                    <td className="sm-rolls">{d.rolls.join(", ") || "—"}</td>
                    <td className="num">
                      {n(d.total_meters)} <small className="muted">({n(d.ordered_meters)})</small>
                    </td>
                    <td>{d.invoice_no || <span className="muted">none</span>}</td>
                    <td>
                      <Badge value={d.status} />
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

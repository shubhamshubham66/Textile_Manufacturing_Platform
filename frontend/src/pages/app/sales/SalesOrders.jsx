// Buyer Orders, Buyer Management, Order Status Tracking and QC-Approved Stock
// for the Sales & Dispatch Manager. All read-only views of live data.
import { useState } from "react";
import {
  Badge,
  Empty,
  ErrorBox,
  Loading,
  PageHead,
  Stat,
  useApi,
} from "../../../components/super/kit.jsx";
import "../../../owner.css";

const n = (v) => Number(v || 0).toLocaleString("en-IN");
const rupee = (v) =>
  `₹${Number(v || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

// --------------------------------------------------------------------------- //
export function SalesBuyerOrders() {
  const { data, error, loading, reload } = useApi("/api/sales/orders", [
    "orders",
    "quality",
  ]);
  const [status, setStatus] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const rows = status
    ? data.orders.filter((o) => o.status === status)
    : data.orders;
  return (
    <div className="module sm-page">
      <PageHead title="Buyer orders" sub={data.note} />
      <div className="sm-tabs" role="tablist">
        <button
          role="tab"
          aria-selected={status === ""}
          className={status === "" ? "is-active" : ""}
          onClick={() => setStatus("")}
        >
          All
        </button>
        {data.statuses.map((s) => (
          <button
            key={s.key}
            role="tab"
            aria-selected={status === s.key}
            className={status === s.key ? "is-active" : ""}
            onClick={() => setStatus(s.key)}
          >
            {s.label}
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
                  <th className="num">Dispatched</th>
                  <th className="num">Ready</th>
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
                    <td className="num">{n(o.dispatched_meters)} m</td>
                    <td className="num">{o.rolls_ready} rolls</td>
                    <td>{o.deadline || "—"}</td>
                    <td>
                      <Badge
                        value={badgeFor(o.status)}
                        label={o.status_label}
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

function badgeFor(status) {
  return (
    {
      confirmed: "confirmed",
      in_production: "in_production",
      in_quality: "in_quality",
      ready_to_ship: "ready_to_ship",
      partially_dispatched: "waiting",
      dispatched: "dispatched",
      closed: "closed",
    }[status] || "info"
  );
}

// --------------------------------------------------------------------------- //
export function SalesBuyers() {
  const { data, error, loading, reload } = useApi("/api/sales/buyers", [
    "orders",
  ]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead title="Buyer management" sub={data.note} />
      <section className="panel">
        <div className="sm-cards">
          {data.buyers.map((b) => (
            <article key={b.id} className="sm-person">
              <header>
                <span className="avatar">
                  {b.name
                    .split(" ")
                    .map((p) => p[0])
                    .slice(0, 2)
                    .join("")}
                </span>
                <div>
                  <strong>{b.name}</strong>
                  <small className="muted">{b.contact_person || "—"}</small>
                </div>
              </header>
              <dl className="sm-mini">
                <div>
                  <dt>Phone</dt>
                  <dd>{b.phone || "—"}</dd>
                </div>
                <div>
                  <dt>Email</dt>
                  <dd>{b.email || "—"}</dd>
                </div>
                <div>
                  <dt>Active orders</dt>
                  <dd>{b.active_orders}</dd>
                </div>
                <div>
                  <dt>Delivered</dt>
                  <dd>{b.delivered_orders}</dd>
                </div>
                <div>
                  <dt>Invoiced</dt>
                  <dd>{rupee(b.invoiced_total)}</dd>
                </div>
              </dl>
              {b.address && <p className="muted sm-small">{b.address}</p>}
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

// --------------------------------------------------------------------------- //
export function SalesTracking() {
  const { data, error, loading, reload } = useApi("/api/sales/tracking", [
    "orders",
    "quality",
  ]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead
        title="Order status tracking"
        sub="Live stage of every order: Confirmed → In Production → QC Pending → Ready → Dispatched → Delivered."
      />
      <section className="panel">
        <div className="owner-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Order</th>
                <th>Buyer</th>
                <th>Progress</th>
                <th>Deadline</th>
                <th>Status</th>
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
                  <td>
                    <span className="sm-progress" title={`${o.progress}%`}>
                      <i style={{ width: `${o.progress}%` }} />
                    </span>{" "}
                    <small>{o.progress}%</small>
                  </td>
                  <td>
                    {o.deadline || "—"}{" "}
                    {o.late && <Badge value="delayed" label="Late" />}
                  </td>
                  <td>
                    <Badge value={badgeFor(o.status)} label={o.status_label} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

// --------------------------------------------------------------------------- //
export function SalesStock() {
  const { data, error, loading, reload } = useApi("/api/sales/stock", [
    "quality",
    "orders",
  ]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead title="QC-approved finished stock" sub={data.rule} />
      <div className="sm-stats sm-stats-4">
        <Stat
          label="Approved rolls on shelf"
          value={n(data.total_rolls)}
          tone={data.total_rolls ? "green" : undefined}
        />
        <Stat label="Approved metres" value={`${n(data.total_meters)} m`} />
        <Stat label="Orders with stock" value={data.stock.length} />
      </div>
      {data.stock.length === 0 ? (
        <Empty>No QC-approved stock on the shelf right now.</Empty>
      ) : (
        <section className="panel">
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Buyer</th>
                  <th>Fabric</th>
                  <th className="num">Rolls</th>
                  <th className="num">Metres</th>
                  <th>Roll IDs</th>
                </tr>
              </thead>
              <tbody>
                {data.stock.map((s) => (
                  <tr key={s.order_no}>
                    <td>
                      <strong>{s.order_no}</strong>
                    </td>
                    <td>{s.buyer}</td>
                    <td>{s.fabric}</td>
                    <td className="num">{s.rolls}</td>
                    <td className="num">{n(s.meters)}</td>
                    <td className="sm-rolls">{s.roll_nos.join(", ")}</td>
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

// Buyer dashboard — the six cards from live data (/api/buyer/dashboard),
// scoped to the logged-in buyer. Reuses the shared super UI kit.
import {
  Badge,
  Empty,
  ErrorBox,
  Loading,
  PageHead,
  Stat,
  go,
  useApi,
} from "../../../components/super/kit.jsx";
import "../../../owner.css";

const n = (v) => Number(v || 0).toLocaleString("en-IN");
const rupee = (v) =>
  `₹${Number(v || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

export default function BuyerDashboard() {
  const { data, error, loading, reload } = useApi("/api/buyer/dashboard", [
    "orders",
    "quality",
    "production",
    "payments",
  ]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const c = data.cards;

  return (
    <div className="module sm-page">
      <PageHead
        title="My dashboard"
        sub="Your orders, their stage, and payments — all in one place."
      />

      <div className="sm-stats sm-stats-4">
        <Stat
          label="My orders"
          value={c.my_orders}
          onClick={() => go("/app/by-orders")}
        />
        <Stat
          label="Pending orders"
          value={c.pending}
          hint="awaiting confirmation"
          tone={c.pending ? "amber" : undefined}
          onClick={() => go("/app/by-orders")}
        />
        <Stat
          label="In production"
          value={c.in_production}
          tone={c.in_production ? "blue" : undefined}
          onClick={() => go("/app/by-track")}
        />
        <Stat
          label="QC status"
          value={c.qc_status}
          hint="in inspection"
          onClick={() => go("/app/by-track")}
        />
      </div>
      <div className="sm-stats sm-stats-4">
        <Stat
          label="Ready for dispatch"
          value={c.ready_for_dispatch}
          tone={c.ready_for_dispatch ? "teal" : undefined}
          onClick={() => go("/app/by-track")}
        />
        <Stat
          label="Dispatched / delivered"
          value={c.dispatched}
          tone="green"
          onClick={() => go("/app/by-delivery")}
        />
        <Stat
          label="Outstanding payment"
          value={rupee(data.outstanding_payment)}
          tone={data.outstanding_payment ? "amber" : "green"}
          onClick={() => go("/app/by-invoices")}
        />
      </div>

      <section className="panel">
        <div className="sm-panel-head">
          <h3>Recent orders</h3>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => go("/app/by-new-order")}
          >
            ＋ Place new order
          </button>
        </div>
        {data.recent_orders.length === 0 ? (
          <Empty>
            You have no orders yet. Browse products and place your first order.
          </Empty>
        ) : (
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
                </tr>
              </thead>
              <tbody>
                {data.recent_orders.map((o) => (
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
                    </td>
                    <td>{o.progress_percent}%</td>
                    <td>{o.expected_delivery || "—"}</td>
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

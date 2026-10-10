// Accounts & Finance Manager dashboard — the six required cards from live data
// (/api/accounts/dashboard), reusing the shared super UI kit.
import {
  Badge,
  Empty,
  ErrorBox,
  Loading,
  PageHead,
  Stat,
  go,
  when,
  useApi,
} from "../../../components/super/kit.jsx";
import "../../../owner.css";

const rupee = (v) =>
  `₹${Number(v || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

export default function AccountsDashboard() {
  const { data, error, loading, reload } = useApi("/api/accounts/dashboard", [
    "payments",
    "wages",
    "orders",
    "attendance",
  ]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const c = data.cards;

  return (
    <div className="module sm-page">
      <PageHead
        title="Accounts & finance dashboard"
        sub={`This month (${data.month.start} to ${data.month.end}) — sales, receivables, payables, expenses, wages and profit/loss.`}
      />

      <div className="sm-stats sm-stats-4">
        <Stat
          label="Total sales"
          value={rupee(c.total_sales)}
          hint="invoiced this month"
          onClick={() => go("/app/am-invoices")}
        />
        <Stat
          label="Pending buyer payments"
          value={rupee(c.pending_buyer_payments)}
          hint={`${c.pending_buyer_count} invoices`}
          tone={c.pending_buyer_payments ? "amber" : "green"}
          onClick={() => go("/app/am-buyer-payments")}
        />
        <Stat
          label="Supplier payments due"
          value={rupee(c.supplier_payments_due)}
          hint={`${c.supplier_due_count} suppliers`}
          tone={c.supplier_payments_due ? "amber" : "green"}
          onClick={() => go("/app/am-supplier-payments")}
        />
        <Stat
          label="Monthly expenses"
          value={rupee(c.monthly_expenses)}
          hint="supplier + wages + other"
          onClick={() => go("/app/am-reports")}
        />
      </div>
      <div className="sm-stats sm-stats-4">
        <Stat
          label="Worker wages"
          value={rupee(c.worker_wages)}
          hint={`${rupee(c.worker_wages_paid)} paid · ${rupee(c.worker_wages_due)} due`}
          tone={c.worker_wages_due ? "amber" : undefined}
          onClick={() => go("/app/am-wages")}
        />
        <Stat
          label="Monthly profit / loss"
          value={rupee(c.profit_or_loss)}
          hint={c.is_profit ? "profit (cash basis)" : "loss (cash basis)"}
          tone={c.is_profit ? "green" : "red"}
          onClick={() => go("/app/am-reports")}
        />
      </div>

      <div className="sm-grid-2">
        <section
          className={`panel ${data.receivables.some((r) => r.overdue) ? "sm-attention" : ""}`}
        >
          <h3>Buyers owe us</h3>
          {data.receivables.length === 0 ? (
            <Empty>No outstanding buyer payments.</Empty>
          ) : (
            <div className="owner-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Invoice</th>
                    <th>Buyer</th>
                    <th className="num">Balance</th>
                    <th>Age</th>
                  </tr>
                </thead>
                <tbody>
                  {data.receivables.map((r) => (
                    <tr
                      key={r.invoice_no}
                      className={r.overdue ? "row-warn" : ""}
                    >
                      <td>{r.invoice_no}</td>
                      <td>{r.buyer}</td>
                      <td className="num">{rupee(r.balance)}</td>
                      <td>
                        {r.days}d{" "}
                        {r.overdue && <Badge value="delayed" label="Overdue" />}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section
          className={`panel ${data.payables.some((r) => r.overdue) ? "sm-attention" : ""}`}
        >
          <h3>We owe suppliers</h3>
          {data.payables.length === 0 ? (
            <Empty>No supplier payments due.</Empty>
          ) : (
            <div className="owner-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Supplier</th>
                    <th className="num">Due</th>
                    <th>Age</th>
                  </tr>
                </thead>
                <tbody>
                  {data.payables.map((r) => (
                    <tr
                      key={r.supplier}
                      className={r.overdue ? "row-warn" : ""}
                    >
                      <td>{r.supplier}</td>
                      <td className="num">{rupee(r.due)}</td>
                      <td>
                        {r.days}d{" "}
                        {r.overdue && <Badge value="delayed" label="Overdue" />}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      <section className="panel">
        <h3>Month net (cash basis)</h3>
        <div className="sm-stats sm-stats-4">
          <Stat
            label="Buyer payments in"
            value={rupee(data.profit.buyer_payments_in)}
            tone="green"
          />
          <Stat
            label="Supplier payments out"
            value={rupee(data.profit.supplier_payments_out)}
          />
          <Stat label="Wages paid" value={rupee(data.profit.wages)} />
          <Stat
            label="Net"
            value={rupee(data.profit.profit_or_loss)}
            tone={data.profit.is_profit ? "green" : "red"}
          />
        </div>
      </section>

      <section className="panel">
        <h3>Recent activity</h3>
        {data.activity.length === 0 ? (
          <Empty>No activity recorded yet.</Empty>
        ) : (
          <ul className="sm-exceptions is-plain">
            {data.activity.map((a) => (
              <li key={a.id}>
                <strong>{a.action.replace(/_/g, " ")}</strong> — {a.details}
                <small className="sm-sub">
                  {a.user} · {when(a.at)}
                </small>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";

function isoDaysAgo(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

// Wages (accountant): calculate wages for a period (days × rate + overtime),
// pay wages. Wage cost allocation to orders is shown in Owner reports.
export default function Wages() {
  const [wages, setWages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [period, setPeriod] = useState({
    start: isoDaysAgo(6),
    end: isoDaysAgo(0),
  });

  async function load() {
    setLoading(true);
    setError("");
    try {
      setWages(await apiFetch("/api/wages"));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function calculate() {
    setMsg("");
    setBusy(true);
    try {
      const res = await apiFetch("/api/wages/calculate", {
        method: "POST",
        body: { period_start: period.start, period_end: period.end },
      });
      setMsg(
        `Calculated wages for ${res.wages.length} employees — total ₹${res.total.toLocaleString("en-IN")}.`,
      );
      await load();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function pay(id) {
    setMsg("");
    try {
      await apiFetch(`/api/wages/${id}/pay`, { method: "POST" });
      await load();
    } catch (err) {
      setMsg(err.message);
    }
  }

  const totalPending = wages
    .filter((w) => w.status === "pending")
    .reduce((s, w) => s + w.amount, 0);

  return (
    <div className="module">
      <h2>Wages</h2>
      {error && <div className="form-error">{error}</div>}
      {msg && <div className="callout callout-ok">{msg}</div>}

      <section className="panel">
        <h3>Calculate wages</h3>
        <div className="toolbar-controls">
          <label className="field">
            <span>From</span>
            <input
              type="date"
              value={period.start}
              onChange={(e) => setPeriod({ ...period, start: e.target.value })}
            />
          </label>
          <label className="field">
            <span>To</span>
            <input
              type="date"
              value={period.end}
              onChange={(e) => setPeriod({ ...period, end: e.target.value })}
            />
          </label>
          <button
            className="btn btn-primary"
            disabled={busy}
            onClick={calculate}
          >
            {busy ? "Calculating…" : "Calculate"}
          </button>
        </div>
        <p className="muted">
          amount = (present=1, half-day=0.5) × daily wage + overtime (hours over
          8 × ₹80/hr).
        </p>
      </section>

      <section className="panel">
        <div className="toolbar">
          <h3>Wage records</h3>
          <span className="muted">
            Pending total:{" "}
            <strong>₹{totalPending.toLocaleString("en-IN")}</strong>
          </span>
        </div>
        {loading ? (
          <p className="muted">Loading…</p>
        ) : wages.length === 0 ? (
          <p className="muted">
            No wage records yet. Calculate for a period above.
          </p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Employee</th>
                <th>Period</th>
                <th>Days</th>
                <th>Amount</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {wages.map((w) => (
                <tr key={w.id}>
                  <td>{w.employee}</td>
                  <td>
                    {w.period_start} → {w.period_end}
                  </td>
                  <td>{w.days_present}</td>
                  <td>₹{w.amount.toLocaleString("en-IN")}</td>
                  <td>
                    <span
                      className={`status status-${w.status === "paid" ? "pass" : "raised"}`}
                    >
                      {w.status}
                    </span>
                  </td>
                  <td>
                    {w.status === "pending" && (
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => pay(w.id)}
                      >
                        Pay
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

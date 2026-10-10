import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";

const DEFECTS = ["none", "hole", "colour_mismatch", "uneven_weaving", "other"];
const DEFECT_LABELS = {
  none: "None",
  hole: "Hole",
  colour_mismatch: "Colour mismatch",
  uneven_weaving: "Uneven weave",
  other: "Other",
};

// Quality module (quality inspector): new roll, inspect (pass/rework/reject),
// defect report, and Pending/Passed/Failed lists.
export default function Quality() {
  const [meta, setMeta] = useState({ orders: [], machines: [] });
  const [rolls, setRolls] = useState([]);
  const [report, setReport] = useState(null);
  const [tab, setTab] = useState("pending"); // pending|pass|failed|report
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [newRoll, setNewRoll] = useState({
    order_id: "",
    machine_id: "",
    length_meters: "",
  });
  const [rollErr, setRollErr] = useState({});
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const [inspect, setInspect] = useState(null); // {id, result, defect_type, notes}

  async function loadRolls() {
    setLoading(true);
    setError("");
    try {
      let data;
      if (tab === "failed") {
        const [rework, reject] = await Promise.all([
          apiFetch("/api/quality/rolls?status=rework"),
          apiFetch("/api/quality/rolls?status=reject"),
        ]);
        data = [...rework, ...reject];
      } else if (tab === "pass") {
        data = await apiFetch("/api/quality/rolls?status=pass");
      } else {
        data = await apiFetch("/api/quality/rolls?status=pending");
      }
      setRolls(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadReport() {
    setLoading(true);
    try {
      setReport(await apiFetch("/api/quality/defect-report"));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    apiFetch("/api/quality/_meta")
      .then(setMeta)
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (tab === "report") loadReport();
    else loadRolls();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  function validateRoll() {
    const e = {};
    if (!newRoll.order_id) e.order_id = "Select an order.";
    if (!newRoll.machine_id) e.machine_id = "Select a machine.";
    const l = Number(newRoll.length_meters);
    if (!newRoll.length_meters || isNaN(l) || l <= 0)
      e.length_meters = "Length must be greater than 0.";
    setRollErr(e);
    return Object.keys(e).length === 0;
  }

  async function createRoll(ev) {
    ev.preventDefault();
    setMsg("");
    if (!validateRoll()) return;
    setBusy(true);
    try {
      const r = await apiFetch("/api/quality/rolls", {
        method: "POST",
        body: {
          order_id: Number(newRoll.order_id),
          machine_id: Number(newRoll.machine_id),
          length_meters: Number(newRoll.length_meters),
        },
      });
      setMsg(`Created roll ${r.roll_no} (Pending).`);
      setNewRoll({ order_id: "", machine_id: "", length_meters: "" });
      if (tab === "pending") loadRolls();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function submitInspect() {
    setMsg("");
    if (inspect.result !== "pass" && inspect.defect_type === "none") {
      setMsg("A reworked or rejected roll needs a defect type.");
      return;
    }
    setBusy(true);
    try {
      await apiFetch(`/api/quality/rolls/${inspect.id}/inspect`, {
        method: "POST",
        body: {
          result: inspect.result,
          defect_type: inspect.result === "pass" ? "none" : inspect.defect_type,
          notes: inspect.notes || null,
        },
      });
      setInspect(null);
      loadRolls();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="module">
      <h2>Quality</h2>
      {msg && <div className="callout callout-ok">{msg}</div>}
      {error && <div className="form-error">{error}</div>}

      <section className="panel">
        <h3>New roll</h3>
        <form className="form-grid" onSubmit={createRoll} noValidate>
          <label className="field">
            <span>Order</span>
            <select
              value={newRoll.order_id}
              onChange={(e) =>
                setNewRoll({ ...newRoll, order_id: e.target.value })
              }
              className={rollErr.order_id ? "invalid" : ""}
            >
              <option value="">Select order…</option>
              {meta.orders.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.order_no} — {o.fabric_type}
                </option>
              ))}
            </select>
            {rollErr.order_id && (
              <small className="field-error">{rollErr.order_id}</small>
            )}
          </label>
          <label className="field">
            <span>Machine</span>
            <select
              value={newRoll.machine_id}
              onChange={(e) =>
                setNewRoll({ ...newRoll, machine_id: e.target.value })
              }
              className={rollErr.machine_id ? "invalid" : ""}
            >
              <option value="">Select machine…</option>
              {meta.machines.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
            {rollErr.machine_id && (
              <small className="field-error">{rollErr.machine_id}</small>
            )}
          </label>
          <label className="field">
            <span>Length (metres)</span>
            <input
              type="number"
              min="0"
              step="any"
              value={newRoll.length_meters}
              onChange={(e) =>
                setNewRoll({ ...newRoll, length_meters: e.target.value })
              }
              className={rollErr.length_meters ? "invalid" : ""}
            />
            {rollErr.length_meters && (
              <small className="field-error">{rollErr.length_meters}</small>
            )}
          </label>
          <div className="form-actions">
            <button className="btn btn-primary" disabled={busy}>
              Create roll
            </button>
          </div>
        </form>
      </section>

      <section className="panel">
        <div className="tabs">
          {[
            ["pending", "Pending"],
            ["pass", "Passed"],
            ["failed", "Failed"],
            ["report", "Defect report"],
          ].map(([k, label]) => (
            <button
              key={k}
              className={`tab ${tab === k ? "active" : ""}`}
              onClick={() => setTab(k)}
            >
              {label}
            </button>
          ))}
        </div>

        {loading ? (
          <p className="muted">Loading…</p>
        ) : tab === "report" ? (
          report && (
            <div className="report-grid">
              <div>
                <h4>By defect</h4>
                <ReportTable
                  rows={report.by_defect.map((r) => [
                    DEFECT_LABELS[r.defect_type] || r.defect_type,
                    r.count,
                  ])}
                />
              </div>
              <div>
                <h4>By machine</h4>
                <ReportTable
                  rows={report.by_machine.map((r) => [r.machine, r.count])}
                />
              </div>
              <div>
                <h4>By order</h4>
                <ReportTable
                  rows={report.by_order.map((r) => [r.order_no, r.count])}
                />
              </div>
              <div>
                <h4>Roll status</h4>
                <ReportTable rows={Object.entries(report.roll_status_counts)} />
              </div>
            </div>
          )
        ) : rolls.length === 0 ? (
          <p className="muted">No rolls in this list.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Roll</th>
                <th>Order</th>
                <th>Machine</th>
                <th>Length (m)</th>
                <th>Status</th>
                <th>Defect</th>
                {tab === "pending" && <th>Inspect</th>}
              </tr>
            </thead>
            <tbody>
              {rolls.map((r) => (
                <tr key={r.id}>
                  <td>{r.roll_no}</td>
                  <td>{r.order_no}</td>
                  <td>{r.machine_name}</td>
                  <td>{r.length_meters}</td>
                  <td>
                    <span className={`status status-${r.status}`}>
                      {r.status}
                    </span>
                  </td>
                  <td>{r.defect_type ? DEFECT_LABELS[r.defect_type] : "—"}</td>
                  {tab === "pending" && (
                    <td>
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() =>
                          setInspect({
                            id: r.id,
                            roll_no: r.roll_no,
                            result: "pass",
                            defect_type: "none",
                            notes: "",
                          })
                        }
                      >
                        Inspect
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* Inspect modal */}
      {inspect && (
        <div className="modal-overlay" onClick={() => setInspect(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Inspect roll {inspect.roll_no}</h3>
            <label className="field">
              <span>Result</span>
              <select
                value={inspect.result}
                onChange={(e) =>
                  setInspect({ ...inspect, result: e.target.value })
                }
              >
                <option value="pass">Pass</option>
                <option value="rework">Rework</option>
                <option value="reject">Reject</option>
              </select>
            </label>
            {inspect.result !== "pass" && (
              <label className="field">
                <span>Defect type</span>
                <select
                  value={inspect.defect_type}
                  onChange={(e) =>
                    setInspect({ ...inspect, defect_type: e.target.value })
                  }
                >
                  {DEFECTS.filter((d) => d !== "none").map((d) => (
                    <option key={d} value={d}>
                      {DEFECT_LABELS[d]}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label className="field">
              <span>Notes</span>
              <input
                value={inspect.notes}
                onChange={(e) =>
                  setInspect({ ...inspect, notes: e.target.value })
                }
                placeholder="Optional"
              />
            </label>
            <div className="inline-actions">
              <button
                className="btn btn-primary btn-sm"
                disabled={busy}
                onClick={submitInspect}
              >
                Save inspection
              </button>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setInspect(null)}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ReportTable({ rows }) {
  if (!rows || rows.length === 0) return <p className="muted">—</p>;
  return (
    <table className="data-table">
      <tbody>
        {rows.map(([k, v]) => (
          <tr key={k}>
            <td>{k}</td>
            <td>
              <strong>{v}</strong>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

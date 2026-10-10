import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";
import { isLiveRefresh, useLive } from "../../live/LiveContext.jsx";
import { inr, qty, ddmmyyyy, statusLabel } from "../../lib/format.js";
import "../../owner.css";

// Owner Orders — READ ONLY. The owner views orders and tracks them; orders are
// created, confirmed and cancelled by the Store manager (not here). No New-order
// form, no Check yarn, no Confirm/Edit/Cancel on this screen.

const STATUSES = [
  "draft",
  "confirmed",
  "in_production",
  "in_quality",
  "ready_to_ship",
  "dispatched",
  "closed",
  "cancelled",
];

const STATUS_CHIP = {
  draft: "owner-chip-grey",
  confirmed: "owner-chip-blue",
  in_production: "owner-chip-blue",
  in_quality: "owner-chip-amber",
  ready_to_ship: "owner-chip-blue",
  dispatched: "owner-chip-green",
  closed: "owner-chip-green",
  cancelled: "owner-chip-red",
};

const RESULT_CHIP = {
  pass: "owner-chip-green",
  rework: "owner-chip-amber",
  reject: "owner-chip-red",
  pending: "owner-chip-grey",
};

export default function Orders() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const initialStatus =
    typeof window !== "undefined" && window.__ownerOrdersFilter
      ? window.__ownerOrdersFilter
      : "";
  if (typeof window !== "undefined") window.__ownerOrdersFilter = undefined;

  const [statusFilter, setStatusFilter] = useState(initialStatus);
  const [search, setSearch] = useState("");
  const [track, setTrack] = useState(null);
  const [trackLoading, setTrackLoading] = useState(false);

  async function loadOrders() {
    if (!isLiveRefresh()) setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.set("status", statusFilter);
      if (search.trim()) params.set("q", search.trim());
      const qs = params.toString();
      setOrders(await apiFetch(`/api/orders${qs ? `?${qs}` : ""}`));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadOrders();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  useLive(["orders"], loadOrders);

  async function openTracker(order) {
    setTrack({ loading: true });
    setTrackLoading(true);
    try {
      const data = await apiFetch(`/api/orders/${order.id}/track`);
      setTrack(data);
    } catch (err) {
      setTrack({ error: err.message });
    } finally {
      setTrackLoading(false);
    }
  }

  return (
    <div className="module owner-page">
      <h2>Orders</h2>
      <p className="muted">
        Read-only view. Orders are created and confirmed by the Store manager.
      </p>

      <section className="panel">
        <div className="toolbar">
          <h3>Orders list</h3>
          <div className="toolbar-controls">
            <input
              placeholder="Search order / fabric / colour…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && loadOrders()}
            />
            <button className="btn btn-ghost btn-sm" onClick={loadOrders}>
              Search
            </button>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All statuses</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {statusLabel(s)}
                </option>
              ))}
            </select>
          </div>
        </div>

        {error && <div className="form-error">{error}</div>}
        {loading ? (
          <p className="muted">Loading orders…</p>
        ) : orders.length === 0 ? (
          <p className="muted">No orders found.</p>
        ) : (
          <table className="data-table owner-sticky">
            <thead>
              <tr>
                <th>Order</th>
                <th>Buyer</th>
                <th>Fabric</th>
                <th>Colour</th>
                <th className="num">Qty</th>
                <th className="num">Rate</th>
                <th>Deadline</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td>{o.order_no}</td>
                  <td>{o.buyer_name}</td>
                  <td>{o.fabric_type}</td>
                  <td>{o.colour}</td>
                  <td className="num">{qty(o.quantity_meters, "m")}</td>
                  <td className="num owner-num">{inr(o.unit_price)}</td>
                  <td>{ddmmyyyy(o.deadline)}</td>
                  <td>
                    <span
                      className={`owner-chip ${STATUS_CHIP[o.status] || "owner-chip-grey"}`}
                    >
                      {statusLabel(o.status)}
                    </span>
                  </td>
                  <td className="row-actions">
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => openTracker(o)}
                    >
                      Track
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {track && (
        <TrackerDrawer
          track={track}
          loading={trackLoading}
          onClose={() => setTrack(null)}
        />
      )}
    </div>
  );
}

function TrackerDrawer({ track, loading, onClose }) {
  return (
    <div className="owner-drawer-backdrop" onClick={onClose}>
      <div className="owner-drawer" onClick={(e) => e.stopPropagation()}>
        <button
          className="link-btn"
          onClick={onClose}
          style={{ float: "right" }}
        >
          close
        </button>
        {loading || track.loading ? (
          <p className="muted">Loading tracker…</p>
        ) : track.error ? (
          <div className="form-error">{track.error}</div>
        ) : (
          <>
            <h3>
              {track.order_no} — {track.fabric_type} ({track.colour})
            </h3>
            <p className="muted">
              {track.buyer_name} · {qty(track.quantity_meters, "m")} ordered
            </p>

            <div className="stepper">
              {track.stage_flow.map((s, i) => (
                <div
                  key={s}
                  className={`step-dot ${i <= track.stage_index ? "done" : ""}`}
                >
                  <span
                    className="step-circle"
                    style={{
                      background:
                        i <= track.stage_index ? "var(--brand)" : "#e5e7eb",
                      color: i <= track.stage_index ? "#fff" : "#64748b",
                    }}
                  >
                    {i + 1}
                  </span>
                  <small>{statusLabel(s)}</small>
                </div>
              ))}
            </div>

            <div style={{ margin: "1rem 0" }}>
              <div className="pl-row">
                <span>Progress</span>
                <strong className="owner-num">{track.progress_percent}%</strong>
              </div>
              <div className="pl-row">
                <span>Deadline</span>
                <strong>{ddmmyyyy(track.deadline)}</strong>
              </div>
              <div className="pl-row">
                <span>Status</span>
                <span
                  className={
                    track.late ? "owner-flag-late" : "owner-flag-ontrack"
                  }
                >
                  {track.late ? "Late" : "On track"}
                </span>
              </div>
            </div>

            <h4>Rolls ({track.rolls.length})</h4>
            {track.rolls.length === 0 ? (
              <p className="muted">No rolls made yet.</p>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Roll</th>
                    <th className="num">Length</th>
                    <th>Machine</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {track.rolls.map((r) => (
                    <tr key={r.roll_no}>
                      <td>{r.roll_no}</td>
                      <td className="num">{qty(r.length_meters, "m")}</td>
                      <td>{r.machine}</td>
                      <td>
                        <span
                          className={`owner-chip ${RESULT_CHIP[r.result] || "owner-chip-grey"}`}
                          title={
                            r.defect_type && r.defect_type !== "none"
                              ? `Defect: ${r.defect_type}`
                              : undefined
                          }
                        >
                          {statusLabel(r.result)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </div>
    </div>
  );
}

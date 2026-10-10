// Supermanager: attendance, accounts & reports, alerts, activity log, settings.
import { useEffect, useState } from "react";
import { apiFetch } from "../../../lib/api.js";
import { inr, currentMonthValue, monthRange } from "../../../lib/format.js";
import { Badge, Dialog, Empty, ErrorBox, Field, Loading, Notice, PageHead, Stat, day, go, when, useApi } from "../../../components/super/kit.jsx";
import "../../../owner.css";

const today = () => new Date().toISOString().slice(0, 10);

// --------------------------------------------------------------------------- //
export function SuperAttendance() {
  const [d, setD] = useState(today());
  const { data, error, loading, reload } = useApi(`/api/super/attendance?day=${d}`, ["wages"]);
  const [fix, setFix] = useState(null);
  const [msg, setMsg] = useState(null);
  const [dept, setDept] = useState("");

  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const t = data.totals;
  const rows = data.rows.filter((r) => !dept || (r.department || "none") === dept);
  return (
    <div className="module sm-page">
      <PageHead title="Attendance monitoring" sub="Who is in, across every department.">
        <label className="owner-month">
          <span>Day</span>
          <input type="date" value={d} max={today()} onChange={(e) => e.target.value && setD(e.target.value)} />
        </label>
      </PageHead>
      <Notice kind={msg?.kind} onClose={() => setMsg(null)}>
        {msg?.text}
      </Notice>
      <div className="sm-stats sm-stats-4">
        <Stat label="Present" value={t.present} tone="green" />
        <Stat label="Half day" value={t.half_day} tone={t.half_day ? "amber" : undefined} />
        <Stat label="Absent" value={t.absent} tone={t.absent ? "red" : undefined} />
        <Stat label="Not marked" value={t.not_marked} hint={data.last_marked_day ? `Last marked: ${day(data.last_marked_day)}` : undefined} />
      </div>

      <section className="panel">
        <h3>By department</h3>
        <div className="owner-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Department</th>
                <th className="num">Present</th>
                <th className="num">Half day</th>
                <th className="num">Absent</th>
                <th className="num">Not marked</th>
              </tr>
            </thead>
            <tbody>
              {data.by_department.map((r) => (
                <tr key={r.department}>
                  <td>{r.label}</td>
                  <td className="num">{r.present}</td>
                  <td className="num">{r.half_day}</td>
                  <td className="num">{r.absent}</td>
                  <td className="num">{r.not_marked}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="sm-toolbar">
          <h3>Workers on {day(data.day)}</h3>
          <select className="sm-select" value={dept} onChange={(e) => setDept(e.target.value)} aria-label="Department">
            <option value="">All departments</option>
            {data.by_department.map((r) => (
              <option key={r.department} value={r.department}>
                {r.label}
              </option>
            ))}
          </select>
        </div>
        {rows.length === 0 ? (
          <Empty>No active workers.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Worker</th>
                  <th>Department</th>
                  <th>Status</th>
                  <th>Shift</th>
                  <th className="num">Hours</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.employee_id} className={r.status === "absent" ? "row-warn" : ""}>
                    <td>{r.name}</td>
                    <td>{r.department_label}</td>
                    <td>
                      <Badge value={r.status} />
                    </td>
                    <td>{r.shift || "—"}</td>
                    <td className="num">{r.hours ?? "—"}</td>
                    <td>
                      <button className="btn btn-ghost btn-sm" onClick={() => setFix(r)}>
                        Record exception
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="muted sm-small">{data.not_tracked}</p>
      </section>

      <section className="panel">
        <h3>Recorded exceptions and corrections</h3>
        {data.corrections.length === 0 ? (
          <Empty>No attendance corrections recorded.</Empty>
        ) : (
          <ul className="sm-exceptions is-plain">
            {data.corrections.map((c) => (
              <li key={c.id}>
                {c.details} <small className="muted">— {c.user}, {when(c.at)}</small>
              </li>
            ))}
          </ul>
        )}
      </section>

      {fix && (
        <AttendanceFix
          row={fix}
          dayIso={data.day}
          onClose={() => setFix(null)}
          onSaved={(text) => {
            setFix(null);
            setMsg({ kind: "ok", text });
            reload();
          }}
        />
      )}
    </div>
  );
}

function AttendanceFix({ row, dayIso, onClose, onSaved }) {
  const [status, setStatus] = useState(row.status === "not_marked" ? "present" : row.status);
  const [reason, setReason] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    if (reason.trim().length < 3) return setErr("Give the reason for this exception.");
    setBusy(true);
    setErr("");
    try {
      await apiFetch("/api/super/attendance/exception", {
        method: "POST",
        body: { employee_id: row.employee_id, work_date: dayIso, status, reason: reason.trim() },
      });
      onSaved(`Attendance for ${row.name} recorded as ${status.replace("_", " ")}.`);
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title={`Attendance exception — ${row.name}`} onClose={onClose}>
      <p className="muted">
        {day(dayIso)} · now: {row.status.replace("_", " ")}. The change and your reason go into the activity log.
      </p>
      <ErrorBox error={err} />
      <form className="form-grid sm-form" onSubmit={submit} noValidate>
        <Field label="Record as">
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="present">Present</option>
            <option value="half_day">Half day</option>
            <option value="absent">Absent</option>
          </select>
        </Field>
        <Field label="Reason (required)" wide>
          <textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Was on outdoor duty, register missed" />
        </Field>
        <div className="sm-row-end sm-wide">
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary btn-sm" disabled={busy}>
            {busy ? "Saving…" : "Record"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

// --------------------------------------------------------------------------- //
export function SuperAccounts() {
  const [range, setRange] = useState(() => monthRange(currentMonthValue()));
  const { data, error, loading, reload } = useApi(`/api/super/accounts?start=${range.start}&end=${range.end}`, ["payments", "wages", "orders", "production"]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const p = data.profit;
  const s = data.sales;
  return (
    <div className="module sm-page">
      <PageHead title="Accounts & reports" sub={data.note}>
        <div className="sm-range">
          <label className="owner-month">
            <span>From</span>
            <input type="date" value={range.start} onChange={(e) => e.target.value && setRange({ ...range, start: e.target.value })} />
          </label>
          <label className="owner-month">
            <span>To</span>
            <input type="date" value={range.end} onChange={(e) => e.target.value && setRange({ ...range, end: e.target.value })} />
          </label>
        </div>
      </PageHead>
      <ErrorBox error={error} />

      <div className="sm-stats">
        <Stat label="Invoiced" value={inr(s.invoiced)} hint={`${s.invoices} invoices`} />
        <Stat label="Buyer payments received" value={inr(data.buyer_payments)} tone="green" />
        <Stat label="Still to receive (these invoices)" value={inr(s.outstanding)} tone={s.outstanding ? "amber" : undefined} />
        <Stat label="Supplier bills raised" value={inr(data.supplier_bills.raised)} hint={`${data.supplier_bills.count} bills · ${inr(data.supplier_bills.paid)} paid`} />
        <Stat label="Worker wages" value={inr(data.wages.total)} hint={`${inr(data.wages.paid)} paid · ${inr(data.wages.due)} due`} />
        <Stat label="Production cost" value={inr(data.production_cost.total)} hint={`${data.production_cost.orders} orders${data.production_cost.has_estimates ? " · includes yarn estimates" : ""}`} />
        <Stat
          label="Net cash (in − bills − wages paid)"
          value={inr(p.profit_or_loss)}
          tone={p.profit_or_loss >= 0 ? "green" : "red"}
          hint="Cash basis, from recorded payments only"
        />
      </div>

      <section className="panel">
        <h3>Department-wise report</h3>
        <div className="owner-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Department</th>
                <th>Figures for the period</th>
                <th className="num">Tasks open</th>
                <th className="num">Overdue</th>
                <th className="num">Done</th>
              </tr>
            </thead>
            <tbody>
              {data.departments.map((d) => (
                <tr key={d.department}>
                  <td>
                    <strong>{d.label}</strong>
                    <small className="sm-sub">{d.managers.join(", ") || "No manager"}</small>
                  </td>
                  <td>{d.metrics.map((m) => `${m.label}: ${m.value}`).join(" · ")}</td>
                  <td className="num">{d.tasks_open}</td>
                  <td className="num">{d.tasks_overdue}</td>
                  <td className="num">{d.tasks_done}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <h3>Date-wise report</h3>
        {data.daily.length === 0 ? (
          <Empty>No production or payments in this period.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th className="num">Metres produced</th>
                  <th className="num">Money in</th>
                  <th className="num">Money out</th>
                </tr>
              </thead>
              <tbody>
                {data.daily.map((r) => (
                  <tr key={r.day}>
                    <td>{day(r.day)}</td>
                    <td className="num">{Number(r.meters).toLocaleString("en-IN")}</td>
                    <td className="num">{r.money_in ? inr(r.money_in) : "—"}</td>
                    <td className="num">{r.money_out ? inr(r.money_out) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel">
        <h3>Invoices in the period</h3>
        {s.rows.length === 0 ? (
          <Empty>No invoices raised in this period.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Buyer</th>
                  <th>Date</th>
                  <th className="num">Total</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {s.rows.map((i) => (
                  <tr key={i.invoice_no}>
                    <td>{i.invoice_no}</td>
                    <td>{i.buyer}</td>
                    <td>{day(i.date)}</td>
                    <td className="num">{inr(i.total)}</td>
                    <td>
                      <Badge value={i.status} />
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

// --------------------------------------------------------------------------- //
export function SuperAlerts() {
  const { data, error, loading, reload } = useApi("/api/super/alerts", ["orders", "machines", "production", "quality", "yarn", "wages", "tasks"]);
  const [kind, setKind] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  const list = data.alerts.filter((a) => !kind || a.kind === kind);
  return (
    <div className="module sm-page">
      <PageHead title="Notifications & alerts" sub="Worked out from live data. Turn categories on or off in Settings." />
      <div className="sm-chips">
        <button className={!kind ? "is-active" : ""} onClick={() => setKind("")}>
          All <b>{data.alerts.length}</b>
        </button>
        {data.kinds.map((k) => (
          <button key={k.key} className={kind === k.key ? "is-active" : ""} onClick={() => setKind(k.key)} disabled={!k.count}>
            {k.label} <b>{k.count}</b>
          </button>
        ))}
      </div>
      <section className="panel">
        {list.length === 0 ? (
          <Empty>No alerts here — all clear.</Empty>
        ) : (
          <ul className="sm-alerts">
            {list.map((a, i) => (
              <li key={i} className={`sm-alert is-${a.severity}`}>
                <button type="button" onClick={() => go(a.page)}>
                  <Badge value={a.severity} />
                  <span>
                    <strong>{a.title}</strong>
                    <small className="muted">{a.detail}</small>
                  </span>
                  <span className="sm-go" aria-hidden>
                    ›
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

// --------------------------------------------------------------------------- //
const CATEGORY_LABEL = {
  order: "Orders", stock: "Stock", qc: "Quality", dispatch: "Dispatch", attendance: "Attendance",
  team: "Managers", worker: "Workers", task: "Instructions", payment: "Payments", settings: "Settings",
};

export function SuperActivity() {
  const [f, setF] = useState({ category: "", q: "" });
  const [page, setPage] = useState(0);
  const size = 30;
  const qs = new URLSearchParams({ ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)), limit: size, offset: page * size }).toString();
  const { data, error, loading, reload } = useApi(`/api/super/activity?${qs}`, ["orders", "yarn", "quality", "wages", "tasks", "payments"]);
  useEffect(() => setPage(0), [f.category, f.q]);
  const pages = data ? Math.max(1, Math.ceil(data.total / size)) : 1;
  return (
    <div className="module sm-page">
      <PageHead title="Activity log" sub="An auditable record of important actions — written automatically, it cannot be edited." />
      <ErrorBox error={error} onRetry={reload} />
      <section className="panel">
        <div className="sm-toolbar">
          <input className="sm-search" type="search" placeholder="Search details or person…" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} aria-label="Search activity" />
          <select className="sm-select" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} aria-label="Category">
            <option value="">All categories</option>
            {(data?.categories || []).map((c) => (
              <option key={c} value={c}>
                {CATEGORY_LABEL[c] || c}
              </option>
            ))}
          </select>
        </div>
        {loading && !data ? (
          <Loading />
        ) : data.rows.length === 0 ? (
          <Empty>Nothing recorded yet.</Empty>
        ) : (
          <>
            <div className="owner-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Who</th>
                    <th>Area</th>
                    <th>What happened</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((a) => (
                    <tr key={a.id}>
                      <td className="sm-nowrap">{when(a.at)}</td>
                      <td>
                        {a.user}
                        {a.role && <small className="sm-sub">{a.role.replace(/_/g, " ")}</small>}
                      </td>
                      <td>
                        <span className={`sm-cat cat-${a.category}`}>{CATEGORY_LABEL[a.category] || a.category}</span>
                      </td>
                      <td>{a.details}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <nav className="owner-pager" aria-label="Pages">
              <span className="muted">
                {data.total} entries · page {page + 1} of {pages}
              </span>
              <div className="owner-pager-btns">
                <button type="button" disabled={page === 0} onClick={() => setPage(page - 1)}>
                  ‹ Newer
                </button>
                <button type="button" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>
                  Older ›
                </button>
              </div>
            </nav>
          </>
        )}
      </section>
    </div>
  );
}

// --------------------------------------------------------------------------- //
export function SuperSettings() {
  const { data, error, loading, reload, setData } = useApi("/api/super/settings");
  const [cap, setCap] = useState("");
  const [alerts, setAlerts] = useState({});
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (data) {
      setCap(String(data.capacity_m_per_machine_day));
      setAlerts(data.alerts);
    }
  }, [data]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;

  async function save() {
    if (!(Number(cap) > 0)) return setMsg({ kind: "err", text: "Capacity must be more than 0." });
    setBusy(true);
    try {
      const d = await apiFetch("/api/super/settings", { method: "PUT", body: { capacity_m_per_machine_day: Number(cap), alerts } });
      setData(d);
      setMsg({ kind: "ok", text: "Settings saved." });
    } catch (e) {
      setMsg({ kind: "err", text: e.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="module sm-page">
      <PageHead title="Settings" sub="Department set-up, capacity, alert preferences and who can open what.">
        <button className="btn btn-primary" onClick={save} disabled={busy}>
          {busy ? "Saving…" : "Save settings"}
        </button>
      </PageHead>
      <Notice kind={msg?.kind} onClose={() => setMsg(null)}>
        {msg?.text}
      </Notice>

      <div className="sm-grid-2">
        <section className="panel">
          <h3>Production capacity</h3>
          <p className="muted sm-small">Used by the order review to check whether an order can be made by its deadline.</p>
          <Field label="Metres one weaving machine makes per day">
            <input type="number" min="1" value={cap} onChange={(e) => setCap(e.target.value)} />
          </Field>
        </section>
        <section className="panel">
          <h3>Alert preferences</h3>
          <ul className="sm-toggles">
            {data.alert_kinds.map((k) => (
              <li key={k.key}>
                <label>
                  <input type="checkbox" checked={!!alerts[k.key]} onChange={(e) => setAlerts({ ...alerts, [k.key]: e.target.checked })} />
                  {k.label}
                </label>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <section className="panel">
        <h3>Departments</h3>
        <div className="owner-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Department</th>
                <th>Login role (screens)</th>
                <th>Active managers</th>
              </tr>
            </thead>
            <tbody>
              {data.departments.map((d) => (
                <tr key={d.key}>
                  <td>{d.label}</td>
                  <td>{d.role.replace(/_/g, " ")}</td>
                  <td>{d.managers.join(", ") || <span className="muted">None — add one in Department managers</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <h3>Role permissions</h3>
        <p className="muted sm-small">
          Enforced by the server on every request. Changing who can open what is a code change, so it is shown here read-only.
        </p>
        <div className="owner-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Role</th>
                <th>Pages</th>
              </tr>
            </thead>
            <tbody>
              {data.permissions.map((p) => (
                <tr key={p.role}>
                  <td className="sm-nowrap">{p.role === "manager" ? "supermanager" : p.role.replace(/_/g, " ")}</td>
                  <td>{p.pages.join(" · ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

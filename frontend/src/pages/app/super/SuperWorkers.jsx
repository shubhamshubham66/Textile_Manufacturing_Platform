import { useState } from "react";
import { apiFetch } from "../../../lib/api.js";
import { inr } from "../../../lib/format.js";
import { Badge, Dialog, Empty, ErrorBox, Field, Loading, Notice, PageHead, useApi } from "../../../components/super/kit.jsx";
import "../../../owner.css";

// Workers: add, assign department + reporting manager, edit, activate or
// deactivate, attendance this month and the tasks handed to them.
export default function SuperWorkers() {
  const [filters, setFilters] = useState({ q: "", department: "", status: "" });
  const qs = new URLSearchParams(Object.entries(filters).filter(([, v]) => v)).toString();
  const { data, error, loading, reload } = useApi(`/api/super/workers${qs ? `?${qs}` : ""}`, ["wages", "tasks"]);
  const [form, setForm] = useState(null);
  const [loginFor, setLoginFor] = useState(null);
  const [msg, setMsg] = useState(null);
  const setF = (k) => (e) => setFilters({ ...filters, [k]: e.target.value });

  async function toggle(w) {
    if (!window.confirm(`${w.is_active ? "Deactivate" : "Activate"} ${w.name}?`)) return;
    try {
      await apiFetch(`/api/super/workers/${w.id}/active`, { method: "POST", body: { active: !w.is_active } });
      setMsg({ kind: "ok", text: `${w.name} ${w.is_active ? "deactivated" : "activated"}.` });
      reload();
    } catch (e) {
      setMsg({ kind: "err", text: e.message });
    }
  }

  const workers = data?.workers || [];
  return (
    <div className="module sm-page">
      <PageHead title="Workers" sub="Everyone on the floor, their department and who they report to.">
        <button className="btn btn-primary" onClick={() => setForm({ mode: "new" })}>
          ＋ Add worker
        </button>
      </PageHead>
      <Notice kind={msg?.kind} onClose={() => setMsg(null)}>
        {msg?.text}
      </Notice>
      <ErrorBox error={error} onRetry={reload} />

      <section className="panel">
        <div className="sm-toolbar">
          <input className="sm-search" type="search" placeholder="Search name or work…" value={filters.q} onChange={setF("q")} aria-label="Search workers" />
          <div className="sm-filters">
            <select className="sm-select" value={filters.department} onChange={setF("department")} aria-label="Department">
              <option value="">All departments</option>
              {(data?.departments || []).map((d) => (
                <option key={d.key} value={d.key}>
                  {d.label}
                </option>
              ))}
              <option value="none">Not assigned</option>
            </select>
            <select className="sm-select" value={filters.status} onChange={setF("status")} aria-label="Status">
              <option value="">Active and inactive</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>
        </div>

        {loading && !data ? (
          <Loading />
        ) : workers.length === 0 ? (
          <Empty>No workers match these filters.</Empty>
        ) : (
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Worker</th>
                  <th>Department</th>
                  <th>Reports to</th>
                  <th className="num">Daily wage</th>
                  <th>Attendance this month</th>
                  <th>Tasks</th>
                  <th>Login</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {workers.map((w) => (
                  <tr key={w.id} className={w.is_active ? "" : "sm-row-off"}>
                    <td>
                      <strong>{w.name}</strong>
                      <small className="sm-sub">{w.role_on_floor || "—"}{w.phone ? ` · ${w.phone}` : ""}</small>
                    </td>
                    <td>{w.department_label || <span className="muted">Not assigned</span>}</td>
                    <td>{w.manager?.name || <span className="muted">—</span>}</td>
                    <td className="num">{inr(w.daily_wage)}</td>
                    <td>
                      <span className="sm-att">
                        <b className="ok">{w.attendance.present}</b> present · <b className="warn">{w.attendance.half_day}</b> half ·{" "}
                        <b className="bad">{w.attendance.absent}</b> absent
                      </span>
                    </td>
                    <td>
                      {w.tasks.length === 0 ? (
                        <span className="muted">—</span>
                      ) : (
                        <ul className="sm-taskmini">
                          {w.tasks.map((t) => (
                            <li key={t.id}>
                              {t.title} <Badge value={t.status} />
                            </li>
                          ))}
                        </ul>
                      )}
                    </td>
                    <td>
                      {w.has_login ? (
                        <small>{w.login_email}</small>
                      ) : (
                        <span className="muted">No login</span>
                      )}
                    </td>
                    <td>
                      <Badge value={w.is_active ? "active" : "inactive"} label={w.is_active ? "Active" : "Inactive"} />
                    </td>
                    <td>
                      <div className="sm-actions">
                        <button className="btn btn-ghost btn-sm" onClick={() => setForm({ mode: "edit", w })}>
                          Edit
                        </button>
                        <button className="btn btn-ghost btn-sm" onClick={() => setLoginFor(w)}>
                          {w.has_login ? "Reset login" : "Give login"}
                        </button>
                        <button className="link-btn" onClick={() => toggle(w)}>
                          {w.is_active ? "Deactivate" : "Activate"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="muted sm-small">
          Give a worker a login (email + password) so they can see their own tasks, post production updates and check
          attendance. Without a login, their department manager records their work for them.
        </p>
      </section>

      {loginFor && (
        <LoginDialog
          w={loginFor}
          onClose={() => setLoginFor(null)}
          onSaved={(text) => {
            setLoginFor(null);
            setMsg({ kind: "ok", text });
            reload();
          }}
        />
      )}

      {form && (
        <WorkerForm
          mode={form.mode}
          w={form.w}
          departments={data?.departments || []}
          managers={data?.managers || []}
          onClose={() => setForm(null)}
          onSaved={(text) => {
            setForm(null);
            setMsg({ kind: "ok", text });
            reload();
          }}
        />
      )}
    </div>
  );
}

function WorkerForm({ mode, w, departments, managers, onClose, onSaved }) {
  const [f, setF] = useState({
    name: w?.name || "",
    role_on_floor: w?.role_on_floor || "",
    phone: w?.phone || "",
    daily_wage: w?.daily_wage ?? "",
    department: w?.department || "",
    manager_user_id: w?.manager?.id || "",
  });
  const [errs, setErrs] = useState({});
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const mgrOptions = managers.filter((m) => !f.department || m.department === f.department);

  async function submit(e) {
    e.preventDefault();
    const x = {};
    if (f.name.trim().length < 2) x.name = "Enter the worker's name.";
    if (f.daily_wage === "" || Number(f.daily_wage) < 0) x.daily_wage = "Enter the daily wage.";
    if (f.phone && !/^[0-9+\-\s]{6,20}$/.test(f.phone)) x.phone = "Use digits only.";
    setErrs(x);
    if (Object.keys(x).length) return;
    setBusy(true);
    setErr("");
    const body = {
      name: f.name.trim(),
      role_on_floor: f.role_on_floor.trim() || null,
      phone: f.phone.trim() || null,
      daily_wage: Number(f.daily_wage),
      department: f.department || null,
      manager_user_id: f.manager_user_id ? Number(f.manager_user_id) : null,
    };
    try {
      if (mode === "new") await apiFetch("/api/super/workers", { method: "POST", body });
      else await apiFetch(`/api/super/workers/${w.id}`, { method: "PUT", body });
      onSaved(mode === "new" ? `${body.name} added.` : `${body.name} updated.`);
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog title={mode === "new" ? "Add worker" : `Edit ${w.name}`} onClose={onClose}>
      <ErrorBox error={err} />
      <form className="form-grid sm-form" onSubmit={submit} noValidate>
        <Field label="Full name" error={errs.name}>
          <input value={f.name} onChange={set("name")} />
        </Field>
        <Field label="Work on the floor">
          <input value={f.role_on_floor} onChange={set("role_on_floor")} placeholder="Loom operator" />
        </Field>
        <Field label="Phone" error={errs.phone}>
          <input value={f.phone} onChange={set("phone")} inputMode="tel" />
        </Field>
        <Field label="Daily wage (₹)" error={errs.daily_wage}>
          <input type="number" min="0" value={f.daily_wage} onChange={set("daily_wage")} />
        </Field>
        <Field label="Department">
          <select value={f.department} onChange={(e) => setF({ ...f, department: e.target.value, manager_user_id: "" })}>
            <option value="">Not assigned</option>
            {departments.map((d) => (
              <option key={d.key} value={d.key}>
                {d.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Reporting manager">
          <select value={f.manager_user_id} onChange={set("manager_user_id")}>
            <option value="">None</option>
            {mgrOptions.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </Field>
        <div className="sm-row-end sm-wide">
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary btn-sm" disabled={busy}>
            {busy ? "Saving…" : mode === "new" ? "Add worker" : "Save changes"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

// Create or reset a worker's sign-in. Uses POST /api/super/workers/{id}/login.
function LoginDialog({ w, onClose, onSaved }) {
  const [email, setEmail] = useState(w.login_email || "");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [errs, setErrs] = useState({});
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    const x = {};
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) x.email = "Enter a valid email.";
    if (pw.length < 8 || !/[A-Za-z]/.test(pw) || !/\d/.test(pw)) x.pw = "At least 8 characters, letters and numbers.";
    if (pw !== pw2) x.pw2 = "Passwords do not match.";
    setErrs(x);
    if (Object.keys(x).length) return;
    setBusy(true);
    setErr("");
    try {
      const r = await apiFetch(`/api/super/workers/${w.id}/login`, {
        method: "POST",
        body: { email: email.trim(), password: pw, confirm_password: pw2 },
      });
      onSaved(
        `${w.name} can now sign in with ${r.email}${r.reset ? " (password reset)" : ""}. Share the password with them.`,
      );
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog title={`${w.has_login ? "Reset login" : "Give login"} · ${w.name}`} onClose={onClose}>
      <ErrorBox error={err} />
      <form className="form-grid sm-form" onSubmit={submit} noValidate>
        <Field label="Login email" error={errs.email} wide>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="worker@gmail.com"
            autoComplete="off"
            autoFocus
          />
        </Field>
        <Field label="Password" error={errs.pw}>
          <input type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="new-password" />
        </Field>
        <Field label="Confirm password" error={errs.pw2}>
          <input type="password" value={pw2} onChange={(e) => setPw2(e.target.value)} autoComplete="new-password" />
        </Field>
        <p className="muted sm-small sm-wide">
          The worker signs in on the Login page with this email and password and sees their own tasks, production
          updates and attendance.
        </p>
        <div className="sm-row-end sm-wide">
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary btn-sm" disabled={busy}>
            {busy ? "Saving…" : w.has_login ? "Reset login" : "Create login"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

import { useState } from "react";
import { apiFetch } from "../../../lib/api.js";
import { Badge, Dialog, Empty, ErrorBox, Field, Loading, Notice, PageHead, passwordProblem, useApi } from "../../../components/super/kit.jsx";
import "../../../owner.css";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Department managers: add, edit, assign department, activate/deactivate,
// reset password, and see each department's performance.
export default function SuperManagers() {
  const { data, error, loading, reload } = useApi("/api/super/managers", ["tasks", "orders", "production", "quality"]);
  const [form, setForm] = useState(null);
  const [reset, setReset] = useState(null);
  const [msg, setMsg] = useState(null);
  const [dept, setDept] = useState("");

  async function toggle(m) {
    const verb = m.is_active ? "Deactivate" : "Activate";
    if (!window.confirm(`${verb} ${m.name}? ${m.is_active ? "They will not be able to sign in." : ""}`)) return;
    try {
      await apiFetch(`/api/super/managers/${m.id}/active`, { method: "POST", body: { active: !m.is_active } });
      setMsg({ kind: "ok", text: `${m.name} ${m.is_active ? "deactivated" : "activated"}.` });
      reload();
    } catch (e) {
      setMsg({ kind: "err", text: e.message });
    }
  }

  const list = (data?.managers || []).filter((m) => !dept || m.department === dept);

  return (
    <div className="module sm-page">
      <PageHead title="Department managers" sub="The people who run each department. Each department gets its own screens.">
        <button className="btn btn-primary" onClick={() => setForm({ mode: "new" })}>
          ＋ Add manager
        </button>
      </PageHead>
      <Notice kind={msg?.kind} onClose={() => setMsg(null)}>
        {msg?.text}
      </Notice>
      <ErrorBox error={error} onRetry={reload} />

      <section className="panel">
        <div className="sm-toolbar">
          <h3>{list.length} managers</h3>
          <select className="sm-select" value={dept} onChange={(e) => setDept(e.target.value)} aria-label="Filter by department">
            <option value="">All departments</option>
            {(data?.departments || []).map((d) => (
              <option key={d.key} value={d.key}>
                {d.label}
              </option>
            ))}
          </select>
        </div>
        {loading && !data ? (
          <Loading />
        ) : list.length === 0 ? (
          <Empty>No department managers yet. Add the first one.</Empty>
        ) : (
          <div className="sm-cards">
            {list.map((m) => (
              <article key={m.id} className={`sm-person${m.is_active ? "" : " is-off"}`}>
                <header>
                  <span className="avatar">{m.name.split(" ").map((p) => p[0]).slice(0, 2).join("")}</span>
                  <div>
                    <strong>{m.name}</strong>
                    <small className="muted">{m.email || m.login_id || "—"}</small>
                  </div>
                  <Badge value={m.is_active ? "active" : "inactive"} label={m.is_active ? "Active" : "Inactive"} />
                </header>
                <p className="sm-dept-name">{m.department_label}</p>
                <dl className="sm-mini">
                  {m.department_metrics.map((x) => (
                    <div key={x.label}>
                      <dt>{x.label}</dt>
                      <dd>{x.value}</dd>
                    </div>
                  ))}
                  <div>
                    <dt>Tasks open / done</dt>
                    <dd>
                      {m.tasks_open} / {m.tasks_done}
                      {m.tasks_overdue > 0 && <Badge value="delayed" label={`${m.tasks_overdue} overdue`} />}
                    </dd>
                  </div>
                </dl>
                <footer className="sm-actions">
                  <button className="btn btn-ghost btn-sm" onClick={() => setForm({ mode: "edit", m })}>
                    Edit
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={() => setReset(m)}>
                    Reset password
                  </button>
                  <button className="link-btn" onClick={() => toggle(m)}>
                    {m.is_active ? "Deactivate" : "Activate"}
                  </button>
                </footer>
              </article>
            ))}
          </div>
        )}
      </section>

      {form && (
        <ManagerForm
          mode={form.mode}
          m={form.m}
          departments={data?.departments || []}
          onClose={() => setForm(null)}
          onSaved={(text) => {
            setForm(null);
            setMsg({ kind: "ok", text });
            reload();
          }}
        />
      )}
      {reset && (
        <ResetForm
          m={reset}
          onClose={() => setReset(null)}
          onSaved={() => {
            setReset(null);
            setMsg({ kind: "ok", text: `Password for ${reset.name} changed. Share it with them in person.` });
          }}
        />
      )}
    </div>
  );
}

function ManagerForm({ mode, m, departments, onClose, onSaved }) {
  const [f, setF] = useState({
    name: m?.name || "",
    email: m?.email || "",
    department: m?.department || "",
    password: "",
    confirm_password: "",
  });
  const [errs, setErrs] = useState({});
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    const x = {};
    if (f.name.trim().length < 2) x.name = "Enter the full name.";
    if (!EMAIL_RE.test(f.email.trim())) x.email = "Enter a valid email — they sign in with it.";
    if (!f.department) x.department = "Choose a department.";
    if (mode === "new") {
      const p = passwordProblem(f.password);
      if (p) x.password = p;
      if (f.password !== f.confirm_password) x.confirm_password = "Passwords do not match.";
    }
    setErrs(x);
    if (Object.keys(x).length) return;
    setBusy(true);
    setErr("");
    try {
      if (mode === "new") {
        await apiFetch("/api/super/managers", { method: "POST", body: { ...f, name: f.name.trim(), email: f.email.trim() } });
        onSaved(`${f.name.trim()} added. They sign in with ${f.email.trim()} and the password you set.`);
      } else {
        await apiFetch(`/api/super/managers/${m.id}`, {
          method: "PUT",
          body: { name: f.name.trim(), email: f.email.trim(), department: f.department },
        });
        onSaved(`${f.name.trim()} updated.`);
      }
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog title={mode === "new" ? "Add department manager" : `Edit ${m.name}`} onClose={onClose}>
      <ErrorBox error={err} />
      <form className="form-grid sm-form" onSubmit={submit} noValidate>
        <Field label="Full name" error={errs.name}>
          <input value={f.name} onChange={set("name")} autoComplete="off" />
        </Field>
        <Field label="Email (sign-in)" error={errs.email}>
          <input type="email" value={f.email} onChange={set("email")} autoComplete="off" />
        </Field>
        <Field label="Department" error={errs.department} wide>
          <select value={f.department} onChange={set("department")}>
            <option value="">Choose a department…</option>
            {departments.map((d) => (
              <option key={d.key} value={d.key}>
                {d.label}
              </option>
            ))}
          </select>
        </Field>
        {mode === "new" && (
          <>
            <Field label="Password" error={errs.password}>
              <input type="password" value={f.password} onChange={set("password")} autoComplete="new-password" />
            </Field>
            <Field label="Confirm password" error={errs.confirm_password}>
              <input type="password" value={f.confirm_password} onChange={set("confirm_password")} autoComplete="new-password" />
            </Field>
          </>
        )}
        <div className="sm-row-end sm-wide">
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary btn-sm" disabled={busy}>
            {busy ? "Saving…" : mode === "new" ? "Add manager" : "Save changes"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

function ResetForm({ m, onClose, onSaved }) {
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    const p = passwordProblem(pw);
    if (p) return setErr(p);
    if (pw !== pw2) return setErr("Passwords do not match.");
    setBusy(true);
    setErr("");
    try {
      await apiFetch(`/api/super/managers/${m.id}/reset-password`, { method: "POST", body: { password: pw, confirm_password: pw2 } });
      onSaved();
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title={`Reset password — ${m.name}`} onClose={onClose}>
      <p className="muted">Set a new password. It is never shown again, so share it with them in person.</p>
      <ErrorBox error={err} />
      <form className="form-grid sm-form" onSubmit={submit} noValidate>
        <Field label="New password">
          <input type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="new-password" />
        </Field>
        <Field label="Confirm new password">
          <input type="password" value={pw2} onChange={(e) => setPw2(e.target.value)} autoComplete="new-password" />
        </Field>
        <div className="sm-row-end sm-wide">
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary btn-sm" disabled={busy}>
            {busy ? "Saving…" : "Reset password"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

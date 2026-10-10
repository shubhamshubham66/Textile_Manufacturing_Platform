import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";

// Owner's Team page: create a manager with a login ID + password, and see the
// managers already created. A manager signs in with the ID (e.g. MGR-001).
const ID_RE = /^[A-Za-z0-9][A-Za-z0-9-]{2,19}$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const EMPTY = { name: "", login_id: "", password: "", confirm_password: "", email: "" };

function passwordProblem(pw) {
  if (pw.length < 8) return "At least 8 characters.";
  if (!/[A-Za-z]/.test(pw) || !/\d/.test(pw)) return "Use letters and numbers.";
  return "";
}

export default function Team() {
  const [managers, setManagers] = useState([]);
  const [nextId, setNextId] = useState("MGR-001");
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [error, setError] = useState("");
  const [created, setCreated] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      const d = await apiFetch("/api/team/managers");
      setManagers(d.managers);
      setNextId(d.next_login_id);
      setForm((f) => (f.login_id ? f : { ...f, login_id: d.next_login_id }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function onSubmit(e) {
    e.preventDefault();
    const errs = {};
    if (form.name.trim().length < 2) errs.name = "Enter the supermanager's full name.";
    if (!ID_RE.test(form.login_id.trim())) errs.login_id = "3–20 letters, numbers or dashes, e.g. MGR-001.";
    const pw = passwordProblem(form.password);
    if (pw) errs.password = pw;
    if (form.confirm_password !== form.password) errs.confirm_password = "Passwords do not match.";
    if (form.email.trim() && !EMAIL_RE.test(form.email.trim())) errs.email = "Enter a valid email, or leave it empty.";
    setErrors(errs);
    setError("");
    setCreated(null);
    if (Object.keys(errs).length) return;

    setSaving(true);
    try {
      const m = await apiFetch("/api/team/managers", {
        method: "POST",
        body: {
          name: form.name.trim(),
          login_id: form.login_id.trim(),
          password: form.password,
          confirm_password: form.confirm_password,
          email: form.email.trim() || null,
        },
      });
      setCreated(m);
      setForm(EMPTY);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="module">
      <h2>Team</h2>
      {error && <div className="form-error">{error}</div>}
      {created && (
        <div className="callout callout-ok">
          Supermanager <strong>{created.name}</strong> created. They sign in with login ID{" "}
          <strong>{created.login_id}</strong> and the password you set.
        </div>
      )}

      <section className="panel">
        <h3>Create supermanager</h3>
        <p className="muted">Give the supermanager a login ID and password. Share them in person.</p>
        <form className="team-form" onSubmit={onSubmit} noValidate>
          <label className="field">
            <span>Full name</span>
            <input value={form.name} onChange={set("name")} placeholder="e.g. Ravi Kumar" autoComplete="off" className={errors.name ? "invalid" : ""} />
            {errors.name && <small className="field-error">{errors.name}</small>}
          </label>
          <label className="field">
            <span>Login ID</span>
            <input
              value={form.login_id}
              onChange={(e) => setForm({ ...form, login_id: e.target.value.toUpperCase() })}
              placeholder={nextId}
              autoComplete="off"
              spellCheck={false}
              className={errors.login_id ? "invalid" : ""}
            />
            {errors.login_id && <small className="field-error">{errors.login_id}</small>}
          </label>
          <label className="field">
            <span>Password</span>
            <input type="password" value={form.password} onChange={set("password")} autoComplete="new-password" placeholder="At least 8 characters, letters and numbers" className={errors.password ? "invalid" : ""} />
            {errors.password && <small className="field-error">{errors.password}</small>}
          </label>
          <label className="field">
            <span>Confirm password</span>
            <input type="password" value={form.confirm_password} onChange={set("confirm_password")} autoComplete="new-password" placeholder="Type the password again" className={errors.confirm_password ? "invalid" : ""} />
            {errors.confirm_password && <small className="field-error">{errors.confirm_password}</small>}
          </label>
          <label className="field team-form-wide">
            <span>
              Gmail <small className="muted">(optional, lets them sign in with email too)</small>
            </span>
            <input type="email" value={form.email} onChange={set("email")} placeholder="supermanager@gmail.com" autoComplete="off" className={errors.email ? "invalid" : ""} />
            {errors.email && <small className="field-error">{errors.email}</small>}
          </label>
          <div className="team-form-wide">
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? "Creating…" : "Create supermanager"}
            </button>
          </div>
        </form>
      </section>

      <section className="panel">
        <div className="toolbar">
          <h3>Supermanagers</h3>
          <span className="muted">{managers.length} total</span>
        </div>
        {loading ? (
          <p className="muted">Loading…</p>
        ) : managers.length === 0 ? (
          <p className="muted">No supermanagers yet. Create the first one above.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Login ID</th>
                <th>Gmail</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {managers.map((m) => (
                <tr key={m.id}>
                  <td>{m.name}</td>
                  <td>
                    <code>{m.login_id}</code>
                  </td>
                  <td>{m.email || <span className="muted">—</span>}</td>
                  <td>
                    <span className={`status status-${m.is_active ? "pass" : "reject"}`}>{m.is_active ? "active" : "disabled"}</span>
                  </td>
                  <td>{m.created_at ? new Date(m.created_at).toLocaleDateString("en-IN") : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

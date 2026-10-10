import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext.jsx";

// Demo accounts, used only by the landing page's "Try as owner / buyer" links
// (/login?demo=owner). Nothing demo-related is shown on this page. Passwords are
// throwaway demo credentials (also in the README), not real secrets.
const DEMO_ACCOUNTS = [
  { role: "Owner", email: "owner@everest.test", password: "owner123" },
  { role: "Store manager", email: "store@everest.test", password: "store123" },
  {
    role: "Floor supervisor",
    email: "floor@everest.test",
    password: "floor123",
  },
  {
    role: "Quality inspector",
    email: "quality@everest.test",
    password: "quality123",
  },
  {
    role: "Accountant",
    email: "accounts@everest.test",
    password: "accounts123",
  },
  { role: "Buyer", email: "buyer@everest.test", password: "buyer123" },
];

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
// Staff login IDs the owner hands out, e.g. MGR-001.
const ID_RE = /^[A-Za-z0-9][A-Za-z0-9-]{2,19}$/;

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function validate() {
    const errs = {};
    const who = email.trim();
    if (!who) errs.email = "Enter your Gmail or login ID.";
    else if (who.includes("@") ? !EMAIL_RE.test(who) : !ID_RE.test(who))
      errs.email = "Enter a valid Gmail or login ID (e.g. MGR-001).";
    if (!password) errs.password = "Password is required.";
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function onSubmit(e) {
    e.preventDefault();
    setFormError("");
    if (!validate()) return;
    setSubmitting(true);
    try {
      const user = await login(email.trim(), password);
      // Redirect into the app after login.
      window.location.assign("/app");
      return user;
    } catch (err) {
      if (err.status === 401) setFormError("Invalid Gmail/ID or password.");
      else if (err.status === 403)
        setFormError(err.message || "Account disabled.");
      else
        setFormError(
          err.message || "Could not log in. Is the backend running?",
        );
    } finally {
      setSubmitting(false);
    }
  }

  // One-click demo login: logs in immediately with a demo account.
  async function quickLogin(account) {
    setFormError("");
    setFieldErrors({});
    setEmail(account.email);
    setPassword(account.password);
    setSubmitting(true);
    try {
      await login(account.email, account.password);
      window.location.assign("/app");
    } catch (err) {
      if (err.status === 401) setFormError("Invalid demo credentials.");
      else
        setFormError(
          err.message || "Could not log in. Is the backend running?",
        );
    } finally {
      setSubmitting(false);
    }
  }

  // "Try as owner / buyer" links from the landing page: /login?demo=owner logs
  // straight in with that demo account.
  useEffect(() => {
    const want = new URLSearchParams(window.location.search).get("demo");
    const account = DEMO_ACCOUNTS.find((a) => a.role.toLowerCase() === want);
    if (account) quickLogin(account);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <a href="/" className="brand auth-brand" style={{ display: "inline-flex", alignItems: "center", gap: "10px", textDecoration: "none", marginBottom: "16px" }}>
          <img
            src="/images/everest-logo.png"
            alt="Everest"
            style={{ height: "34px", width: "auto", objectFit: "contain" }}
          />
          <span className="brand-text" style={{ fontSize: "12px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.06em", color: "#1b2a6b", background: "#e8ebf6", padding: "3px 8px", borderRadius: "999px" }}>
            Textile Mills
          </span>
        </a>
        <h1 className="auth-title">Sign in</h1>
        <p className="muted">
          Welcome back. Enter your credentials to continue.
        </p>

        {formError && (
          <div className="form-error" role="alert">
            {formError}
          </div>
        )}

        <form onSubmit={onSubmit} noValidate>
          <label className="field">
            <span>Gmail or login ID</span>
            <input
              type="text"
              value={email}
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              placeholder="you@gmail.com or MGR-001"
              onChange={(e) => setEmail(e.target.value)}
              className={fieldErrors.email ? "invalid" : ""}
            />
            {fieldErrors.email && (
              <small className="field-error">{fieldErrors.email}</small>
            )}
          </label>

          <label className="field">
            <span>Password</span>
            <input
              type="password"
              value={password}
              autoComplete="current-password"
              placeholder="••••••••"
              onChange={(e) => setPassword(e.target.value)}
              className={fieldErrors.password ? "invalid" : ""}
            />
            {fieldErrors.password && (
              <small className="field-error">{fieldErrors.password}</small>
            )}
          </label>

          <button
            type="submit"
            className="btn btn-primary btn-block"
            disabled={submitting}
          >
            {submitting ? "Signing in…" : "Login"}
          </button>
        </form>

        <p className="muted auth-switch">
          New here? <a href="/signup">Create an account</a>
        </p>

        <p className="muted auth-foot">
          <a href="/">← Back to home</a>
        </p>
      </div>
    </div>
  );
}

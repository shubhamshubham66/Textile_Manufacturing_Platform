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

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function validate() {
    const errs = {};
    if (!email.trim()) errs.email = "Email is required.";
    else if (!EMAIL_RE.test(email.trim()))
      errs.email = "Enter a valid email address.";
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
      if (err.status === 401) setFormError("Invalid email or password.");
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
        <a href="/" className="brand auth-brand">
          <span className="brand-mark">ET</span>
          <span className="brand-text">Everest Textile Mills</span>
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
            <span>Email</span>
            <input
              type="email"
              value={email}
              autoComplete="username"
              placeholder="you@gmail.com"
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

import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api.js";

// Forgot password (buyer accounts):
//   1. Email -> "Send code" (6-digit code arrives by email)
//   2. Code + new password + confirm -> "Reset password"
// Staff logins (MGR-001 etc.) are reset by the owner / Supermanager.

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function passwordProblem(pw) {
  if (pw.length < 8) return "At least 8 characters.";
  if (!/[A-Za-z]/.test(pw) || !/\d/.test(pw)) return "Use letters and numbers.";
  return "";
}

export default function ForgotPassword() {
  const [email, setEmail] = useState(
    () => new URLSearchParams(window.location.search).get("email") || "",
  );
  const [otp, setOtp] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [sent, setSent] = useState(false);
  const [devOtp, setDevOtp] = useState("");
  const [timer, setTimer] = useState(0);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (timer <= 0) return undefined;
    const t = setTimeout(() => setTimer((n) => n - 1), 1000);
    return () => clearTimeout(t);
  }, [timer]);

  async function sendCode() {
    setFormError("");
    if (!EMAIL_RE.test(email.trim())) {
      setErrors({ email: "Enter the email you signed up with." });
      return;
    }
    setErrors({});
    setBusy("send");
    try {
      const data = await apiFetch("/api/auth/forgot/send-otp", {
        method: "POST",
        auth: false,
        body: { email: email.trim() },
      });
      setSent(true);
      setOtp("");
      setDevOtp(data.dev_otp || "");
      setTimer(data.resend_after || 60);
      setNotice(`${data.message} Check your inbox (and spam).`);
    } catch (err) {
      setFormError(err.message);
    } finally {
      setBusy("");
    }
  }

  async function reset(e) {
    e.preventDefault();
    setFormError("");
    const errs = {};
    if (!/^\d{6}$/.test(otp.trim())) errs.otp = "Enter the 6-digit code.";
    const pwErr = passwordProblem(password);
    if (pwErr) errs.password = pwErr;
    if (password !== confirm) errs.confirm = "Passwords do not match.";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy("reset");
    try {
      await apiFetch("/api/auth/forgot/reset", {
        method: "POST",
        auth: false,
        body: {
          email: email.trim(),
          otp: otp.trim(),
          password,
          confirm_password: confirm,
        },
      });
      setDone(true);
    } catch (err) {
      setFormError(err.message);
    } finally {
      setBusy("");
    }
  }

  if (done) {
    return (
      <div className="auth-wrap">
        <div className="auth-card signup-done">
          <div className="signup-tick" aria-hidden>✓</div>
          <h1 className="auth-title">Password changed</h1>
          <p className="muted">
            Sign in with <strong>{email.trim()}</strong> and your new password.
          </p>
          <a href="/login" className="btn btn-primary btn-block">
            Go to sign in
          </a>
        </div>
      </div>
    );
  }

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
        <h1 className="auth-title">Forgot password</h1>
        <p className="muted">
          For buyer accounts. We'll email you a code to set a new password.
        </p>

        {formError && (
          <div className="form-error" role="alert">
            {formError}
          </div>
        )}

        <form onSubmit={reset} noValidate>
          <label className="field">
            <span>Email (Gmail)</span>
            <div className="field-row">
              <input
                type="email"
                value={email}
                autoComplete="email"
                placeholder="you@gmail.com"
                onChange={(e) => setEmail(e.target.value)}
                className={errors.email ? "invalid" : ""}
                readOnly={sent}
              />
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={sendCode}
                disabled={busy === "send" || timer > 0}
              >
                {busy === "send"
                  ? "Sending…"
                  : timer > 0
                    ? `Resend in ${timer}s`
                    : sent
                      ? "Resend code"
                      : "Send code"}
              </button>
            </div>
            {errors.email && <small className="field-error">{errors.email}</small>}
          </label>

          {notice && <p className="form-note">{notice}</p>}

          {sent && (
            <>
              <label className="field">
                <span>Email code</span>
                {devOtp && (
                  <small className="dev-otp">Dev mode, no email set up. Code: {devOtp}</small>
                )}
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  value={otp}
                  autoComplete="one-time-code"
                  placeholder="6-digit code"
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                  className={errors.otp ? "invalid" : ""}
                />
                {errors.otp && <small className="field-error">{errors.otp}</small>}
              </label>
              <label className="field">
                <span>New password</span>
                <input
                  type="password"
                  value={password}
                  autoComplete="new-password"
                  placeholder="At least 8 characters, letters and numbers"
                  onChange={(e) => setPassword(e.target.value)}
                  className={errors.password ? "invalid" : ""}
                />
                {errors.password && <small className="field-error">{errors.password}</small>}
              </label>
              <label className="field">
                <span>Confirm password</span>
                <input
                  type="password"
                  value={confirm}
                  autoComplete="new-password"
                  placeholder="Type the password again"
                  onChange={(e) => setConfirm(e.target.value)}
                  className={errors.confirm ? "invalid" : ""}
                />
                {errors.confirm && <small className="field-error">{errors.confirm}</small>}
              </label>
              <button
                type="submit"
                className="btn btn-primary btn-block"
                disabled={busy === "reset"}
              >
                {busy === "reset" ? "Saving…" : "Reset password"}
              </button>
            </>
          )}
        </form>

        <p className="muted auth-foot">
          Staff login (e.g. MGR-001)? Ask the owner or Supermanager to reset it.
          <br />
          <a href="/login">← Back to sign in</a>
        </p>
      </div>
    </div>
  );
}

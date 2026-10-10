import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api.js";

// Signup, step by step:
//   1. Role + Name + Email  -> "Send OTP" (code arrives by email)
//   2. Enter the 6-digit code -> "Verify"
//   3. New password + Confirm password -> "Create account"
// After the account is made the page stays here and shows a "Go to sign in"
// button; it never jumps to another page on its own.
const ROLES = [
  { value: "owner", label: "Admin" },
  { value: "store_manager", label: "Store manager" },
  { value: "floor_supervisor", label: "Floor supervisor" },
  { value: "quality_inspector", label: "Quality inspector" },
  { value: "accountant", label: "Accountant" },
  { value: "buyer", label: "Buyer" },
];

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function passwordProblem(pw) {
  if (pw.length < 8) return "At least 8 characters.";
  if (!/[A-Za-z]/.test(pw) || !/\d/.test(pw)) return "Use letters and numbers.";
  return "";
}

export default function Signup() {
  const [role, setRole] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");

  const [otpSent, setOtpSent] = useState(false);
  const [devOtp, setDevOtp] = useState("");
  const [emailToken, setEmailToken] = useState("");
  const [timer, setTimer] = useState(0);
  const [busy, setBusy] = useState(""); // "send" | "verify" | "create"
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [notice, setNotice] = useState("");
  const [created, setCreated] = useState(false);

  const verified = !!emailToken;

  useEffect(() => {
    if (timer <= 0) return undefined;
    const id = setTimeout(() => setTimer((t) => t - 1), 1000);
    return () => clearTimeout(id);
  }, [timer]);

  // Changing the email after a code was sent starts the email step again.
  function onEmailChange(v) {
    setEmail(v);
    if (otpSent || verified) {
      setOtpSent(false);
      setEmailToken("");
      setOtp("");
      setDevOtp("");
      setNotice("");
    }
  }

  async function sendOtp() {
    const errs = {};
    if (!role) errs.role = "Choose your role.";
    if (name.trim().length < 2) errs.name = "Enter your full name.";
    if (!EMAIL_RE.test(email.trim())) errs.email = "Enter a valid email address.";
    setErrors(errs);
    setFormError("");
    if (Object.keys(errs).length) return;

    setBusy("send");
    try {
      const data = await apiFetch("/api/auth/signup/send-otp", {
        method: "POST",
        auth: false,
        body: { email: email.trim() },
      });
      setOtpSent(true);
      setOtp("");
      setDevOtp(data.dev_otp || "");
      setTimer(data.resend_after || 60);
      setNotice(`Code sent to ${email.trim()}. Check your inbox (and spam).`);
    } catch (err) {
      setFormError(err.message);
    } finally {
      setBusy("");
    }
  }

  async function verifyOtp() {
    if (!/^\d{6}$/.test(otp.trim())) {
      setErrors({ otp: "Enter the 6-digit code." });
      return;
    }
    setErrors({});
    setFormError("");
    setBusy("verify");
    try {
      const data = await apiFetch("/api/auth/signup/verify-otp", {
        method: "POST",
        auth: false,
        body: { email: email.trim(), otp: otp.trim() },
      });
      setEmailToken(data.email_token);
      setNotice("Email verified. Now set your password.");
    } catch (err) {
      setFormError(err.message);
    } finally {
      setBusy("");
    }
  }

  async function createAccount(e) {
    e.preventDefault();
    const errs = {};
    if (!role) errs.role = "Choose your role.";
    if (name.trim().length < 2) errs.name = "Enter your full name.";
    const pwErr = passwordProblem(password);
    if (pwErr) errs.password = pwErr;
    if (confirm !== password) errs.confirm = "Passwords do not match.";
    setErrors(errs);
    setFormError("");
    if (!verified || Object.keys(errs).length) return;

    setBusy("create");
    try {
      await apiFetch("/api/auth/signup", {
        method: "POST",
        auth: false,
        body: {
          name: name.trim(),
          email: email.trim(),
          role,
          password,
          confirm_password: confirm,
          email_token: emailToken,
        },
      });
      setCreated(true);
    } catch (err) {
      setFormError(err.message);
    } finally {
      setBusy("");
    }
  }

  if (created) {
    const roleLabel = ROLES.find((r) => r.value === role)?.label || role;
    return (
      <div className="auth-wrap">
        <div className="auth-card signup-done">
          <div className="signup-tick" aria-hidden>✓</div>
          <h1 className="auth-title">Account created</h1>
          <p className="muted">
            <strong>{name.trim()}</strong> ({roleLabel}) can now sign in with{" "}
            <strong>{email.trim()}</strong> and the password just set.
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
        <a href="/" className="brand auth-brand">
          <span className="brand-mark">ET</span>
          <span className="brand-text">Everest Textile Mills</span>
        </a>
        <h1 className="auth-title">Create account</h1>
        <p className="muted">Verify your email, then set a password.</p>

        {formError && (
          <div className="form-error" role="alert">
            {formError}
          </div>
        )}

        <form onSubmit={createAccount} noValidate>
          <label className="field">
            <span>Role</span>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className={errors.role ? "invalid" : ""}
            >
              <option value="">Select your role</option>
              {ROLES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
            {errors.role && <small className="field-error">{errors.role}</small>}
          </label>

          <label className="field">
            <span>Full name</span>
            <input
              type="text"
              value={name}
              autoComplete="name"
              placeholder="e.g. Ravi Kumar"
              onChange={(e) => setName(e.target.value)}
              className={errors.name ? "invalid" : ""}
            />
            {errors.name && <small className="field-error">{errors.name}</small>}
          </label>

          <label className="field">
            <span>Email (Gmail)</span>
            <div className="field-row">
              <input
                type="email"
                value={email}
                autoComplete="email"
                placeholder="you@gmail.com"
                onChange={(e) => onEmailChange(e.target.value)}
                className={errors.email ? "invalid" : ""}
                readOnly={verified}
              />
              {verified ? (
                <span className="field-badge">Verified</span>
              ) : (
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={sendOtp}
                  disabled={busy === "send" || timer > 0}
                >
                  {busy === "send"
                    ? "Sending…"
                    : timer > 0
                      ? `Resend in ${timer}s`
                      : otpSent
                        ? "Resend OTP"
                        : "Send OTP"}
                </button>
              )}
            </div>
            {errors.email && <small className="field-error">{errors.email}</small>}
          </label>

          {notice && <p className="form-note">{notice}</p>}

          {otpSent && !verified && (
            <label className="field">
              <span>Email code (OTP)</span>
              {devOtp && (
                <small className="dev-otp">Dev mode, no email set up. Code: {devOtp}</small>
              )}
              <div className="field-row">
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
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={verifyOtp}
                  disabled={busy === "verify"}
                >
                  {busy === "verify" ? "Checking…" : "Verify"}
                </button>
              </div>
              {errors.otp && <small className="field-error">{errors.otp}</small>}
            </label>
          )}

          {verified && (
            <>
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
            </>
          )}

          <button
            type="submit"
            className="btn btn-primary btn-block"
            disabled={!verified || busy === "create"}
          >
            {busy === "create" ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="muted auth-foot">
          Already have an account? <a href="/login">Sign in</a>
        </p>
      </div>
    </div>
  );
}

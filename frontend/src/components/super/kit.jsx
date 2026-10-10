// Small shared pieces for the Supermanager pages: data loading with live
// refresh, page header, stat cards, badges, empty/error states and a dialog.
import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "../../lib/api.js";
import { isLiveRefresh, useLive } from "../../live/LiveContext.jsx";
import { statusLabel } from "../../lib/format.js";

// Load `path` (a string or a function returning one); reload quietly when a
// live change arrives on any of `topics`.
export function useApi(path, topics = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const pathRef = useRef(path);
  pathRef.current = path;

  const load = useCallback(async () => {
    if (!isLiveRefresh()) setLoading(true);
    setError("");
    try {
      setData(await apiFetch(pathRef.current));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [path, load]);
  useLive(topics.length ? topics : ["__none__"], load);
  return { data, error, loading, reload: load, setData };
}

export function go(path) {
  window.dispatchEvent(new CustomEvent("etm:navigate", { detail: { path } }));
}

export function PageHead({ title, sub, children }) {
  return (
    <div className="sm-head">
      <div>
        <h2>{title}</h2>
        {sub && <p className="muted">{sub}</p>}
      </div>
      {children && <div className="sm-head-actions">{children}</div>}
    </div>
  );
}

export function Stat({ label, value, hint, tone, onClick }) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag className={`sm-stat${tone ? ` tone-${tone}` : ""}`} onClick={onClick} type={onClick ? "button" : undefined}>
      <span className="sm-stat-label">{label}</span>
      <strong className="sm-stat-value">{value}</strong>
      {hint && <span className="sm-stat-hint">{hint}</span>}
    </Tag>
  );
}

const TONE = {
  pending_review: "amber", clarification: "amber", draft: "grey", confirmed: "blue",
  in_production: "blue", in_quality: "violet", ready_to_ship: "teal", dispatched: "green",
  closed: "green", rejected: "red", cancelled: "red",
  pending: "grey", in_progress: "blue", completed: "green", delayed: "red",
  running: "green", idle: "amber", maintenance: "red", breakdown: "red",
  pass: "green", rework: "amber", reject: "red", packed: "grey", loaded: "blue", shipped: "green",
  present: "green", half_day: "amber", absent: "red", not_marked: "grey",
  low: "grey", medium: "blue", high: "amber", urgent: "red",
  critical: "red", warning: "amber", info: "blue",
  active: "green", inactive: "grey", ok: "green", issues: "red", waiting: "amber",
};

const EXTRA_LABEL = {
  pending_review: "Pending review", clarification: "Needs clarification", rejected: "Rejected",
  in_progress: "In progress", completed: "Completed", delayed: "Delayed", not_marked: "Not marked",
  half_day: "Half day", maintenance: "Maintenance", urgent: "Urgent", high: "High", medium: "Medium",
  low: "Low", critical: "Critical", warning: "Warning", info: "Info", issues: "Has issues",
  waiting: "Waiting", ok: "OK",
};

export function Badge({ value, label }) {
  if (!value) return null;
  return (
    <span className={`sm-badge tone-${TONE[value] || "grey"}`}>
      {label || EXTRA_LABEL[value] || statusLabel(value)}
    </span>
  );
}

export function Loading({ text = "Loading…" }) {
  return (
    <div className="sm-state" role="status">
      <span className="sm-spinner" aria-hidden /> {text}
    </div>
  );
}

export function ErrorBox({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="form-error sm-error">
      {error}
      {onRetry && (
        <button className="link-btn" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function Empty({ children }) {
  return <p className="sm-empty muted">{children}</p>;
}

export function Notice({ kind = "ok", children, onClose }) {
  if (!children) return null;
  return (
    <div className={`callout ${kind === "ok" ? "callout-ok" : "callout-warn"} sm-notice`}>
      <span>{children}</span>
      {onClose && (
        <button className="link-btn" onClick={onClose}>
          dismiss
        </button>
      )}
    </div>
  );
}

export function Dialog({ title, onClose, children, wide }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose?.();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="owner-drawer-backdrop" onClick={onClose}>
      <div
        className={`owner-dialog sm-dialog${wide ? " is-wide" : ""}`}
        role="dialog"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sm-dialog-head">
          <h3>{title}</h3>
          <button className="icon-btn sm-close" aria-label="Close" onClick={onClose}>
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Field({ label, error, children, wide }) {
  return (
    <label className={`field${wide ? " sm-wide" : ""}`}>
      <span>{label}</span>
      {children}
      {error && <small className="field-error">{error}</small>}
    </label>
  );
}

export function when(iso) {
  if (!iso) return "—";
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  return d.toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function day(iso) {
  if (!iso) return "—";
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}

export function passwordProblem(pw) {
  if (pw.length < 8) return "At least 8 characters.";
  if (!/[A-Za-z]/.test(pw) || !/\d/.test(pw)) return "Use letters and numbers.";
  return "";
}

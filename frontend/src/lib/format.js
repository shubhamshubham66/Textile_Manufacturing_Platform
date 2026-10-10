// Shared display helpers.

// Indian-format rupees, ALWAYS 2 decimals, sign in front of the symbol:
//   1234.5   -> ₹1,234.50
//   -158890  -> −₹1,58,890.00
export function inr(n) {
  const v = Number(n) || 0;
  const abs = Math.abs(v).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${v < 0 ? "−" : ""}₹${abs}`;
}

// Quantity with Indian grouping and a unit suffix (no forced decimals):
//   qty(7637.3, "m") -> "7,637.3 m"
export function qty(n, unit = "") {
  const v = Number(n) || 0;
  const s = v.toLocaleString("en-IN", { maximumFractionDigits: 2 });
  return unit ? `${s} ${unit}` : s;
}

// Hours, 1–2 decimals, with an "h" suffix.
export function hrs(n) {
  const v = Number(n) || 0;
  return `${v.toLocaleString("en-IN", { maximumFractionDigits: 2 })} h`;
}

// ISO date (YYYY-MM-DD or full ISO) -> dd/mm/yyyy. Returns "—" when empty.
export function ddmmyyyy(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) {
    // Already a plain YYYY-MM-DD without time — split manually.
    const parts = String(value).slice(0, 10).split("-");
    if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`;
    return String(value);
  }
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${dd}/${mm}/${d.getFullYear()}`;
}

// Month helpers for the month selector. value is "YYYY-MM".
export function currentMonthValue() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

// "YYYY-MM" -> { start: "YYYY-MM-01", end: "YYYY-MM-<lastday>" }.
export function monthRange(value) {
  const [y, mo] = String(value).split("-").map(Number);
  const last = new Date(y, mo, 0).getDate();
  const pad = (n) => String(n).padStart(2, "0");
  return { start: `${y}-${pad(mo)}-01`, end: `${y}-${pad(mo)}-${pad(last)}` };
}

// "YYYY-MM" -> "October 2026" for display.
export function monthLabel(value) {
  const [y, mo] = String(value).split("-").map(Number);
  if (!y || !mo) return "";
  const d = new Date(y, mo - 1, 1);
  return d.toLocaleDateString("en-IN", { month: "long", year: "numeric" });
}

// Internal status codes -> readable labels ("in_production" -> "In production").
const STATUS_LABELS = {
  draft: "Draft",
  pending_review: "Pending review",
  clarification: "Needs clarification",
  rejected: "Rejected",
  confirmed: "Confirmed",
  in_production: "In production",
  in_quality: "In quality check",
  ready_to_ship: "Ready to ship",
  dispatched: "Dispatched",
  closed: "Closed",
  cancelled: "Cancelled",
  // payment / invoice
  paid: "Paid",
  part_paid: "Partial",
  unpaid: "Unpaid",
  // rolls
  pending: "Pending",
  pass: "Pass",
  rework: "Rework",
  reject: "Reject",
};

export function statusLabel(s) {
  if (!s) return "";
  return (
    STATUS_LABELS[s] ||
    String(s)
      .replace(/_/g, " ")
      .replace(/^\w/, (c) => c.toUpperCase())
  );
}

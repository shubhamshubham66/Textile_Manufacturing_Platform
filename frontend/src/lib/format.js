// Shared display helpers.

// Indian-format rupees with the sign in front of the symbol: −₹1,58,890
export function inr(n) {
  const v = Number(n) || 0;
  const abs = Math.abs(v).toLocaleString("en-IN", { maximumFractionDigits: 2 });
  return `${v < 0 ? "−" : ""}₹${abs}`;
}

// Money with exactly 2 decimals + Indian grouping: ₹7,637.30, −₹1,58,890.00
export function money(n) {
  const v = Number(n) || 0;
  const abs = Math.abs(v).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${v < 0 ? "−" : ""}₹${abs}`;
}

// A dash for truly-not-applicable money cells (avoids "₹0" noise).
export function moneyOrDash(n) {
  return Number(n) ? money(n) : "—";
}

// Metres / hours with 2 decimals and grouping.
export function qty(n, unit = "") {
  const v = (Number(n) || 0).toLocaleString("en-IN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
  return unit ? `${v} ${unit}` : v;
}

// Current month as "YYYY-MM".
export function currentMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

// "2026-10" -> "October 2026"
export function monthLabel(ym) {
  if (!ym) return "";
  const [y, m] = ym.split("-").map(Number);
  const names = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
  ];
  return `${names[m - 1]} ${y}`;
}

// Build a list of recent months as [{value:"2026-10", label:"October 2026"}].
export function recentMonths(count = 12) {
  const out = [];
  const d = new Date();
  for (let i = 0; i < count; i++) {
    const ym = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    out.push({ value: ym, label: monthLabel(ym) });
    d.setMonth(d.getMonth() - 1);
  }
  return out;
}

// Internal status codes -> readable labels ("in_production" -> "In production").
const STATUS_LABELS = {
  draft: "Draft",
  confirmed: "Confirmed",
  in_production: "In production",
  in_quality: "In quality check",
  ready_to_ship: "Ready to ship",
  dispatched: "Dispatched",
  closed: "Closed",
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

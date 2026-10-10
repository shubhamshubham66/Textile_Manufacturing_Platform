// Shared display helpers.

// Indian-format rupees with the sign in front of the symbol: −₹1,58,890
export function inr(n) {
  const v = Number(n) || 0;
  const abs = Math.abs(v).toLocaleString("en-IN", { maximumFractionDigits: 2 });
  return `${v < 0 ? "−" : ""}₹${abs}`;
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
    String(s).replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase())
  );
}

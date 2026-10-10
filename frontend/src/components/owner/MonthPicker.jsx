import { monthLabel } from "../../lib/format.js";

// A plain native month input styled to match the app's inputs. Owner pages only.
// value is "YYYY-MM"; onChange gets the new "YYYY-MM" string.
export default function MonthPicker({ value, onChange, label = "Month" }) {
  return (
    <label className="owner-month">
      <span>{label}</span>
      <input
        type="month"
        value={value}
        max="2099-12"
        onChange={(e) => onChange(e.target.value)}
        aria-label={`Month, currently ${monthLabel(value)}`}
      />
    </label>
  );
}

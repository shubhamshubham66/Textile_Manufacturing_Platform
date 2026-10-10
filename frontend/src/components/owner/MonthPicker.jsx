// Month selector for the owner Dashboard and Reports. Owner-only component.
export default function MonthPicker({ value, options, onChange }) {
  return (
    <label className="month-picker">
      <span className="muted">Month</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label="Select month"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

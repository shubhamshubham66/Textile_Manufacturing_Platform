// Lightweight, dependency-free SVG charts for the owner pages.
// Every chart: a title, units in labels, hover tooltips (<title>), and an
// aria-label text alternative so the data is reachable without the visual.
// Colours come from CSS variables defined in index.css (owner-* classes).

import { inr } from "../../lib/format.js";

const AX = "#64748b"; // axis/label grey

function niceMax(v) {
  if (v <= 0) return 1;
  const mag = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / mag;
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
  return step * mag;
}

/* --------------------------------------------------------------------- */
/* Waterfall (bridge): payments in -> bills out -> wages out -> net        */
/* steps: [{ label, value, kind: "in"|"out"|"net" }]                       */
/* --------------------------------------------------------------------- */
export function Waterfall({ steps, title = "Profit or loss this month" }) {
  const W = 520;
  const H = 240;
  const padL = 56;
  const padB = 48;
  const padT = 12;
  const plotH = H - padB - padT;
  const barW = 56;
  const gap =
    (W - padL - 16 - steps.length * barW) / Math.max(1, steps.length - 1);

  // Running cumulative to position floating bars; net sits on the baseline.
  let running = 0;
  const segs = steps.map((s) => {
    if (s.kind === "net") {
      const seg = { ...s, from: 0, to: s.value };
      return seg;
    }
    const from = running;
    const to = s.kind === "in" ? running + s.value : running - s.value;
    running = to;
    return { ...s, from, to };
  });

  const allVals = segs.flatMap((s) => [s.from, s.to]).concat(0);
  const maxV = Math.max(...allVals);
  const minV = Math.min(...allVals, 0);
  const span = maxV - minV || 1;
  const y = (v) => padT + plotH - ((v - minV) / span) * plotH;

  const colour = (kind) =>
    kind === "in"
      ? "var(--owner-pos)"
      : kind === "out"
        ? "var(--owner-neg)"
        : "#0f766e";

  const aria = steps
    .map((s) => `${s.label} ${inr(s.kind === "out" ? -s.value : s.value)}`)
    .join("; ");

  return (
    <figure
      className="owner-chart"
      role="group"
      aria-label={`${title}: ${aria}`}
    >
      <figcaption className="owner-chart-title">{title}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img">
        {/* zero baseline */}
        <line
          x1={padL}
          y1={y(0)}
          x2={W - 16}
          y2={y(0)}
          stroke={AX}
          strokeWidth="1"
        />
        {segs.map((s, i) => {
          const x = padL + i * (barW + gap);
          const top = Math.min(y(s.from), y(s.to));
          const h = Math.max(2, Math.abs(y(s.from) - y(s.to)));
          return (
            <g key={s.label}>
              <rect
                x={x}
                y={top}
                width={barW}
                height={h}
                rx="2"
                fill={colour(s.kind)}
              >
                <title>
                  {s.label}: {inr(s.kind === "out" ? -s.value : s.value)}
                </title>
              </rect>
              <text
                x={x + barW / 2}
                y={H - padB + 16}
                textAnchor="middle"
                fontSize="11"
                fill={AX}
              >
                {s.label}
              </text>
              <text
                x={x + barW / 2}
                y={top - 4}
                textAnchor="middle"
                fontSize="10.5"
                fill="#334155"
                className="owner-chart-num"
              >
                {inr(s.kind === "out" ? -s.value : s.value)}
              </text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}

/* --------------------------------------------------------------------- */
/* Horizontal bars. data: [{ label, value, colour?, onClick? }]           */
/* --------------------------------------------------------------------- */
export function HBars({ data, title, unit = "", money = false, onBarClick }) {
  const max = niceMax(Math.max(1, ...data.map((d) => d.value)));
  const fmt = (v) =>
    money ? inr(v) : `${v.toLocaleString("en-IN")}${unit ? " " + unit : ""}`;
  const aria = data.map((d) => `${d.label} ${fmt(d.value)}`).join("; ");
  return (
    <figure
      className="owner-chart"
      role="group"
      aria-label={`${title}: ${aria}`}
    >
      <figcaption className="owner-chart-title">{title}</figcaption>
      <div className="owner-hbars">
        {data.length === 0 ? (
          <p className="muted">No data for this month.</p>
        ) : (
          data.map((d) => (
            <div
              className={`owner-hbar-row ${onBarClick ? "clickable" : ""}`}
              key={d.label}
              onClick={onBarClick ? () => onBarClick(d) : undefined}
              role={onBarClick ? "button" : undefined}
              tabIndex={onBarClick ? 0 : undefined}
              onKeyDown={
                onBarClick
                  ? (e) => (e.key === "Enter" || e.key === " ") && onBarClick(d)
                  : undefined
              }
              title={`${d.label}: ${fmt(d.value)}`}
            >
              <span className="owner-hbar-label">{d.label}</span>
              <span className="owner-hbar-track">
                <span
                  className="owner-hbar-fill"
                  style={{
                    width: `${(d.value / max) * 100}%`,
                    background: d.colour || "var(--owner-accent)",
                  }}
                />
              </span>
              <span className="owner-hbar-num">{fmt(d.value)}</span>
            </div>
          ))
        )}
      </div>
    </figure>
  );
}

/* --------------------------------------------------------------------- */
/* Stacked bars per category. series: [{key,label,colour}];               */
/* data: [{ label, parts: {key: value}, marker?: {value,label} }]         */
/* Used for cost-per-order (yarn/wages/machine) with a revenue marker.     */
/* --------------------------------------------------------------------- */
export function StackedBars({ data, series, title, markerLabel = "Revenue" }) {
  const totals = data.map(
    (d) =>
      series.reduce((a, s) => a + (d.parts[s.key] || 0), 0) +
      Math.max(
        0,
        d.marker
          ? d.marker.value -
              series.reduce((a, s) => a + (d.parts[s.key] || 0), 0)
          : 0,
      ),
  );
  const max = niceMax(
    Math.max(
      1,
      ...data.map((d, i) => Math.max(totals[i], d.marker?.value || 0)),
    ),
  );
  const aria = data
    .map(
      (d) =>
        `${d.label}: ` +
        series.map((s) => `${s.label} ${inr(d.parts[s.key] || 0)}`).join(", ") +
        (d.marker ? `, ${markerLabel} ${inr(d.marker.value)}` : ""),
    )
    .join("; ");

  return (
    <figure
      className="owner-chart"
      role="group"
      aria-label={`${title}: ${aria}`}
    >
      <figcaption className="owner-chart-title">{title}</figcaption>
      <div className="owner-legend">
        {series.map((s) => (
          <span key={s.key} className="owner-legend-item">
            <span
              className="owner-legend-swatch"
              style={{ background: s.colour }}
            />
            {s.label}
          </span>
        ))}
        <span className="owner-legend-item">
          <span className="owner-legend-swatch owner-legend-marker" />
          {markerLabel}
        </span>
      </div>
      <div className="owner-stacked">
        {data.length === 0 ? (
          <p className="muted">No data for this month.</p>
        ) : (
          data.map((d) => {
            const cost = series.reduce((a, s) => a + (d.parts[s.key] || 0), 0);
            return (
              <div
                className="owner-stacked-col"
                key={d.label}
                title={`${d.label}: cost ${inr(cost)}`}
              >
                <div className="owner-stacked-bar">
                  {d.marker != null && (
                    <span
                      className="owner-stacked-marker"
                      style={{ bottom: `${(d.marker.value / max) * 100}%` }}
                      title={`${markerLabel}: ${inr(d.marker.value)}`}
                    />
                  )}
                  {series.map((s) => {
                    const v = d.parts[s.key] || 0;
                    if (v <= 0) return null;
                    return (
                      <span
                        key={s.key}
                        className="owner-stacked-seg"
                        style={{
                          height: `${(v / max) * 100}%`,
                          background: s.colour,
                        }}
                        title={`${s.label}: ${inr(v)}`}
                      />
                    );
                  })}
                </div>
                <span className="owner-stacked-label">{d.label}</span>
              </div>
            );
          })
        )}
      </div>
    </figure>
  );
}

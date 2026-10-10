import { money } from "../../lib/format.js";

// Simple, dependency-free waterfall (bridge) chart for the month P&L:
// buyer payments in (green, up) -> bills out (red, down) -> wages out (red, down)
// -> net (highlighted). Pure SVG. Includes an aria-label text alternative.
export default function Waterfall({ inAmount, bills, wages, net }) {
  const steps = [
    { label: "Payments in", delta: +inAmount, kind: "in" },
    { label: "Bills", delta: -bills, kind: "out" },
    { label: "Wages", delta: -wages, kind: "out" },
    { label: net >= 0 ? "Net profit" : "Net loss", total: net, kind: "net" },
  ];

  // Compute running cumulative to place floating bars.
  const maxVal = Math.max(inAmount, 1);
  const W = 520;
  const H = 180;
  const padB = 28;
  const padT = 10;
  const colW = 70;
  const gap = (W - steps.length * colW) / (steps.length + 1);
  const scale = (H - padB - padT) / maxVal;

  let running = 0;
  const bars = steps.map((s, i) => {
    const x = gap + i * (colW + gap);
    let yTop, h, cls;
    if (s.kind === "net") {
      yTop = H - padB - Math.abs(net) * scale;
      h = Math.abs(net) * scale;
      cls = net >= 0 ? "wf-net-pos" : "wf-net-neg";
    } else {
      const before = running;
      running += s.delta;
      const top = Math.max(before, running);
      yTop = H - padB - top * scale;
      h = Math.abs(s.delta) * scale;
      cls = s.kind === "in" ? "wf-in" : "wf-out";
    }
    return { x, yTop: Math.max(padT, yTop), h: Math.max(2, h), cls, s };
  });

  const alt =
    `Payments in ${money(inAmount)}, bills ${money(bills)}, ` +
    `wages ${money(wages)}, net ${money(net)}.`;

  return (
    <figure className="waterfall" aria-label={alt}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        preserveAspectRatio="xMidYMid meet"
        className="waterfall-svg"
      >
        {bars.map((b, i) => (
          <g key={i}>
            <rect
              x={b.x}
              y={b.yTop}
              width={colW}
              height={b.h}
              rx="3"
              className={b.cls}
            />
            <text
              x={b.x + colW / 2}
              y={H - padB + 16}
              textAnchor="middle"
              className="wf-x"
            >
              {b.s.label}
            </text>
            <text
              x={b.x + colW / 2}
              y={b.yTop - 4}
              textAnchor="middle"
              className="wf-v"
            >
              {money(b.s.kind === "net" ? b.s.total : b.s.delta)}
            </text>
          </g>
        ))}
      </svg>
    </figure>
  );
}

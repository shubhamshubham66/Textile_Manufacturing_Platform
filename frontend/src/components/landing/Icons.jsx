// Small inline SVG icons for the landing page (stroke icons, inherit colour).

const base = {
  width: 22,
  height: 22,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
};

// Logo: two warp threads and two weft threads, interlaced.
export function BrandMark({ size = 30 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden className="lp-mark">
      <rect width="32" height="32" rx="8" fill="var(--lp-indigo)" />
      <g strokeWidth="4" strokeLinecap="round" fill="none">
        <path d="M11 6v20" stroke="#fff" />
        <path d="M21 6v20" stroke="#fff" />
        <path d="M6 11h7M17 11h9" stroke="var(--lp-haldi)" />
        <path d="M6 21h9M19 21h7" stroke="var(--lp-haldi)" />
      </g>
    </svg>
  );
}

export const IconSpool = (p) => (
  <svg {...base} {...p}>
    <path d="M6 4h12M6 20h12" />
    <path d="M8 4v16M16 4v16" />
    <path d="M8 8l8 2M8 12l8 2M8 16l8 2" />
  </svg>
);

export const IconLoom = (p) => (
  <svg {...base} {...p}>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="M7 5v14M11 5v14M15 5v14M3 10h18M3 14h18" />
  </svg>
);

export const IconRoll = (p) => (
  <svg {...base} {...p}>
    <ellipse cx="7" cy="12" rx="3" ry="6" />
    <path d="M7 6h11a3 6 0 0 1 0 12H7" />
    <circle cx="7" cy="12" r="1" />
  </svg>
);

export const IconTruck = (p) => (
  <svg {...base} {...p}>
    <path d="M3 6h11v10H3zM14 10h4l3 3v3h-7" />
    <circle cx="7" cy="18" r="2" />
    <circle cx="17" cy="18" r="2" />
  </svg>
);

export const IconOrder = (p) => (
  <svg {...base} {...p}>
    <path d="M6 3h9l3 3v15H6z" />
    <path d="M9 10h6M9 14h6M9 18h3" />
  </svg>
);

export const IconCheck = (p) => (
  <svg {...base} {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="M8 11l2 2 4-4M16 16l5 5" />
  </svg>
);

export const IconChart = (p) => (
  <svg {...base} {...p}>
    <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
  </svg>
);

export const IconEye = (p) => (
  <svg {...base} {...p}>
    <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);

export const IconBell = (p) => (
  <svg {...base} {...p}>
    <path d="M6 16V11a6 6 0 1 1 12 0v5l2 2H4z" />
    <path d="M10 20a2 2 0 0 0 4 0" />
  </svg>
);

export const IconArrow = (p) => (
  <svg {...base} width={18} height={18} {...p}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);

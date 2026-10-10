// Line icons for the landing page (24px grid, stroke = currentColor).
// <Icon name="loom" size={40} /> or the named exports below.

const PATHS = {
  spool: "M6 4h12M6 20h12M8 4v16M16 4v16M8 8l8 2M8 12l8 2M8 16l8 2",
  loom: "M3 5h18v14H3zM7 5v14M11 5v14M15 5v14M3 10h18M3 14h18",
  roll: "M7 6a3 6 0 1 0 0 12a3 6 0 1 0 0-12zM7 6h11a3 6 0 0 1 0 12H7M7 11.5v1",
  truck: "M3 6h11v10H3zM14 10h4l3 3v3h-7M5 18a2 2 0 1 0 4 0a2 2 0 1 0-4 0M15 18a2 2 0 1 0 4 0a2 2 0 1 0-4 0",
  order: "M6 3h9l3 3v15H6zM9 10h6M9 14h6M9 18h3",
  qc: "M4 11a7 7 0 1 0 14 0a7 7 0 1 0-14 0M8 11l2 2 4-4M16 16l5 5",
  chart: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  trend: "M3 17l6-6 4 4 8-8M15 7h6v6",
  eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM9 12a3 3 0 1 0 6 0a3 3 0 1 0-6 0",
  bell: "M6 16v-5a6 6 0 1 1 12 0v5l2 2H4zM10 20a2 2 0 0 0 4 0",
  arrow: "M5 12h14M13 6l6 6-6 6",
  rupee: "M7 4h10M7 8h10M13 4c3 0 4 2 4 4s-2 4-5 4H8l7 8",
  users: "M9 11a4 4 0 1 0 0-8a4 4 0 1 0 0 8zM2 21v-1a6 6 0 0 1 12 0v1M16 3.5a4 4 0 0 1 0 7M18 14a5 5 0 0 1 4 5v2",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM8.5 12l2.5 2.5 4.5-5",
  bolt: "M13 2L4 14h7l-1 8 9-12h-7z",
  cloud: "M7 18a5 5 0 1 1 1-9.9A6 6 0 0 1 19 10a4 4 0 0 1 0 8zM12 12v5M10 15l2 2 2-2",
  layers: "M12 3l9 5-9 5-9-5zM3 13l9 5 9-5M3 17.5l9 5 9-5",
  gear: "M12 15a3 3 0 1 0 0-6a3 3 0 1 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z",
  clock: "M12 21a9 9 0 1 0 0-18a9 9 0 1 0 0 18zM12 7v5l3 2",
  qr: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h3v3h-3zM18 18h3v3h-3zM6 6h1v1H6zM17 6h1v1h-1zM6 17h1v1H6z",
  factory: "M2 21h20M4 21V11l5 3v-3l5 3v-3l5 3V4h2v17",
  wallet: "M3 7h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM3 7l12-4v4M16 13.5h2",
  phone: "M7 2h10v20H7zM11 18h2",
  chat: "M4 4h16v12H8l-4 4zM8 9h8M8 12h5",
  recycle: "M7 19H4l2.5-4.5M17 19h3l-2.5-4.5M9 5.5L12 3l3 2.5M6.5 14.5L9 10M17.5 14.5L15 10M7 19h10M12 3v0",
  puzzle: "M10 3h4v3a2 2 0 1 0 4 0V3h3v7h-3a2 2 0 1 0 0 4h3v7h-7v-3a2 2 0 1 0-4 0v3H3v-7h3a2 2 0 1 0 0-4H3V3z",
  target: "M12 21a9 9 0 1 0 0-18a9 9 0 1 0 0 18zM12 16a4 4 0 1 0 0-8a4 4 0 1 0 0 8zM12 12h.01",
  calendar: "M4 5h16v16H4zM4 10h16M8 3v4M16 3v4M8 14h3v3H8z",
  doc: "M6 3h9l3 3v15H6zM15 3v3h3M9 12h6M9 16h6",
  link: "M10 14a4 4 0 0 0 6 0l3-3a4 4 0 0 0-6-6l-1 1M14 10a4 4 0 0 0-6 0l-3 3a4 4 0 0 0 6 6l1-1",
  cotton: "M12 13a3 3 0 1 0 0-6a3 3 0 1 0 0 6zM7 11a3 3 0 1 1 3-4M17 11a3 3 0 1 0-3-4M8 14a3 3 0 1 0 4 2M16 14a3 3 0 1 1-4 2M12 18v4",
  dye: "M12 3s6 7 6 11a6 6 0 0 1-12 0c0-4 6-11 6-11zM9 15a3 3 0 0 0 3 3",
  check: "M5 12l5 5L20 7",
  star: "M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z",
};

export function Icon({ name, size = 24, strokeWidth = 1.7, ...rest }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...rest}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}

// Logo: two warp threads and two weft threads, interlaced.
export function BrandMark({ size = 32 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden className="lp-mark">
      <rect width="32" height="32" rx="8" fill="var(--lp-blue)" />
      <g strokeWidth="4" strokeLinecap="round" fill="none">
        <path d="M11 6v20" stroke="#fff" />
        <path d="M21 6v20" stroke="#fff" />
        <path d="M6 11h7M17 11h9" stroke="var(--lp-gold)" />
        <path d="M6 21h9M19 21h7" stroke="var(--lp-gold)" />
      </g>
    </svg>
  );
}

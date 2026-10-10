// Features: cards for the six headline capabilities.
const FEATURES = [
  {
    icon: "📦",
    title: "Stock alerts",
    text: "Live yarn stock with a warning before it runs low, and a yarn-sufficiency check on every new order.",
  },
  {
    icon: "🏭",
    title: "Live machine status",
    text: "See which order is on which machine, how far along it is, and what's idle or broken — without walking the floor.",
  },
  {
    icon: "🧾",
    title: "Roll traceability",
    text: "Every roll is linked to its order and machine, with a pass / rework / reject record you can trust.",
  },
  {
    icon: "👤",
    title: "Buyer tracking",
    text: "Buyers see whether their order is being woven, checked or ready to ship — in their own portal.",
  },
  {
    icon: "📈",
    title: "Profit report",
    text: "Raw-material bills, wages and buyer payments come together into a monthly profit-or-loss view.",
  },
  {
    icon: "⏱️",
    title: "Idle machine loss in ₹",
    text: "Our unique point: idle hours × hourly cost shown as a real rupee loss on the dashboard.",
    highlight: true,
  },
];

export default function Features() {
  return (
    <section id="features" className="section">
      <div className="section-inner">
        <h2 className="section-title">What you get</h2>
        <p className="section-sub">
          Everything the floor, the office and the owner need, in one place.
        </p>
        <div className="feature-grid">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className={`feature-card ${f.highlight ? "feature-highlight" : ""}`}
            >
              <div className="feature-icon" aria-hidden>
                {f.icon}
              </div>
              <h3>{f.title}</h3>
              <p>{f.text}</p>
              {f.highlight && <span className="feature-tag">Our edge</span>}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

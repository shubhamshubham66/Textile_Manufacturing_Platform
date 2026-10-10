// How it works: 5 steps — Order, Yarn, Make, Check, Ship.
const STEPS = [
  {
    n: 1,
    title: "Order",
    icon: "📝",
    text: "A buyer places an order with fabric type, colour, quantity and deadline.",
  },
  {
    n: 2,
    title: "Yarn",
    icon: "🧵",
    text: "Yarn is received into the store; the system checks there's enough for the order.",
  },
  {
    n: 3,
    title: "Make",
    icon: "⚙️",
    text: "Yarn runs through spinning, weaving and dyeing with live machine status.",
  },
  {
    n: 4,
    title: "Check",
    icon: "🔍",
    text: "Each roll is inspected — pass, rework or reject — and traced to its order.",
  },
  {
    n: 5,
    title: "Ship",
    icon: "🚚",
    text: "Passed rolls are packed and dispatched with a matching invoice. No double dispatch.",
  },
];

export default function HowItWorks() {
  return (
    <section id="how" className="section section-alt">
      <div className="section-inner">
        <h2 className="section-title">How it works</h2>
        <p className="section-sub">Five steps, from order to shipment.</p>
        <ol className="steps">
          {STEPS.map((s) => (
            <li key={s.n} className="step">
              <div className="step-icon" aria-hidden>
                {s.icon}
              </div>
              <div className="step-no">Step {s.n}</div>
              <h3>{s.title}</h3>
              <p>{s.text}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

import { Icon } from "./landing/Icons.jsx";

// Feature grid: nine cards (icon on top, title, one line), with a blue block
// sitting behind the right edge of the grid.
const FEATURES = [
  { icon: "spool", title: "Yarn stock & alerts", text: "Live stock by count and colour, with low-stock warnings." },
  { icon: "order", title: "Order yarn check", text: "A yes/no yarn check before any order is confirmed." },
  { icon: "loom", title: "Floor board", text: "Every machine's order, progress and status at a glance." },
  { icon: "clock", title: "Idle-loss tracking", text: "Stops logged with a reason and costed in rupees." },
  { icon: "qc", title: "Roll quality check", text: "Pass, rework or reject, with the defect noted." },
  { icon: "qr", title: "Roll traceability", text: "Each roll links back to its order and machine." },
  { icon: "truck", title: "Dispatch & invoice", text: "Ship passed rolls and print the invoice in one step." },
  { icon: "users", title: "Wages & attendance", text: "Daily attendance turned into monthly wages." },
  { icon: "chart", title: "Monthly profit & loss", text: "Yarn bills, wages and payments in one P&L." },
];

export default function Features() {
  return (
    <section id="features" className="lp-section">
      <div className="lp-inner">
        <div className="lp-head">
          <h2 className="lp-title">
            Top <span className="lp-outline">features</span> of our mill platform
          </h2>
          <p>Spun around how Everest actually works, from the yarn gate to the bank.</p>
        </div>

        <div className="lp-grid-wrap">
          <ul className="lp-grid">
            {FEATURES.map((f) => (
              <li key={f.title} className="lp-card">
                <span className="lp-card-icon">
                  <Icon name={f.icon} size={44} strokeWidth={1.4} />
                </span>
                <h3>{f.title}</h3>
                <p>{f.text}</p>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

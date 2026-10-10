import { Icon } from "./landing/Icons.jsx";

// Key benefits around a process diagram of our own mill: three benefits on
// each side, the six production stages in the middle joined by a thread.
const LEFT = [
  {
    title: "Less idle time",
    text: "Stops are logged with a reason the moment they happen, so the same fault doesn't eat a shift twice.",
  },
  {
    title: "Fewer bad rolls",
    text: "Every roll is inspected and graded; rework and reject reasons show which machine needs attention.",
  },
  {
    title: "Yarn never runs out",
    text: "Stock warns before it runs low, and orders are checked against yarn before they're promised.",
  },
];

const RIGHT = [
  {
    title: "Buyers stop calling",
    text: "Buyers see their own orders move from weaving to quality to ready-to-ship, and nothing else.",
  },
  {
    title: "Dispatch without mistakes",
    text: "Only passed rolls can ship, a roll can never ship twice, and the invoice prints with the dispatch.",
  },
  {
    title: "The real monthly profit",
    text: "Yarn bills, wages and buyer payments meet in one profit-or-loss the owner can trust.",
  },
];

const STAGES = [
  { icon: "cotton", label: "Yarn inward", who: "Store" },
  { icon: "spool", label: "Spinning", who: "Floor" },
  { icon: "loom", label: "Weaving", who: "Floor" },
  { icon: "dye", label: "Dyeing", who: "Floor" },
  { icon: "qc", label: "Quality check", who: "Inspector" },
  { icon: "truck", label: "Dispatch & invoice", who: "Store + Accounts" },
];

function Benefit({ title, text }) {
  return (
    <li>
      <h3>{title}</h3>
      <p>
        <span className="lp-tick">
          <Icon name="check" size={12} strokeWidth={3} />
        </span>
        {text}
      </p>
    </li>
  );
}

export default function HowItWorks() {
  return (
    <section id="how" className="lp-section lp-section-tint">
      <div className="lp-inner">
        <div className="lp-head">
          <h2 className="lp-title">
            Key <span className="lp-outline">benefits</span> for the mill
          </h2>
          <p>Yarn in, fabric out: six stages, each handled by the right person.</p>
        </div>

        <div className="lp-benefits">
          <ul className="lp-benefit-list">
            {LEFT.map((b) => (
              <Benefit key={b.title} {...b} />
            ))}
          </ul>

          <ol className="lp-process">
            {STAGES.map((s, i) => (
              <li key={s.label}>
                <span className="lp-process-icon">
                  <Icon name={s.icon} size={34} strokeWidth={1.5} />
                </span>
                <b>
                  {i + 1}. {s.label}
                </b>
                <small>{s.who}</small>
              </li>
            ))}
          </ol>

          <ul className="lp-benefit-list">
            {RIGHT.map((b) => (
              <Benefit key={b.title} {...b} />
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

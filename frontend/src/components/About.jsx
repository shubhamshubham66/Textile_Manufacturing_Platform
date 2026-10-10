// About: what the mill runs on today, and what replaces each piece.
const SWAPS = [
  {
    before: "Yarn stock in a notebook",
    after: "Live yarn stock with a low-stock warning, and a yarn check on every new order",
  },
  {
    before: "Walking the floor to find an order",
    after: "A floor board: which order is on which machine, how far along, what's idle or broken",
  },
  {
    before: "Quality on paper slips",
    after: "Each roll inspected as pass, rework or reject, traced to its order and machine",
  },
  {
    before: "Buyers phoning for updates",
    after: "A buyer portal showing whether the order is being woven, checked or ready to ship",
  },
  {
    before: "Wages in a register",
    after: "Attendance, wages, yarn bills and buyer payments in one monthly profit-or-loss",
  },
];

export default function About() {
  return (
    <section id="about" className="lp-section">
      <div className="lp-inner">
        <div className="lp-head">
          <h2>The mill&apos;s memory lives in people. We put it in one system.</h2>
          <p>
            Orders get delayed, machines sit idle, and nobody knows what a single
            roll really cost. Here is what changes.
          </p>
        </div>

        <ul className="lp-swaps">
          {SWAPS.map((s) => (
            <li key={s.before}>
              <span className="lp-before">{s.before}</span>
              <span className="lp-swap-arrow" aria-hidden>
                →
              </span>
              <span className="lp-after">{s.after}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

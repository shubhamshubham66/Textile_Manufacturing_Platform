import {
  IconBell,
  IconEye,
  IconRoll,
  IconChart,
  IconOrder,
  IconCalendar,
} from "./landing/Icons.jsx";

// Features: the idle-loss USP gets the big panel; the rest sit beside it.
const FEATURES = [
  {
    Icon: IconBell,
    title: "Stock that warns you",
    text: "Low-yarn alerts, and a yes/no yarn check before you confirm an order.",
  },
  {
    Icon: IconEye,
    title: "The floor without walking it",
    text: "Every machine's order, progress, and today's metres at a glance.",
  },
  {
    Icon: IconRoll,
    title: "Every roll traceable",
    text: "Each roll links back to its order and machine, with its inspection result.",
  },
  {
    Icon: IconOrder,
    title: "Buyers track their own orders",
    text: "Their own orders and invoices only, never anyone else's.",
  },
  {
    Icon: IconCalendar,
    title: "Attendance, no register",
    text: "Mark who's in once; wages are worked out and added to each order's cost.",
  },
  {
    Icon: IconChart,
    title: "The month's real profit",
    text: "Yarn bills, wages and buyer payments meet in one profit-or-loss.",
  },
];

export default function Features() {
  return (
    <section id="features" className="lp-section">
      <div className="lp-inner">
        <div className="lp-head">
          <h2>What the owner gets that a register never gave</h2>
        </div>

        <div className="lp-features">
          {/* Left: full-height photo, idle-loss card sitting inside it at the bottom */}
          <div className="lp-photo">
            <img
              src="/images/floor-tablet.jpg"
              alt="A loom operator checking the day's numbers on a tablet"
              loading="lazy"
            />
            <article className="lp-usp">
              <span className="lp-usp-tag">Only in Everest</span>
              <h3>Idle machine loss, in rupees</h3>
              <p>
                Every stop is logged with a reason: no yarn, motor fault, shift
                changeover. Idle time stops being a feeling and becomes a number
                on the owner&apos;s dashboard.
              </p>
              <div
                className="lp-formula"
                aria-label="Idle hours times hourly cost equals rupees lost"
              >
                <span>
                  <b>11.5 h</b>
                  <small>idle + breakdown</small>
                </span>
                <i>×</i>
                <span>
                  <b>₹250–400</b>
                  <small>per machine-hour</small>
                </span>
                <i>=</i>
                <span className="lp-formula-total">
                  <b>₹3,404</b>
                  <small>lost today</small>
                </span>
              </div>
              <p className="lp-usp-foot">
                Top reason today: motor fault on Spin-03 (4 h).
              </p>
            </article>
          </div>

          <ul className="lp-feature-list">
            {FEATURES.map(({ Icon, title, text }) => (
              <li key={title}>
                <span className="lp-feature-icon">
                  <Icon />
                </span>
                <div>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

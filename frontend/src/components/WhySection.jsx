import { Icon } from "./landing/Icons.jsx";

// "Why" section: an illustration of the platform's screens on the left,
// twelve reasons with gold-ringed icons on the right.
const REASONS = [
  { icon: "factory", text: "Built for one mill: ours" },
  { icon: "rupee", text: "Idle loss shown in rupees" },
  { icon: "order", text: "Yarn check before every order" },
  { icon: "users", text: "Six role-based logins" },
  { icon: "qr", text: "Every roll traceable" },
  { icon: "doc", text: "One-click invoice PDFs" },
  { icon: "eye", text: "Buyer portal for order status" },
  { icon: "trend", text: "Monthly profit or loss" },
  { icon: "chat", text: "AI assistant on live data" },
  { icon: "phone", text: "Works on any phone" },
  { icon: "cloud", text: "Cloud hosted, nothing to install" },
  { icon: "shield", text: "Each person sees only their part" },
];

function Illustration() {
  return (
    <div className="lp-illus" aria-hidden>
      <div className="lp-illus-card lp-illus-main">
        <div className="lp-illus-head">
          <i /> <i /> <i />
          <span>Owner dashboard</span>
        </div>
        <div className="lp-illus-bars">
          {[45, 70, 55, 85, 62, 92, 74].map((h, n) => (
            <span key={n} style={{ height: `${h}%` }} />
          ))}
        </div>
        <div className="lp-illus-lines">
          <span />
          <span />
          <span />
        </div>
      </div>
      <div className="lp-illus-card lp-illus-money">
        <small>Profit this month</small>
        <b>₹4.8 L</b>
        <svg viewBox="0 0 120 36" preserveAspectRatio="none">
          <path d="M0 30 L20 24 L40 27 L60 15 L80 18 L100 8 L120 4" />
        </svg>
      </div>
      <div className="lp-illus-card lp-illus-qc">
        <Icon name="roll" size={26} />
        <div>
          <b>Roll R-0412</b>
          <small>Passed · Grade A</small>
        </div>
      </div>
      <div className="lp-illus-card lp-illus-pie">
        <svg viewBox="0 0 42 42">
          <circle cx="21" cy="21" r="15.9" className="a" />
          <circle cx="21" cy="21" r="15.9" className="b" strokeDasharray="62 38" />
          <circle cx="21" cy="21" r="15.9" className="c" strokeDasharray="18 82" strokeDashoffset="-62" />
        </svg>
        <small>Machine time</small>
      </div>
    </div>
  );
}

export default function WhySection() {
  return (
    <section id="why" className="lp-section">
      <div className="lp-inner">
        <div className="lp-head">
          <h2 className="lp-title">
            Why <span className="lp-outline lp-outline-gold">Everest ERP</span>?
          </h2>
          <p>A platform shaped around one mill&apos;s daily problems, not a generic package.</p>
        </div>

        <div className="lp-why">
          <Illustration />
          <ul className="lp-reasons">
            {REASONS.map((r) => (
              <li key={r.text}>
                <span className="lp-ring">
                  <Icon name={r.icon} size={24} />
                </span>
                {r.text}
              </li>
            ))}
          </ul>
        </div>

        <div className="lp-center">
          <a href="/login" className="lp-btn lp-btn-primary lp-btn-lg">
            Login to the platform
          </a>
        </div>
      </div>
    </section>
  );
}

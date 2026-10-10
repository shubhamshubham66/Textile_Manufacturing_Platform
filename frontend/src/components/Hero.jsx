import { useEffect, useState } from "react";
import { Icon } from "./landing/Icons.jsx";

// Hero: pitch on the left, a laptop + phone showing our own floor board on the
// right, then a blue wave band with the mill's numbers. The only animation is
// the idle-loss counter (skipped when the user prefers reduced motion).
// Figures are demo values that match the seeded data.

const MACHINES = [
  { name: "Spin-01", status: "running", pct: 72 },
  { name: "Spin-02", status: "idle" },
  { name: "Spin-03", status: "breakdown" },
  { name: "Weave-01", status: "running", pct: 37 },
  { name: "Weave-02", status: "running", pct: 58 },
  { name: "Weave-03", status: "idle" },
  { name: "Dye-01", status: "running", pct: 21 },
  { name: "Dye-02", status: "idle" },
];

// ₹/second lost by the idle + broken machines (250+250+400+300 ₹/hr).
const LOSS_PER_SEC = 1200 / 3600;
const START_LOSS = 3404;

function useTickingLoss() {
  const [loss, setLoss] = useState(START_LOSS);
  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const t0 = Date.now();
    const id = setInterval(() => {
      setLoss(START_LOSS + ((Date.now() - t0) / 1000) * LOSS_PER_SEC);
    }, 250);
    return () => clearInterval(id);
  }, []);
  return loss;
}

const rupees = (n) => "₹" + Math.floor(n).toLocaleString("en-IN");

function LaptopMock({ loss }) {
  return (
    <div className="lp-devices" aria-label="Everest platform on laptop and phone">
      <div className="lp-laptop">
        <div className="lp-screen">
          <div className="lp-app-bar">
            <b>Everest ERP</b>
            <span>Floor board</span>
            <i className="lp-live-dot" /> <small>Live</small>
          </div>
          <div className="lp-app-kpis">
            <div>
              <small>Running</small>
              <b className="is-green">4 / 8</b>
            </div>
            <div>
              <small>Metres today</small>
              <b>2,340</b>
            </div>
            <div>
              <small>Idle loss</small>
              <b className="is-red">{rupees(loss)}</b>
            </div>
          </div>
          <div className="lp-app-tiles">
            {MACHINES.map((m) => (
              <div key={m.name} className={`lp-app-tile is-${m.status}`}>
                <span>{m.name}</span>
                {m.pct ? (
                  <em>
                    <i style={{ width: `${m.pct}%` }} />
                  </em>
                ) : (
                  <small>{m.status}</small>
                )}
              </div>
            ))}
          </div>
          <div className="lp-app-chart" aria-hidden>
            {[40, 62, 48, 75, 58, 82, 66, 90, 70, 86].map((h, i) => (
              <i key={i} style={{ height: `${h}%` }} />
            ))}
          </div>
        </div>
        <div className="lp-laptop-base" />
      </div>

      <div className="lp-phone">
        <div className="lp-phone-screen">
          <small>Buyer portal</small>
          <b>ORD-2003</b>
          <span className="lp-phone-pill">Weaving · 37%</span>
          <em>
            <i style={{ width: "37%" }} />
          </em>
          <small>Due 24 Oct</small>
          <span className="lp-phone-line">
            <Icon name="check" size={11} strokeWidth={3} /> Yarn issued
          </span>
          <span className="lp-phone-line">
            <Icon name="check" size={11} strokeWidth={3} /> Spinning done
          </span>
          <span className="lp-phone-line is-now">
            <Icon name="loom" size={11} /> Weaving now
          </span>
          <span className="lp-phone-row">
            <Icon name="roll" size={12} /> 4 rolls passed QC
          </span>
        </div>
      </div>
    </div>
  );
}

export default function Hero() {
  const loss = useTickingLoss();

  const STATS = [
    { value: "8", label: "Machines tracked live" },
    { value: "6", label: "Role-based logins" },
    { value: "5", label: "Stages, yarn to truck" },
    { value: rupees(loss), label: "Idle loss caught today", hot: true },
    { value: "100%", label: "Rolls traceable" },
  ];

  return (
    <section id="home" className="lp-hero">
      <div className="lp-hero-top">
        <div className="lp-hero-inner">
          <div className="lp-hero-copy">
            <h1>
              <span className="lp-outline">Textile ERP</span> for
              <br />
              Everest Textile Mills
            </h1>
            <p className="lp-lead">
              Thread every order from the yarn gate to the invoice. Store, floor,
              quality, dispatch and the owner&apos;s books in one platform built
              only for our mill.
            </p>
            <div className="lp-hero-cta">
              <a href="/login" className="lp-btn lp-btn-primary lp-btn-lg">
                Open the platform
              </a>
              <a
                href="#how"
                className="lp-btn lp-btn-outline lp-btn-lg"
                onClick={(e) => {
                  e.preventDefault();
                  document.getElementById("how")?.scrollIntoView({ behavior: "smooth" });
                }}
              >
                See how it works
              </a>
            </div>
            <p className="lp-hero-note">
              One-click demo logins for all six roles are on the login page.
            </p>
          </div>
          <LaptopMock loss={loss} />
        </div>
        <svg className="lp-wave" viewBox="0 0 1440 160" preserveAspectRatio="none" aria-hidden>
          <path d="M0 40 C 260 170, 520 170, 760 90 S 1200 0, 1440 30 V160 H0 Z" />
        </svg>
      </div>

      <div className="lp-band">
        <ul className="lp-stats">
          {STATS.map((s) => (
            <li key={s.label} className={s.hot ? "is-hot" : ""}>
              <b>{s.value}</b>
              <span>{s.label}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

import { useEffect, useState } from "react";

// Hero: the pitch on the left, a live-looking "floor board" on the right.
// The floor board is the one animated moment on the page: the idle-loss counter
// ticks up while machines sit idle — the product's unique point, shown not told.
// Figures are illustrative demo values (they match the seeded demo data).

const MACHINES = [
  { name: "Spin-01", stage: "Spinning", status: "running", order: "ORD-2004", pct: 72 },
  { name: "Spin-02", stage: "Spinning", status: "idle", note: "Waiting for yarn" },
  { name: "Spin-03", stage: "Spinning", status: "breakdown", note: "Motor fault" },
  { name: "Weave-01", stage: "Weaving", status: "running", order: "ORD-2003", pct: 37 },
  { name: "Weave-02", stage: "Weaving", status: "running", order: "ORD-2004", pct: 58 },
  { name: "Weave-03", stage: "Weaving", status: "idle", note: "No order assigned" },
  { name: "Dye-01", stage: "Dyeing", status: "running", order: "ORD-2003", pct: 21 },
  { name: "Dye-02", stage: "Dyeing", status: "idle", note: "Shift changeover" },
];

// ₹ per second lost by the idle/breakdown machines above (250+250+400+300 ₹/hr).
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

function scrollTo(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
}

export default function Hero() {
  const loss = useTickingLoss();
  const stopped = MACHINES.filter((m) => m.status !== "running").length;

  return (
    <section id="home" className="lp-hero">
      <div className="lp-hero-inner">
        <div className="lp-hero-copy">
          <p className="lp-kicker">For Everest Textile Mills · yarn to invoice</p>
          <h1>
            Every idle loom costs money.
            <br />
            <span>Now you can see how much.</span>
          </h1>
          <p className="lp-lead">
            One platform for the store, the floor, quality, dispatch and the
            owner&apos;s books. No notebooks, no paper slips, no phone calls to
            ask where an order is.
          </p>
          <div className="lp-hero-cta">
            <a href="/login" className="lp-btn lp-btn-primary lp-btn-lg">
              Login
            </a>
            <a
              href="#how"
              className="lp-btn lp-btn-outline lp-btn-lg"
              onClick={(e) => {
                e.preventDefault();
                scrollTo("how");
              }}
            >
              <span className="lp-play" aria-hidden>▶</span> Watch demo
            </a>
          </div>
          <p className="lp-hero-note">
            Judges: one-click demo logins for all six roles are on the login page.
          </p>
        </div>

        <div className="lp-board" aria-label="Example floor board">
          <div className="lp-board-head">
            <span>Floor board</span>
            <span className="lp-live">
              <i /> Live · Shift A
            </span>
          </div>

          {["Spinning", "Weaving", "Dyeing"].map((stage) => (
            <div className="lp-board-row" key={stage}>
              <span className="lp-board-stage">{stage}</span>
              <div className="lp-board-tiles">
                {MACHINES.filter((m) => m.stage === stage).map((m) => (
                  <div className={`lp-tile is-${m.status}`} key={m.name}>
                    <div className="lp-tile-top">
                      <b>{m.name}</b>
                      <span className="lp-status">{m.status}</span>
                    </div>
                    {m.status === "running" ? (
                      <>
                        <span className="lp-tile-sub">{m.order}</span>
                        <span className="lp-bar">
                          <span style={{ width: `${m.pct}%` }} />
                        </span>
                      </>
                    ) : (
                      <span className="lp-tile-sub">{m.note}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}

          <div className="lp-board-loss">
            <div>
              <span className="lp-loss-label">Lost to idle &amp; breakdown today</span>
              <span className="lp-loss-value">
                ₹{Math.floor(loss).toLocaleString("en-IN")}
              </span>
            </div>
            <span className="lp-loss-meta">
              {stopped} of {MACHINES.length} machines stopped
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}

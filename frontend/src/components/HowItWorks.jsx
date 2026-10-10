// How it works: five steps from order to truck, as cards that step up like a
// staircase over a photo of the mill floor. The last step (Ship) is dark.
const ICON = {
  order: (
    <>
      <path d="M7 3h7l4 4v14H7z" />
      <path d="M14 3v4h4" />
      <path d="M9.5 12h5M9.5 16h5" />
    </>
  ),
  yarn: (
    <>
      <path d="M6 4h12M6 20h12" />
      <path d="M8 4v16M16 4v16" />
      <path d="M8 9l8-2M8 13l8-2M8 17l8-2" />
    </>
  ),
  make: (
    <>
      <rect x="4" y="5" width="16" height="14" rx="1.5" />
      <path d="M4 10h16M4 14.5h16M9.5 5v14M14.5 5v14" />
    </>
  ),
  check: (
    <>
      <circle cx="11" cy="11" r="6.5" />
      <path d="M8.5 11l2 2 3.5-4" />
      <path d="M16 16l4.5 4.5" />
    </>
  ),
  ship: (
    <>
      <path d="M3 6h11v10H3z" />
      <path d="M14 9h4l3 3v4h-7" />
      <circle cx="7.5" cy="17.5" r="1.8" />
      <circle cx="17" cy="17.5" r="1.8" />
    </>
  ),
};

const STEPS = [
  { icon: "order", title: "Order", who: "Owner", text: "Enter fabric, colour, metres and deadline. The system says at once whether there's enough yarn." },
  { icon: "yarn", title: "Yarn", who: "Store manager", text: "Log yarn at the gate. Stock updates live and warns before it runs low." },
  { icon: "make", title: "Make", who: "Floor supervisor", text: "Assign machines for spinning, weaving and dyeing; log output and every stop with a reason." },
  { icon: "check", title: "Check", who: "Quality inspector", text: "Inspect each roll: pass, rework or reject, with the defect noted." },
  { icon: "ship", title: "Ship", who: "Store manager", text: "Pick passed rolls, dispatch and print the invoice in one step. A roll can never ship twice." },
];

export default function HowItWorks() {
  return (
    <section id="how" className="lp-stairs">
      <div className="lp-stairs-inner">
        <div className="lp-stairs-head">
          <h2>From order to truck in five steps</h2>
          <p>Each person sees only their step. The owner sees all of it.</p>
        </div>

        <ol className="lp-stairs-steps">
          {STEPS.map((s, i) => (
            <li
              key={s.title}
              className={`lp-stair ${i === STEPS.length - 1 ? "is-last" : ""}`}
              style={{ "--i": i }}
            >
              <div className="lp-stair-top">
                <span className="lp-stair-no">{String(i + 1).padStart(2, "0")}</span>
                <svg
                  width="28"
                  height="28"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.75"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  {ICON[s.icon]}
                </svg>
              </div>
              <h3>{s.title}</h3>
              <span className="lp-stair-who">{s.who}</span>
              <p>{s.text}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

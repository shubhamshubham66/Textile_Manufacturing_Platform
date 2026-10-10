import { Icon } from "./landing/Icons.jsx";

// "Keys" section: three bordered boxes, each with its icon sitting in a notch
// cut out of the top border.
const KEYS = [
  {
    icon: "eye",
    title: "Live floor visibility",
    text: "Every spinning, weaving and dyeing machine on one board: which order it runs, how far along it is, and what's idle or broken. No more walking the floor to find an order.",
  },
  {
    icon: "rupee",
    title: "Zero idle-loss blindness",
    text: "Each stop is logged with a reason (no yarn, motor fault, changeover) and turned into rupees, so the owner sees what idle machines really cost every single day.",
  },
  {
    icon: "puzzle",
    title: "Integrated modules",
    text: "Yarn store, production, quality, dispatch, wages and accounts share one database. An order flows from gate to invoice without being typed twice.",
  },
];

export default function About() {
  return (
    <section id="about" className="lp-section lp-section-tint">
      <div className="lp-inner">
        <div className="lp-head">
          <h2 className="lp-title">
            Keys to a smoother <span className="lp-outline">mill floor</span>
          </h2>
          <p>What changes when the mill stops running on notebooks and phone calls.</p>
        </div>

        <div className="lp-keys">
          {KEYS.map((k) => (
            <article key={k.title} className="lp-key">
              <span className="lp-key-icon">
                <Icon name={k.icon} size={52} strokeWidth={1.4} />
              </span>
              <h3>{k.title}</h3>
              <p>{k.text}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

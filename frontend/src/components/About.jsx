// About: what the system gives the mill, one item per point.
const POINTS = [
  { title: "Yarn stock", text: "Live yarn stock with a low-stock warning, and a yarn check on every new order" },
  { title: "Floor board", text: "Which order is on which machine, how far along, what's idle or broken" },
  { title: "Roll quality", text: "Each roll inspected as pass, rework or reject, traced to its order and machine" },
  { title: "Buyer portal", text: "Buyers see whether their order is being woven, checked or ready to ship" },
  { title: "Wages & profit", text: "Attendance, wages, yarn bills and buyer payments in one monthly profit-or-loss" },
];

// Photo of the weaving floor on the left, numbered list on the right.
function About() {
  return (
    <section id="about" className="lp-section">
      <div className="lp-inner lp-av-split">
        <figure className="lp-av-photo">
          <img src="/images/weaving-floor.jpg" alt="A weaver checking fabric on a loom on the weaving floor" loading="lazy" />
          <figcaption>
            <b>5</b> registers replaced by one system
          </figcaption>
        </figure>
        <div>
          <div className="lp-head lp-head-left">
            <h2>The mill&apos;s memory lives in people. We put it in one system.</h2>
            <p>Orders get delayed, machines sit idle, and nobody knows what a single roll really cost.</p>
          </div>
          <ol className="lp-av-list">
            {POINTS.map(({ title, text }, i) => (
              <li key={title}>
                <span className="lp-av-no">{String(i + 1).padStart(2, "0")}</span>
                <div>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}

export default About;

// About: who Everest is, the five problems the mill had, and the solution.
const PROBLEMS = [
  { title: "Yarn stock lives in a notebook", text: "Nobody knows what's left until a machine stops for want of yarn." },
  { title: "Orders are found by walking the floor", text: "Which order is on which machine, and how far along, is anyone's guess." },
  { title: "Quality is noted on paper slips", text: "Rejected rolls can't be traced back to the order or machine that made them." },
  { title: "Buyers phone for every update", text: "Staff stop work to answer \u201cwhere is my order?\u201d calls all day." },
  { title: "Wages and costs sit in separate registers", text: "No one sees the month's real profit or loss until it's too late." },
];

export default function About() {
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
            <span className="lp-eyebrow">About Everest Textile Mills</span>
            <h2>The mill&apos;s memory lives in people. We put it in one system.</h2>
            <p>
              Everest spins, weaves and dyes cotton fabric under one roof, with a
              store, a machine floor, quality checks and dispatch. Until now all
              of it ran on notebooks, slips and phone calls.
            </p>
          </div>

          <h3 className="lp-av-label">The problem</h3>
          <ol className="lp-av-list">
            {PROBLEMS.map(({ title, text }, i) => (
              <li key={title}>
                <span className="lp-av-no">{String(i + 1).padStart(2, "0")}</span>
                <div>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </div>
              </li>
            ))}
          </ol>

          <div className="lp-av-solution">
            <h3>The solution</h3>
            <p>
              One platform where the store, floor, quality, dispatch and accounts
              teams share live data: yarn stock with warnings, a live floor board,
              roll-by-roll quality, a buyer portal and a monthly profit-or-loss.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

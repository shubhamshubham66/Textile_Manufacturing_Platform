// About: the problem (5 points) and the solution (5 points), text drawn from the
// README, plus the unique point about the mill's memory living in people.
const PROBLEMS = [
  "Raw material stock lives in a notebook.",
  "Machine and order status is only known by walking the floor.",
  "Quality checks are recorded on paper slips.",
  "Buyers get order updates by phone calls.",
  "Worker attendance and wages sit in a register.",
];

const SOLUTIONS = [
  "Live yarn stock with low-stock alerts and a yarn check on new orders.",
  "A real-time floor view: which order is on which machine, and what's idle or broken.",
  "Digital roll inspection — pass, rework or reject — traceable to order and machine.",
  "A buyer portal where buyers track their own orders without a phone call.",
  "Attendance, wages, bills and payments feed one profit-or-loss view.",
];

export default function About() {
  return (
    <section id="about" className="section">
      <div className="section-inner">
        <h2 className="section-title">The problem, and what we do about it</h2>

        <div className="callout">
          <strong>The real issue:</strong> today the mill's memory lives in
          people, not in a system. When someone is away, the knowledge walks out
          with them.
        </div>

        <div className="two-col">
          <div className="panel panel-problem">
            <h3>Today (the pain)</h3>
            <ul className="check-list cross">
              {PROBLEMS.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </div>
          <div className="panel panel-solution">
            <h3>With Everest</h3>
            <ul className="check-list tick">
              {SOLUTIONS.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}

import { IconOrder, IconSpool, IconLoom, IconCheck, IconTruck } from "./landing/Icons.jsx";

// How it works: the five steps an order goes through, in order, with the role
// that handles each step. A thread runs through them like warp through a loom.
const STEPS = [
  {
    title: "Order",
    who: "Owner",
    Icon: IconOrder,
    text: "Enter fabric, colour, metres and deadline. The system says at once whether there's enough yarn.",
  },
  {
    title: "Yarn",
    who: "Store manager",
    Icon: IconSpool,
    text: "Log yarn at the gate. Stock updates live and warns before it runs low.",
  },
  {
    title: "Make",
    who: "Floor supervisor",
    Icon: IconLoom,
    text: "Assign machines for spinning, weaving and dyeing; log output and every stop with a reason.",
  },
  {
    title: "Check",
    who: "Quality inspector",
    Icon: IconCheck,
    text: "Inspect each roll: pass, rework or reject, with the defect noted.",
  },
  {
    title: "Ship",
    who: "Store manager",
    Icon: IconTruck,
    text: "Pick passed rolls, dispatch and print the invoice in one step. A roll can never ship twice.",
  },
];

export default function HowItWorks() {
  return (
    <section id="how" className="lp-section lp-section-tint">
      <div className="lp-inner">
        <div className="lp-head">
          <h2>From order to truck in five steps</h2>
          <p>Each person sees only their step. The owner sees all of it.</p>
        </div>

        <ol className="lp-steps">
          {STEPS.map(({ title, who, Icon, text }, i) => (
            <li key={title} className="lp-step">
              <span className="lp-step-knot">
                <Icon />
              </span>
              <span className="lp-step-no">{String(i + 1).padStart(2, "0")}</span>
              <h3>{title}</h3>
              <span className="lp-step-who">{who}</span>
              <p>{text}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

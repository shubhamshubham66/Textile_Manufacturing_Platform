// Hero: one-line pitch + Login and Watch demo buttons.
export default function Hero() {
  return (
    <section id="home" className="hero">
      <div className="hero-inner">
        <span className="pill">Everest Textile Mills · Factory OS</span>
        <h1 className="hero-title">
          One platform to run the mill — yarn to invoice, no notebooks.
        </h1>
        <p className="hero-sub">
          Track stock, machines, quality, dispatch and costs in real time. See
          the money lost to idle machines, and know the true cost of every roll.
        </p>
        <div className="hero-cta">
          <a href="/login" className="btn btn-primary btn-lg">
            Login
          </a>
          <a
            href="#how"
            className="btn btn-ghost btn-lg"
            onClick={(e) => {
              e.preventDefault();
              document
                .getElementById("how")
                ?.scrollIntoView({ behavior: "smooth" });
            }}
          >
            ▶ Watch demo
          </a>
        </div>
      </div>
    </section>
  );
}

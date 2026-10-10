// Hero: breadcrumb, headline, short pitch and two buttons on the left; a photo
// of a mill floor on the right, inside a soft grid panel.
function scrollTo(id, e) {
  e.preventDefault();
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
}

export default function Hero() {
  return (
    <section id="home" className="lp-phero">
      <div className="lp-phero-panel">
        <div className="lp-phero-copy">
          <p className="lp-crumbs">
            Everest Textile Mills <span aria-hidden>›</span> Mill operations platform
          </p>

          <h1>One system to run our whole mill</h1>

          <p className="lp-phero-lead">
            Store, floor, quality, dispatch and accounts teams of Everest Textile
            Mills work in one place: yarn stock, machine status, roll checks,
            invoices and wages. Log in with your role to see your work.
          </p>

          <div className="lp-phero-cta">
            <a href="/login" className="lp-pbtn lp-pbtn-solid">
              Login to your account
            </a>
            <a href="#features" className="lp-pbtn lp-pbtn-line" onClick={(e) => scrollTo("features", e)}>
              See what it does
            </a>
          </div>
        </div>

        <figure className="lp-phero-media">
          <img
            src="/images/mill-floor.jpg"
            alt="Spinning machines with rows of white yarn bobbins on a mill floor"
            width="1400"
            height="1050"
            loading="eager"
          />
        </figure>
      </div>
    </section>
  );
}

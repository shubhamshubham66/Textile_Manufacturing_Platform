// Demo strip: one big call to try the app with demo data, as the owner or as a
// buyer. The links log in straight away with that demo account.
export default function CtaStrip() {
  return (
    <section className="lp-cta-strip" aria-labelledby="lp-cta-title">
      <div className="lp-inner lp-cta-inner">
        <div>
          <h2 id="lp-cta-title">See it with real demo data</h2>
          <p>One click logs you in. No sign-up, nothing to install.</p>
        </div>
        <div className="lp-cta-actions">
          <a href="/login?demo=owner" className="lp-btn lp-btn-haldi lp-btn-lg">
            Try as owner
          </a>
          <a href="/login?demo=buyer" className="lp-btn lp-btn-ghost-light lp-btn-lg">
            Try as buyer
          </a>
        </div>
      </div>
    </section>
  );
}

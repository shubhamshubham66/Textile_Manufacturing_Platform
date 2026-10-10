// Public Landing Page Footer with all platform features, full navbar links, contact and Team 41 credit.

const GITHUB_PROFILE = "https://github.com/shubhamshubham66";
const GITHUB_REPO = "https://github.com/shubhamshubham66/Textile_Manufacturing_Platform";
const CONTACT_EMAIL = "kshubham35413@gmail.com";
const CONTACT_PHONE = "+91 8174871687";
const CONTACT_PHONE_RAW = "+918174871687";

const NAV_LINKS = [
  { id: "home", label: "Home", type: "section" },
  { id: "about", label: "About Us", type: "section" },
  { id: "how", label: "How It Works", type: "section" },
  { id: "features", label: "Features & Modules", type: "section" },
  { id: "ai", label: "AI Copilot Help", type: "section" },
  { id: "demo", label: "Interactive Demo", href: "/login", type: "link" },
  { id: "login", label: "Login to Workspace", href: "/login", type: "link" },
];

const PLATFORM_FEATURES = [
  { label: "Production Floor & Machines", target: "features" },
  { label: "Idle Machine Loss in ₹ (USP)", target: "features" },
  { label: "Raw Yarn Stock & Low Alerts", target: "features" },
  { label: "Roll-by-Roll Quality Inspection", target: "features" },
  { label: "Dispatch Desk & Challans", target: "features" },
  { label: "Automated GST Tax Invoices", target: "features" },
  { label: "One-Click Attendance & Wages", target: "features" },
  { label: "Real-Time Month Profit & Loss", target: "features" },
  { label: "Buyer Self-Service Portal", href: "/login" },
  { label: "Textile Mill AI Assistant", target: "ai" },
];

export default function Footer() {
  function scrollToSection(id, e) {
    e.preventDefault();
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  }

  return (
    <footer id="contact" className="lp-footer">
      <div className="lp-inner lp-footer-grid">
        {/* Column 1: Brand & Overview */}
        <div className="lp-footer-brand">
          <a
            href="#home"
            className="lp-brand lp-brand-light"
            onClick={(e) => scrollToSection("home", e)}
          >
            <img
              src="/images/everest-logo-light.png"
              alt="Everest Textile Mills"
              className="lp-brand-logo-img"
            />
            <span className="lp-brand-badge lp-brand-badge-light">Textile Mills</span>
          </a>
          <p className="lp-footer-tagline">
            One unified digital operating system replacing notebooks, paper slips, registers,
            and phone calls across all fabric factory operations.
          </p>

          <div className="lp-footer-actions">
            <a href="/login" className="lp-btn lp-btn-haldi">
              Open Live Demo →
            </a>
            <a href="/login" className="lp-btn lp-btn-outline-light">
              Sign In
            </a>
          </div>
        </div>

        {/* Column 2: All Navbar Buttons */}
        <div className="lp-footer-col">
          <h4>Navigation</h4>
          <ul className="lp-footer-links">
            {NAV_LINKS.map((link) => (
              <li key={link.id}>
                {link.type === "section" ? (
                  <a href={`#${link.id}`} onClick={(e) => scrollToSection(link.id, e)}>
                    {link.label}
                  </a>
                ) : (
                  <a href={link.href}>{link.label}</a>
                )}
              </li>
            ))}
          </ul>
        </div>

        {/* Column 3: Platform Features & Modules */}
        <div className="lp-footer-col">
          <h4>Platform Features</h4>
          <ul className="lp-footer-links">
            {PLATFORM_FEATURES.map((feat) => (
              <li key={feat.label}>
                {feat.target ? (
                  <a
                    href={`#${feat.target}`}
                    onClick={(e) => scrollToSection(feat.target, e)}
                  >
                    {feat.label}
                  </a>
                ) : (
                  <a href={feat.href}>{feat.label}</a>
                )}
              </li>
            ))}
          </ul>
        </div>

        {/* Column 4: Contact & Developer Info */}
        <div className="lp-footer-col">
          <h4>Contact & Developer</h4>
          <ul className="lp-footer-contact-list">
            <li>
              <span className="lp-contact-icon" aria-hidden>
                👤
              </span>
              <div>
                <span className="lp-contact-label">Developer</span>
                <strong className="lp-contact-val">shubhamshubham66</strong>
              </div>
            </li>
            <li>
              <span className="lp-contact-icon" aria-hidden>
                ✉️
              </span>
              <div>
                <span className="lp-contact-label">Email</span>
                <a href={`mailto:${CONTACT_EMAIL}`} className="lp-contact-link">
                  {CONTACT_EMAIL}
                </a>
              </div>
            </li>
            <li>
              <span className="lp-contact-icon" aria-hidden>
                📞
              </span>
              <div>
                <span className="lp-contact-label">Contact / Phone</span>
                <a href={`tel:${CONTACT_PHONE_RAW}`} className="lp-contact-link">
                  {CONTACT_PHONE}
                </a>
              </div>
            </li>
            <li>
              <span className="lp-contact-icon" aria-hidden>
                🐙
              </span>
              <div>
                <span className="lp-contact-label">GitHub Profile</span>
                <a
                  href={GITHUB_PROFILE}
                  target="_blank"
                  rel="noreferrer"
                  className="lp-contact-link"
                >
                  github.com/shubhamshubham66
                </a>
              </div>
            </li>
            <li>
              <span className="lp-contact-icon" aria-hidden>
                📂
              </span>
              <div>
                <span className="lp-contact-label">Source Repository</span>
                <a
                  href={GITHUB_REPO}
                  target="_blank"
                  rel="noreferrer"
                  className="lp-contact-link"
                >
                  Textile_Manufacturing_Platform
                </a>
              </div>
            </li>
          </ul>
        </div>
      </div>

      {/* Footer Bottom Strip */}
      <div className="lp-inner lp-footer-bottom">
        <div className="lp-footer-copy">
          © {new Date().getFullYear()} Everest Textile Mills · All rights reserved.
        </div>

        <div className="lp-footer-team-credit">
          <span className="lp-team-badge">
            <span className="lp-team-heart">❤️</span> Made by <strong>Team Number 41</strong>
          </span>
        </div>
      </div>
    </footer>
  );
}

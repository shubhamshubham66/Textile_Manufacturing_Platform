import { BrandMark } from "./landing/Icons.jsx";

// Footer: contact, demo logins, GitHub.
const GITHUB_URL = "https://github.com/shubhamshubham66/Textile_Manufacturing_Platform";

const ROLES = [
  ["Owner", "owner@everest.test"],
  ["Store manager", "store@everest.test"],
  ["Floor supervisor", "floor@everest.test"],
  ["Quality inspector", "quality@everest.test"],
  ["Accountant", "accounts@everest.test"],
  ["Buyer", "buyer@everest.test"],
];

export default function Footer() {
  return (
    <footer id="contact" className="lp-footer">
      <div className="lp-inner lp-footer-grid">
        <div className="lp-footer-brand">
          <a href="#home" className="lp-brand lp-brand-light">
            <BrandMark />
            <span>
              Everest <em>Textile Mills</em>
            </span>
          </a>
          <p>Yarn, floor, quality, dispatch and the books, in one place.</p>
          <a href="/login" className="lp-btn lp-btn-haldi">
            Open the demo
          </a>
        </div>

        <div>
          <h4>Demo logins</h4>
          <ul className="lp-roles">
            {ROLES.map(([role, email]) => (
              <li key={email}>
                <span>{role}</span>
                <code>{email}</code>
              </li>
            ))}
          </ul>
          <p className="lp-footer-small">
            Password is the first word of the email + 123, e.g. owner123. Or use
            one-click login on the login page.
          </p>
        </div>

        <div>
          <h4>Contact</h4>
          <ul className="lp-footer-links">
            <li>
              <a href="mailto:hello@everest-textile.test">hello@everest-textile.test</a>
            </li>
            <li>
              <a href="tel:+911234567890">+91 12345 67890</a>
            </li>
          </ul>
          <h4>Project</h4>
          <ul className="lp-footer-links">
            <li>
              <a href={GITHUB_URL} target="_blank" rel="noreferrer">
                GitHub repository
              </a>
            </li>
          </ul>
        </div>
      </div>
      <div className="lp-inner lp-footer-bottom">
        © {new Date().getFullYear()} Everest Textile Mills · hackathon demo with sample data
      </div>
    </footer>
  );
}

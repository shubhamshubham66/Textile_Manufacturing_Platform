// Footer: Contact, Demo login, GitHub.
const GITHUB_URL =
  "https://github.com/shubhamshubham66/Textile_Manufacturing_Platform";

export default function Footer() {
  return (
    <footer id="contact" className="footer">
      <div className="footer-inner">
        <div className="footer-col">
          <div className="brand">
            <span className="brand-mark">ET</span>
            <span className="brand-text">Everest Textile Mills</span>
          </div>
          <p className="muted">
            One platform for yarn, production, quality, dispatch and costs.
          </p>
        </div>

        <div className="footer-col">
          <h4>Contact</h4>
          <ul className="footer-links">
            <li>
              <a href="mailto:hello@everest-textile.test">
                hello@everest-textile.test
              </a>
            </li>
            <li>
              <a href="tel:+911234567890">+91 12345 67890</a>
            </li>
          </ul>
        </div>

        <div className="footer-col">
          <h4>Demo login</h4>
          <ul className="footer-links">
            <li>
              <a href="/login">Try as owner / buyer</a>
            </li>
          </ul>
        </div>

        <div className="footer-col">
          <h4>Project</h4>
          <ul className="footer-links">
            <li>
              <a href={GITHUB_URL} target="_blank" rel="noreferrer">
                GitHub ↗
              </a>
            </li>
          </ul>
        </div>
      </div>
      <div className="footer-bottom muted">
        © {new Date().getFullYear()} Everest Textile Mills — hackathon demo.
      </div>
    </footer>
  );
}

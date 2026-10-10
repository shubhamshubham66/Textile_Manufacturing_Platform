import { useEffect, useState } from "react";
import { BrandMark } from "./landing/Icons.jsx";

// Public navbar.
// Left: logo. Centre: section links (smooth scroll). Right: Demo + Login (Login
// is the primary button). On mobile the links collapse into a menu while the
// logo and Login stay visible.
const LINKS = [
  { id: "home", label: "Home" },
  { id: "about", label: "About" },
  { id: "how", label: "How it works" },
  { id: "features", label: "Features" },
  { id: "ai", label: "AI help" },
];

export default function Navbar() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  function go(id, e) {
    e.preventDefault();
    setOpen(false);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  }

  return (
    <header className={`lp-nav ${scrolled ? "is-scrolled" : ""}`}>
      <div className="lp-nav-inner">
        <a href="#home" className="lp-brand" onClick={(e) => go("home", e)}>
          <BrandMark />
          <span>
            Everest <em>Textile Mills</em>
          </span>
        </a>

        <nav className={`lp-nav-links ${open ? "is-open" : ""}`} aria-label="Sections">
          {LINKS.map((l) => (
            <a key={l.id} href={`#${l.id}`} onClick={(e) => go(l.id, e)}>
              {l.label}
            </a>
          ))}
          <a href="/login" className="lp-btn lp-btn-quiet lp-only-mobile">
            Try the demo
          </a>
        </nav>

        <div className="lp-nav-actions">
          <a href="/login" className="lp-btn lp-btn-quiet lp-only-desktop">
            Demo
          </a>
          <a href="/login" className="lp-btn lp-btn-primary">
            Login
          </a>
          <button
            className="lp-menu"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            <span />
            <span />
          </button>
        </div>
      </div>
    </header>
  );
}

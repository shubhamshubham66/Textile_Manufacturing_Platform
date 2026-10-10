import { useState } from "react";

// Public navbar.
// Left: logo. Center: section links (scroll to section). Right: Demo + Login
// (Login is the primary button). On mobile the center links collapse into a
// hamburger menu while the logo and Login stay visible.
const LINKS = [
  { id: "home", label: "Home" },
  { id: "about", label: "About" },
  { id: "how", label: "How it works" },
  { id: "features", label: "Features" },
  { id: "ai", label: "AI help" },
];

export default function Navbar() {
  const [open, setOpen] = useState(false);

  function go(id, e) {
    e.preventDefault();
    setOpen(false);
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <header className="navbar">
      <div className="nav-inner">
        {/* Left: logo */}
        <a href="#home" className="brand" onClick={(e) => go("home", e)}>
          <span className="brand-mark">ET</span>
          <span className="brand-text">Everest Textile Mills</span>
        </a>

        {/* Center: links (hidden on mobile unless menu open) */}
        <nav className={`nav-links ${open ? "open" : ""}`}>
          {LINKS.map((l) => (
            <a key={l.id} href={`#${l.id}`} onClick={(e) => go(l.id, e)}>
              {l.label}
            </a>
          ))}
          {/* Demo + Login also appear inside the mobile dropdown */}
          <a
            href="#how"
            className="btn btn-ghost nav-mobile-only"
            onClick={(e) => go("how", e)}
          >
            Demo
          </a>
          <a href="/login" className="btn btn-primary nav-mobile-only">
            Login
          </a>
        </nav>

        {/* Right: Demo + Login (desktop) + hamburger (mobile) */}
        <div className="nav-actions">
          <a
            href="#how"
            className="btn btn-ghost nav-desktop-only"
            onClick={(e) => go("how", e)}
          >
            Demo
          </a>
          <a href="/login" className="btn btn-primary">
            Login
          </a>
          <button
            className="hamburger"
            aria-label="Toggle menu"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            <span />
            <span />
            <span />
          </button>
        </div>
      </div>
    </header>
  );
}

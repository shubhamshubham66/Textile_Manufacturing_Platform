import { useEffect, useState, useRef } from "react";
import { BrandMark } from "./landing/Icons.jsx";

// Comprehensive navigation definitions with all platform features inside each button dropdown.
const NAV_DATA = [
  {
    id: "home",
    label: "Home",
    badge: "Live",
    tagline: "Factory Overview & Real-Time Status",
    items: [
      {
        id: "overview",
        title: "Factory Birds-Eye Overview",
        desc: "Complete operational status of Everest Textile Mills under one roof",
        target: "home",
        badge: "Overview",
        type: "section",
        icon: "loom",
      },
      {
        id: "floor-live",
        title: "Live Production Floor Board",
        desc: "Real-time running status of spinning, weaving & dyeing machine lines",
        target: "home",
        badge: "Live Status",
        type: "section",
        icon: "eye",
      },
      {
        id: "idle-loss",
        title: "Idle Machine Loss in ₹",
        desc: "Calculate live rupee loss from machine downtime & stoppage reasons",
        target: "features",
        badge: "USP",
        type: "section",
        icon: "chart",
      },
      {
        id: "portals",
        title: "8 Role-Based Workspaces",
        desc: "Dedicated views for Owner, Floor, Store, QC, Workers & Buyers",
        href: "/login",
        badge: "8 Roles",
        type: "link",
        icon: "order",
      },
      {
        id: "demo",
        title: "Try 1-Click Interactive Demo",
        desc: "Instant access with preloaded mill orders, machines & stock",
        href: "/login",
        badge: "Try Demo",
        type: "link",
        icon: "arrow",
      },
    ],
  },
  {
    id: "about",
    label: "About",
    badge: "Mill Story",
    tagline: "Zero-Paper Mill Transformation",
    items: [
      {
        id: "heritage",
        title: "Mill Heritage & Operations",
        desc: "Spinning, weaving and dyeing cotton fabric under one unified roof",
        target: "about",
        badge: "Background",
        type: "section",
        icon: "loom",
      },
      {
        id: "problems",
        title: "5 Core Problems Solved",
        desc: "Eliminating paper registers, floor-walking, lost rolls & phone calls",
        target: "about",
        badge: "Problems",
        type: "section",
        icon: "check",
      },
      {
        id: "paperless",
        title: "100% Digital Factory Ledger",
        desc: "One single source of truth across all 6 factory departments",
        target: "about",
        badge: "Solution",
        type: "section",
        icon: "roll",
      },
      {
        id: "traceability",
        title: "End-to-End Roll Traceability",
        desc: "Trace every finished fabric roll back to its yarn cone & machine",
        target: "about",
        badge: "Audit Trail",
        type: "section",
        icon: "spool",
      },
      {
        id: "architecture",
        title: "High-Performance Cloud Stack",
        desc: "Built with FastAPI, React, SQLite/PostgreSQL and Dify AI",
        target: "about",
        badge: "Stack",
        type: "section",
        icon: "chart",
      },
    ],
  },
  {
    id: "how",
    label: "How it works",
    badge: "6 Steps",
    tagline: "From Order to Truck in 6 Steps",
    items: [
      {
        id: "step-order",
        step: "01",
        title: "Order Intake & Yarn Check",
        desc: "Enter fabric specs; the system verifies yarn sufficiency instantly",
        target: "how",
        badge: "Owner Desk",
        type: "section",
        icon: "order",
      },
      {
        id: "step-yarn",
        step: "02",
        title: "Yarn Gate Intake & Stock",
        desc: "Barcode gate receipts, auto-updating stock & low-yarn alerts",
        target: "how",
        badge: "Store Mgr",
        type: "section",
        icon: "spool",
      },
      {
        id: "step-prod",
        step: "03",
        title: "Machine Routing & Output",
        desc: "Assign spinning, weaving & dyeing machines; log downtime reasons",
        target: "how",
        badge: "Supervisor",
        type: "section",
        icon: "loom",
      },
      {
        id: "step-qc",
        step: "04",
        title: "Roll-by-Roll Inspection",
        desc: "Inspect rolls: Pass, Rework, or Reject with defect categorization",
        target: "how",
        badge: "Inspector",
        type: "section",
        icon: "check",
      },
      {
        id: "step-dispatch",
        step: "05",
        title: "Dispatch & Auto-Invoicing",
        desc: "Pick passed rolls, prevent double dispatch, auto-generate GST invoice",
        target: "how",
        badge: "Dispatch",
        type: "section",
        icon: "truck",
      },
      {
        id: "step-finance",
        step: "06",
        title: "Financial Settlement & P&L",
        desc: "Reconcile raw materials, worker wages, machine cost & month P&L",
        target: "features",
        badge: "Finance",
        type: "section",
        icon: "chart",
      },
    ],
  },
  {
    id: "features",
    label: "Features",
    badge: "All Modules",
    tagline: "Comprehensive Textile Manufacturing Suite",
    isMega: true,
    categories: [
      {
        title: "Production & Floor Control",
        badge: "Floor",
        items: [
          {
            title: "Live Machine Board",
            desc: "Status, active order, speed & today's metres produced",
            target: "features",
            badge: "Live",
            icon: "eye",
          },
          {
            title: "Idle Machine Loss ₹",
            desc: "Hourly cost × downtime hours = exact rupee loss metric",
            target: "features",
            badge: "USP",
            icon: "chart",
          },
          {
            title: "Spinning, Weaving & Dyeing",
            desc: "Multi-stage manufacturing flow with machine routing",
            target: "features",
            badge: "Stages",
            icon: "loom",
          },
          {
            title: "Worker Floor Assignments",
            desc: "Assign floor operators to specific looms and frames",
            target: "features",
            badge: "Staff",
            icon: "order",
          },
        ],
      },
      {
        title: "Yarn & Raw Inventory",
        badge: "Warehouse",
        items: [
          {
            title: "Raw Yarn Stock Ledger",
            desc: "Live stock counts by count, blend, color & warehouse shelf",
            target: "features",
            badge: "Stock",
            icon: "spool",
          },
          {
            title: "Low-Stock Early Warning",
            desc: "Proactive alerts before yarn runs out on confirmed orders",
            target: "features",
            badge: "Alerts",
            icon: "bell",
          },
          {
            title: "Gate Material Receiving",
            desc: "Scan and log supplier yarn deliveries with auto stock update",
            target: "features",
            badge: "Intake",
            icon: "truck",
          },
          {
            title: "Purchase Requisitions",
            desc: "Raise and approve yarn purchase orders with suppliers",
            target: "features",
            badge: "PO",
            icon: "order",
          },
        ],
      },
      {
        title: "Quality & Dispatch",
        badge: "QC & Logistics",
        items: [
          {
            title: "Roll-by-Roll Inspection",
            desc: "Grade rolls: Pass, Rework, Reject with defect logging",
            target: "features",
            badge: "QC",
            icon: "check",
          },
          {
            title: "Defect Analysis Taxonomy",
            desc: "Track holes, colour mismatches, uneven weave & tension",
            target: "features",
            badge: "Defects",
            icon: "roll",
          },
          {
            title: "Dispatch Pick Validation",
            desc: "Pick verified rolls with zero risk of double shipping",
            target: "features",
            badge: "Dispatch",
            icon: "truck",
          },
          {
            title: "Instant Invoices & Challans",
            desc: "One-click GST tax invoices with roll list and PDF download",
            target: "features",
            badge: "Invoice",
            icon: "order",
          },
        ],
      },
      {
        title: "Finance, HR & Portals",
        badge: "Business",
        items: [
          {
            title: "One-Click Attendance",
            desc: "Digital daily roll call replacing physical paper registers",
            target: "features",
            badge: "HR",
            icon: "calendar",
          },
          {
            title: "Automated Wage Engine",
            desc: "Days worked × daily rate + overtime wage auto-calculation",
            target: "features",
            badge: "Wages",
            icon: "chart",
          },
          {
            title: "True Month Profit & Loss",
            desc: "Live P&L reconciling yarn bills, wages & machine cost",
            target: "features",
            badge: "P&L",
            icon: "chart",
          },
          {
            title: "Buyer Self-Service Portal",
            desc: "Buyers view live order stages, delivery ETAs & invoices",
            href: "/login",
            badge: "Portal",
            icon: "eye",
          },
        ],
      },
    ],
  },
  {
    id: "ai",
    label: "AI help",
    badge: "Dify AI",
    tagline: "Textile Mill Copilot Assistant",
    items: [
      {
        id: "ai-copilot",
        title: "Textile Mill AI Copilot",
        desc: "Domain-specific AI trained on mill orders, machines & inventory",
        target: "ai",
        badge: "Copilot",
        type: "section",
        icon: "sparkle",
      },
      {
        id: "ai-queries",
        title: "Natural Language Floor Search",
        desc: "'Which machine has Order #104?' or 'How much 30s combed yarn left?'",
        target: "ai",
        badge: "NLP Search",
        type: "section",
        icon: "order",
      },
      {
        id: "ai-bottlenecks",
        title: "Downtime & Bottleneck Insights",
        desc: "Detect recurring breakdown patterns and preventative actions",
        target: "ai",
        badge: "Analytics",
        type: "section",
        icon: "chart",
      },
      {
        id: "ai-chat-open",
        title: "Launch Live AI Assistant",
        desc: "Open the floating interactive chat assistant right here",
        action: "open-chat",
        badge: "Chat Now",
        type: "action",
        icon: "chat",
      },
    ],
  },
];

// Clean stroke icons helper for dropdown menus
function NavIcon({ name, className = "" }) {
  const props = {
    width: 18,
    height: 18,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    className: `lp-sub-icon ${className}`,
    "aria-hidden": true,
  };

  switch (name) {
    case "loom":
      return (
        <svg {...props}>
          <rect x="3" y="5" width="18" height="14" rx="2" />
          <path d="M7 5v14M11 5v14M15 5v14M3 10h18M3 14h18" />
        </svg>
      );
    case "spool":
      return (
        <svg {...props}>
          <path d="M6 4h12M6 20h12" />
          <path d="M8 4v16M16 4v16" />
          <path d="M8 8l8 2M8 12l8 2M8 16l8 2" />
        </svg>
      );
    case "roll":
      return (
        <svg {...props}>
          <ellipse cx="7" cy="12" rx="3" ry="6" />
          <path d="M7 6h11a3 6 0 0 1 0 12H7" />
          <circle cx="7" cy="12" r="1" />
        </svg>
      );
    case "truck":
      return (
        <svg {...props}>
          <path d="M3 6h11v10H3zM14 10h4l3 3v3h-7" />
          <circle cx="7" cy="18" r="2" />
          <circle cx="17" cy="18" r="2" />
        </svg>
      );
    case "order":
      return (
        <svg {...props}>
          <path d="M6 3h9l3 3v15H6z" />
          <path d="M9 10h6M9 14h6M9 18h3" />
        </svg>
      );
    case "check":
      return (
        <svg {...props}>
          <circle cx="11" cy="11" r="7" />
          <path d="M8 11l2 2 4-4M16 16l5 5" />
        </svg>
      );
    case "chart":
      return (
        <svg {...props}>
          <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
        </svg>
      );
    case "eye":
      return (
        <svg {...props}>
          <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      );
    case "bell":
      return (
        <svg {...props}>
          <path d="M6 16V11a6 6 0 1 1 12 0v5l2 2H4z" />
          <path d="M10 20a2 2 0 0 0 4 0" />
        </svg>
      );
    case "calendar":
      return (
        <svg {...props}>
          <rect x="3" y="4" width="18" height="18" rx="2" />
          <path d="M16 2v4M8 2v4M3 10h18" />
        </svg>
      );
    case "sparkle":
      return (
        <svg {...props}>
          <path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.2 2.2M16.2 16.2l2.2 2.2M5.6 18.4l2.2-2.2M16.2 7.8l2.2-2.2" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      );
    case "chat":
      return (
        <svg {...props}>
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      );
    case "arrow":
    default:
      return (
        <svg {...props}>
          <path d="M5 12h14M12 5l7 7-7 7" />
        </svg>
      );
  }
}

export default function Navbar() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [activeDropdown, setActiveDropdown] = useState(null);
  const [mobileExpanded, setMobileExpanded] = useState({});
  const closeTimerRef = useRef(null);
  const navRef = useRef(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Close dropdown on outside click or escape key
  useEffect(() => {
    function handleClickOutside(e) {
      if (navRef.current && !navRef.current.contains(e.target)) {
        setActiveDropdown(null);
      }
    }
    function handleKeyDown(e) {
      if (e.key === "Escape") {
        setActiveDropdown(null);
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  function handleTriggerMouseEnter(id) {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
    setActiveDropdown(id);
  }

  function handleTriggerMouseLeave() {
    closeTimerRef.current = setTimeout(() => {
      setActiveDropdown(null);
    }, 180);
  }

  function handleDropdownMouseEnter() {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  }

  function handleDropdownMouseLeave() {
    closeTimerRef.current = setTimeout(() => {
      setActiveDropdown(null);
    }, 180);
  }

  function toggleDropdown(id, e) {
    e.preventDefault();
    e.stopPropagation();
    setActiveDropdown((prev) => (prev === id ? null : id));
  }

  function toggleMobileExpand(id, e) {
    e.preventDefault();
    e.stopPropagation();
    setMobileExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  function handleNavClick(sectionId, e) {
    e.preventDefault();
    setActiveDropdown(null);
    setOpen(false);
    document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth" });
  }

  function handleItemClick(item, e) {
    if (item.action === "open-chat") {
      e.preventDefault();
      setActiveDropdown(null);
      setOpen(false);
      window.dispatchEvent(new Event("etm:open-chat"));
      return;
    }

    if (item.target) {
      e.preventDefault();
      setActiveDropdown(null);
      setOpen(false);
      const targetElem = document.getElementById(item.target);
      if (targetElem) {
        targetElem.scrollIntoView({ behavior: "smooth" });
      }
      return;
    }

    if (item.href) {
      setActiveDropdown(null);
      setOpen(false);
      // Let standard link anchor / navigation run
    }
  }

  return (
    <header className={`lp-nav ${scrolled ? "is-scrolled" : ""}`} ref={navRef}>
      <div className="lp-nav-inner">
        {/* Brand logo */}
        <a href="#home" className="lp-brand" onClick={(e) => handleNavClick("home", e)}>
          <img
            src="/images/everest-logo.png"
            alt="Everest Textile Mills"
            className="lp-brand-logo-img"
          />
          <span className="lp-brand-badge">Textile Mills</span>
        </a>

        {/* Desktop & Mobile Navigation Links with Dropdowns */}
        <nav className={`lp-nav-links ${open ? "is-open" : ""}`} aria-label="Main Navigation">
          {NAV_DATA.map((nav) => {
            const isDropdownActive = activeDropdown === nav.id;
            const isMobileOpen = Boolean(mobileExpanded[nav.id]);

            return (
              <div
                key={nav.id}
                className={`lp-nav-item ${isDropdownActive ? "is-active" : ""}`}
                onMouseEnter={() => handleTriggerMouseEnter(nav.id)}
                onMouseLeave={handleTriggerMouseLeave}
              >
                {/* Main Link & Dropdown Trigger */}
                <div className="lp-nav-trigger-row">
                  <a
                    href={`#${nav.id}`}
                    className="lp-nav-link"
                    onClick={(e) => handleNavClick(nav.id, e)}
                  >
                    <span>{nav.label}</span>
                  </a>

                  {/* Dropdown toggle button for clicks */}
                  <button
                    type="button"
                    className="lp-nav-caret-btn"
                    aria-label={`Toggle ${nav.label} features menu`}
                    aria-expanded={isDropdownActive}
                    onClick={(e) => {
                      if (window.innerWidth <= 860) {
                        toggleMobileExpand(nav.id, e);
                      } else {
                        toggleDropdown(nav.id, e);
                      }
                    }}
                  >
                    <svg
                      width="12"
                      height="12"
                      viewBox="0 0 12 12"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className={`lp-caret-icon ${
                        (isDropdownActive || isMobileOpen) ? "is-open" : ""
                      }`}
                      aria-hidden="true"
                    >
                      <path d="M2.5 4.5l3.5 3.5 3.5-3.5" />
                    </svg>
                  </button>
                </div>

                {/* DESKTOP DROPDOWN MENU */}
                {isDropdownActive && (
                  <div
                    className={`lp-dropdown ${nav.isMega ? "lp-dropdown-mega" : ""}`}
                    onMouseEnter={handleDropdownMouseEnter}
                    onMouseLeave={handleDropdownMouseLeave}
                    role="menu"
                  >
                    {/* Header info strip */}
                    <div className="lp-dropdown-head">
                      <span className="lp-dropdown-tagline">{nav.tagline}</span>
                      <span className="lp-dropdown-badge">{nav.badge}</span>
                    </div>

                    {/* Standard Dropdown layout (Home, About, How it works, AI) */}
                    {!nav.isMega && (
                      <div className="lp-dropdown-list">
                        {nav.items?.map((item) => (
                          <a
                            key={item.id}
                            href={item.href || `#${item.target || nav.id}`}
                            className="lp-dropdown-card"
                            onClick={(e) => handleItemClick(item, e)}
                            role="menuitem"
                          >
                            <span className="lp-card-icon-box">
                              <NavIcon name={item.icon} />
                            </span>
                            <div className="lp-card-content">
                              <div className="lp-card-top">
                                {item.step && <span className="lp-card-step">{item.step}</span>}
                                <strong className="lp-card-title">{item.title}</strong>
                                {item.badge && <span className="lp-card-pill">{item.badge}</span>}
                              </div>
                              <p className="lp-card-desc">{item.desc}</p>
                            </div>
                            <span className="lp-card-arrow" aria-hidden>
                              →
                            </span>
                          </a>
                        ))}
                      </div>
                    )}

                    {/* Mega Dropdown layout for Features */}
                    {nav.isMega && (
                      <div className="lp-mega-body">
                        <div className="lp-mega-grid">
                          {nav.categories?.map((cat) => (
                            <div key={cat.title} className="lp-mega-col">
                              <div className="lp-col-header">
                                <h4>{cat.title}</h4>
                                <span className="lp-col-badge">{cat.badge}</span>
                              </div>
                              <div className="lp-col-items">
                                {cat.items.map((item) => (
                                  <a
                                    key={item.title}
                                    href={item.href || `#${item.target || "features"}`}
                                    className="lp-mega-item"
                                    onClick={(e) => handleItemClick(item, e)}
                                    role="menuitem"
                                  >
                                    <span className="lp-mega-icon-box">
                                      <NavIcon name={item.icon} />
                                    </span>
                                    <div className="lp-mega-content">
                                      <div className="lp-mega-title-row">
                                        <strong className="lp-mega-title">{item.title}</strong>
                                        {item.badge && (
                                          <span className="lp-card-pill">{item.badge}</span>
                                        )}
                                      </div>
                                      <p className="lp-mega-desc">{item.desc}</p>
                                    </div>
                                  </a>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>

                        {/* Mega Menu Footer Banner */}
                        <div className="lp-mega-footer">
                          <div className="lp-mega-footer-left">
                            <span className="lp-mega-pulse-dot" />
                            <span>
                              All features are active and connected with role-based live updates.
                            </span>
                          </div>
                          <a href="/login" className="lp-mega-cta-btn">
                            Explore Live System Demo →
                          </a>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* MOBILE ACCORDION (Inside hamburger menu) */}
                <div className={`lp-mob-accordion ${isMobileOpen ? "is-expanded" : ""}`}>
                  {!nav.isMega ? (
                    <div className="lp-mob-sublist">
                      {nav.items?.map((item) => (
                        <a
                          key={item.id}
                          href={item.href || `#${item.target || nav.id}`}
                          className="lp-mob-item"
                          onClick={(e) => handleItemClick(item, e)}
                        >
                          <NavIcon name={item.icon} />
                          <div className="lp-mob-item-text">
                            <div className="lp-mob-item-title-row">
                              <strong>{item.title}</strong>
                              {item.badge && <span className="lp-card-pill">{item.badge}</span>}
                            </div>
                            <span className="lp-mob-item-desc">{item.desc}</span>
                          </div>
                        </a>
                      ))}
                    </div>
                  ) : (
                    <div className="lp-mob-sublist">
                      {nav.categories?.map((cat) => (
                        <div key={cat.title} className="lp-mob-cat-group">
                          <div className="lp-mob-cat-title">{cat.title}</div>
                          {cat.items.map((item) => (
                            <a
                              key={item.title}
                              href={item.href || `#${item.target || "features"}`}
                              className="lp-mob-item"
                              onClick={(e) => handleItemClick(item, e)}
                            >
                              <NavIcon name={item.icon} />
                              <div className="lp-mob-item-text">
                                <div className="lp-mob-item-title-row">
                                  <strong>{item.title}</strong>
                                  {item.badge && <span className="lp-card-pill">{item.badge}</span>}
                                </div>
                                <span className="lp-mob-item-desc">{item.desc}</span>
                              </div>
                            </a>
                          ))}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {/* Mobile action buttons */}
          <div className="lp-mobile-nav-actions">
            <a href="/login" className="lp-btn lp-btn-quiet lp-only-mobile">
              Try the demo
            </a>
            <a href="/login" className="lp-btn lp-btn-primary lp-only-mobile">
              Login to Workspace
            </a>
          </div>
        </nav>

        {/* Right side CTA actions */}
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

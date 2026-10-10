import { useState } from "react";
import { useAuth } from "../auth/AuthContext.jsx";
import Orders from "./app/Orders.jsx";
import YarnStore from "./app/YarnStore.jsx";
import Stock from "./app/Stock.jsx";
import Purchase from "./app/Purchase.jsx";
import Machines from "./app/Machines.jsx";
import Production from "./app/Production.jsx";
import Quality from "./app/Quality.jsx";
import Dispatch from "./app/Dispatch.jsx";
import Payments from "./app/Payments.jsx";
import Attendance from "./app/Attendance.jsx";
import Wages from "./app/Wages.jsx";
import Reports from "./app/Reports.jsx";
import Dashboard from "./app/Dashboard.jsx";
import MyOrders from "./app/MyOrders.jsx";
import Invoices from "./app/Invoices.jsx";
import ChatBubble from "../components/ChatBubble.jsx";

// Resource key -> built module page. Resources not listed here fall back to a
// clearly-labelled prototype placeholder (built in later phases).
const PAGES = {
  orders: Orders,
  yarn: YarnStore,
  stock: Stock,
  purchase: Purchase,
  machines: Machines,
  production: Production,
  quality: Quality,
  rolls: Quality,
  dispatch: Dispatch,
  payments: Payments,
  attendance: Attendance,
  wages: Wages,
  reports: Reports,
  dashboard: Dashboard,
  my_orders: MyOrders,
  invoices: Invoices,
};

// Role label lookup for display (keys match backend role names).
const ROLE_LABELS = {
  owner: "Owner",
  store_manager: "Store manager",
  floor_supervisor: "Floor supervisor",
  quality_inspector: "Quality inspector",
  accountant: "Accountant",
  buyer: "Buyer",
};

// The app shell after login. The sidebar is built from the `menu` returned by the
// backend for the user's role — ONE config, no per-role UI code. The content area
// is a placeholder; real module pages arrive in later phases.
export default function AppShell() {
  const { user, menu, logout } = useAuth();
  const [active, setActive] = useState(menu[0]?.path || "");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);

  if (!user) return null; // guarded by App, but be safe

  const activeItem = menu.find((m) => m.path === active) || menu[0];
  const initials = user.name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div className="shell">
      {/* Sidebar */}
      <aside className={`shell-side ${sidebarOpen ? "open" : ""}`}>
        <div className="shell-brand">
          <span className="brand-mark">ET</span>
          <span className="brand-text">Everest</span>
        </div>
        <nav className="shell-menu">
          {menu.map((item) => (
            <button
              key={item.path}
              className={`shell-link ${active === item.path ? "active" : ""}`}
              onClick={() => {
                setActive(item.path);
                setSidebarOpen(false);
              }}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </aside>

      {/* Main column */}
      <div className="shell-main">
        <header className="shell-top">
          <button
            className="hamburger shell-hamburger"
            aria-label="Toggle menu"
            onClick={() => setSidebarOpen((v) => !v)}
          >
            <span />
            <span />
            <span />
          </button>

          <div className="shell-top-title">
            {activeItem?.label || "Dashboard"}
          </div>

          <div className="shell-top-actions">
            {/* Notifications bell */}
            <div className="notif-wrap">
              <button
                className="icon-btn"
                title="Notifications"
                aria-label="Notifications"
                aria-expanded={notifOpen}
                onClick={() => setNotifOpen((v) => !v)}
              >
                🔔
              </button>
              {notifOpen && (
                <div
                  className="notif-popover"
                  role="dialog"
                  aria-label="Notifications"
                >
                  <div className="notif-head">Notifications</div>
                  <div className="notif-empty muted">
                    You're all caught up — no new notifications.
                  </div>
                </div>
              )}
            </div>

            {/* Profile: name + role */}
            <div className="profile">
              <span className="avatar">{initials}</span>
              <span className="profile-meta">
                <strong>{user.name}</strong>
                <small className="muted">
                  {ROLE_LABELS[user.role] || user.role}
                </small>
              </span>
            </div>

            <button className="btn btn-ghost btn-sm" onClick={logout}>
              Logout
            </button>
          </div>
        </header>

        <main className="shell-content">
          {(() => {
            const Page = PAGES[activeItem?.resource];
            if (Page) return <Page />;
            return (
              <div className="placeholder-card">
                <h2>{activeItem?.label}</h2>
                <p className="muted">
                  This is the <strong>{activeItem?.label}</strong> area for the{" "}
                  <strong>{ROLE_LABELS[user.role] || user.role}</strong> role.
                </p>
                <p className="muted">
                  Prototype placeholder — this module is built in a later phase.
                </p>
                <span className="badge loading">Prototype</span>
              </div>
            );
          })()}
        </main>
      </div>

      {sidebarOpen && (
        <div className="shell-overlay" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Floating chat bubble on every logged-in page too (mount point). */}
      <ChatBubble />
    </div>
  );
}

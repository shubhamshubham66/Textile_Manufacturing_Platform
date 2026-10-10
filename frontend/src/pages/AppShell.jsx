import { useState, useEffect } from "react";
import { useAuth } from "../auth/AuthContext.jsx";
import Orders from "./app/Orders.jsx";
import {
  PurchaseDashboard,
  SuppliersDesk,
  RawInventory,
} from "./app/purchase/PurchaseMain.jsx";
import {
  PurchaseRequests,
  PurchaseOrders,
  MaterialReceiving,
} from "./app/purchase/PurchaseFlow.jsx";
import {
  LowStockAlerts,
  MaterialRequirements,
  PurchaseReports,
  PurchaseNotifications,
} from "./app/purchase/PurchaseInsight.jsx";
import Machines from "./app/Machines.jsx";
import Production from "./app/Production.jsx";
import Quality from "./app/Quality.jsx";
import Dispatch from "./app/Dispatch.jsx";
import Payments from "./app/Payments.jsx";
import SuperOrders from "./app/super/SuperOrders.jsx";
import SuperDashboard from "./app/super/SuperDashboard.jsx";
import SuperManagers from "./app/super/SuperManagers.jsx";
import SuperWorkers from "./app/super/SuperWorkers.jsx";
import SuperTasks from "./app/super/SuperTasks.jsx";
import {
  SuperProduction,
  SuperInventory,
  SuperQuality,
  SuperDispatch,
} from "./app/super/SuperMonitors.jsx";
import {
  SuperAttendance,
  SuperAccounts,
  SuperAlerts,
  SuperActivity,
  SuperSettings,
} from "./app/super/SuperAdmin.jsx";
import MyTasks from "./app/MyTasks.jsx";
import { MenuIcon } from "../components/super/icons.jsx";
import TopSearch from "../components/super/TopSearch.jsx";
import "../super.css";
import Attendance from "./app/Attendance.jsx";
import Wages from "./app/Wages.jsx";
import Reports from "./app/Reports.jsx";
import Dashboard from "./app/Dashboard.jsx";
import MasterData from "./app/MasterData.jsx";
import MyOrders from "./app/MyOrders.jsx";
import Invoices from "./app/Invoices.jsx";
import Team from "./app/Team.jsx";
import ProdDashboard from "./app/prod/ProdDashboard.jsx";
import {
  ProdOrders,
  ProdPlanning,
  ProdStages,
} from "./app/prod/ProdOrders.jsx";
import {
  ProdMachines,
  ProdWorkers,
  ProdMonitoring,
} from "./app/prod/ProdFloor.jsx";
import {
  ProdMaterials,
  ProdQc,
  ProdReports,
  ProdNotifications,
  ProdActivity,
} from "./app/prod/ProdOps.jsx";
import SalesDashboard from "./app/sales/SalesDashboard.jsx";
import {
  SalesBuyerOrders,
  SalesBuyers,
  SalesTracking,
  SalesStock,
} from "./app/sales/SalesOrders.jsx";
import {
  SalesPlanning,
  SalesChallan,
  SalesHistory,
  SalesDelivery,
} from "./app/sales/SalesDispatch.jsx";
import {
  SalesInvoices,
  SalesNotifications,
  SalesReports,
  SalesActivity,
} from "./app/sales/SalesOps.jsx";
import AccountsDashboard from "./app/accounts/AccountsDashboard.jsx";
import {
  AccountsInvoices,
  AccountsOvertime,
  AccountsProductionExpenses,
  AccountsExpenses,
  AccountsReports,
  AccountsNotifications,
  AccountsActivity,
} from "./app/accounts/AccountsPages.jsx";
import ChatBubble from "../components/ChatBubble.jsx";
import { LiveProvider, useLiveStatus } from "../live/LiveContext.jsx";

// Resource key -> built module page. Resources not listed here fall back to a
// clearly-labelled prototype placeholder (built in later phases).
const PAGES = {
  orders: Orders,
  order_desk: SuperOrders,
  super_dashboard: SuperDashboard,
  super_managers: SuperManagers,
  super_workers: SuperWorkers,
  super_tasks: SuperTasks,
  super_production: SuperProduction,
  super_inventory: SuperInventory,
  super_quality: SuperQuality,
  super_dispatch: SuperDispatch,
  super_attendance: SuperAttendance,
  super_accounts: SuperAccounts,
  super_alerts: SuperAlerts,
  super_activity: SuperActivity,
  super_settings: SuperSettings,
  my_tasks: MyTasks,
  yarn: MaterialReceiving,
  stock: RawInventory,
  purchase: PurchaseOrders,
  purchase_dashboard: PurchaseDashboard,
  suppliers_desk: SuppliersDesk,
  purchase_requests: PurchaseRequests,
  low_stock: LowStockAlerts,
  material_requirements: MaterialRequirements,
  purchase_reports: PurchaseReports,
  purchase_notifications: PurchaseNotifications,
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
  team: Team,
  master_data: MasterData,
  // Production Manager screens.
  pm_dashboard: ProdDashboard,
  pm_orders: ProdOrders,
  pm_planning: ProdPlanning,
  pm_stages: ProdStages,
  pm_machines: ProdMachines,
  pm_workers: ProdWorkers,
  pm_monitoring: ProdMonitoring,
  pm_materials: ProdMaterials,
  pm_qc: ProdQc,
  pm_reports: ProdReports,
  pm_notifications: ProdNotifications,
  pm_activity: ProdActivity,
  // Sales & Dispatch Manager screens.
  sd_dashboard: SalesDashboard,
  sd_orders: SalesBuyerOrders,
  sd_buyers: SalesBuyers,
  sd_tracking: SalesTracking,
  sd_stock: SalesStock,
  sd_planning: SalesPlanning,
  sd_challan: SalesChallan,
  sd_history: SalesHistory,
  sd_invoices: SalesInvoices,
  sd_delivery: SalesDelivery,
  sd_notifications: SalesNotifications,
  sd_reports: SalesReports,
  sd_activity: SalesActivity,
  // Accounts & Finance Manager screens (buyer/supplier payments, attendance and
  // wages reuse the existing payments/attendance/wages pages via shared keys).
  am_dashboard: AccountsDashboard,
  am_invoices: AccountsInvoices,
  am_overtime: AccountsOvertime,
  am_prod_expenses: AccountsProductionExpenses,
  am_expenses: AccountsExpenses,
  am_reports: AccountsReports,
  am_notifications: AccountsNotifications,
  am_activity: AccountsActivity,
};

// Role label lookup for display (keys match backend role names).
const ROLE_LABELS = {
  owner: "Owner",
  store_manager: "Store manager",
  floor_supervisor: "Floor supervisor",
  quality_inspector: "Quality inspector",
  accountant: "Accountant",
  buyer: "Buyer",
  manager: "Supermanager",
  production_manager: "Production manager",
  sales_manager: "Sales & Dispatch manager",
  accounts_manager: "Accounts & Finance manager",
};

// The app shell after login. The sidebar is built from the `menu` returned by the
// backend for the user's role — ONE config, no per-role UI code. The content area
// is a placeholder; real module pages arrive in later phases.
// Wrap the shell so every page can use live updates.
export default function AppShell() {
  return (
    <LiveProvider>
      <Shell />
    </LiveProvider>
  );
}

const LEVEL_ICON = { alert: "⛔", warn: "⚠️", success: "✅", info: "ℹ️" };

function ago(ms) {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  return m < 60 ? `${m} min ago` : `${Math.round(m / 60)} h ago`;
}

// "● Live · updated 3s ago" in the top bar.
function LiveBadge() {
  const { status, updatedAt } = useLiveStatus();
  const [, tick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, []);
  const text =
    status === "live"
      ? `Live · updated ${updatedAt ? ago(Date.now() - updatedAt) : "now"}`
      : status === "connecting"
        ? "Connecting…"
        : "Reconnecting…";
  return (
    <span
      className={`live-badge is-${status}`}
      title="Screens update by themselves when anything changes"
    >
      <i aria-hidden />
      <span className="live-badge-text">{text}</span>
    </span>
  );
}

function Toasts() {
  const { toasts, dismissToast } = useLiveStatus();
  return (
    <div className="live-toasts" aria-live="polite">
      {toasts.map((t) => (
        <button
          key={t.key}
          className={`live-toast is-${t.level}`}
          onClick={() => dismissToast(t.key)}
        >
          <span aria-hidden>{LEVEL_ICON[t.level] || "ℹ️"}</span> {t.message}
        </button>
      ))}
    </div>
  );
}

function Shell() {
  const { user, menu, logout } = useAuth();
  const live = useLiveStatus();
  // The open page follows the URL (/app/reports etc.), so refresh keeps you on
  // the same page and the browser Back button moves between pages.
  const pathFromUrl = () => {
    const here = window.location.pathname;
    return menu.some((m) => m.path === here) ? here : menu[0]?.path || "";
  };
  const [active, setActiveState] = useState(pathFromUrl);

  function setActive(path) {
    setActiveState(path);
    if (path && window.location.pathname !== path) {
      window.history.pushState({}, "", path);
    }
  }

  useEffect(() => {
    // Plain /app (or an unknown /app/... path) -> show the first page's URL.
    const here = window.location.pathname;
    if (menu[0] && !menu.some((m) => m.path === here)) {
      window.history.replaceState({}, "", menu[0].path);
    }
    function onPop() {
      setActiveState(pathFromUrl());
    }
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [menu]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);

  // Owner pages can request an in-app navigation (e.g. a dashboard chart bar
  // linking to the filtered Orders list) via an `etm:navigate` event. Inert for
  // every other role, which never dispatches it.
  useEffect(() => {
    function onNavigate(e) {
      const path = e.detail?.path;
      if (path && menu.some((m) => m.path === path)) {
        setActive(path);
        setSidebarOpen(false);
      }
    }
    window.addEventListener("etm:navigate", onNavigate);
    return () => window.removeEventListener("etm:navigate", onNavigate);
  }, [menu]);

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
              <MenuIcon resource={item.resource} />
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

          {user.role === "manager" && (
            <TopSearch
              onGo={(path) => {
                if (menu.some((m) => m.path === path)) setActive(path);
              }}
            />
          )}

          <div className="shell-top-actions">
            <LiveBadge />
            {/* Notifications bell */}
            <div className="notif-wrap">
              <button
                className="icon-btn"
                title="Notifications"
                aria-label={`Notifications${live.unread ? `, ${live.unread} new` : ""}`}
                aria-expanded={notifOpen}
                onClick={() => {
                  setNotifOpen((v) => !v);
                  live.markRead();
                }}
              >
                🔔
                {live.unread > 0 && (
                  <span className="notif-count">{live.unread}</span>
                )}
              </button>
              {notifOpen && (
                <div
                  className="notif-popover"
                  role="dialog"
                  aria-label="Notifications"
                >
                  <div className="notif-head">Notifications</div>
                  {live.notes.length === 0 ? (
                    <div className="notif-empty muted">
                      You're all caught up — no new notifications.
                    </div>
                  ) : (
                    <ul className="notif-list">
                      {live.notes.map((n) => (
                        <li key={n.key} className={`notif-item is-${n.level}`}>
                          <span aria-hidden>{LEVEL_ICON[n.level] || "ℹ️"}</span>
                          <span>
                            {n.message}
                            <small className="muted">
                              {n.current
                                ? "Right now"
                                : new Date(n.at).toLocaleTimeString()}
                            </small>
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
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

      <Toasts />

      {/* Floating chat bubble on every logged-in page too (mount point). */}
      <ChatBubble />
    </div>
  );
}

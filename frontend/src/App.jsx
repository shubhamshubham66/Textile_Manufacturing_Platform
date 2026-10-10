import Landing from "./pages/Landing.jsx";
import HealthCheck from "./pages/HealthCheck.jsx";

// Minimal path-based routing (no router dependency yet). The public landing page
// is the default route; /health keeps the Phase 2 backend/DB check available.
// A real router + app routes (/login, dashboards) arrive in a later phase.
export default function App() {
  const path = window.location.pathname;

  if (path.startsWith("/health")) {
    return <HealthCheck />;
  }

  return <Landing />;
}

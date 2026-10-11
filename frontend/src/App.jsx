import Landing from "./pages/Landing.jsx";
import HealthCheck from "./pages/HealthCheck.jsx";
import Login from "./pages/Login.jsx";
import Signup from "./pages/Signup.jsx";
import ForgotPassword from "./pages/ForgotPassword.jsx";
import AppShell from "./pages/AppShell.jsx";
import { useAuth } from "./auth/AuthContext.jsx";

// Minimal path-based routing (no router dependency yet):
//   /          -> public landing page
//   /login     -> login page (redirects to /app if already signed in)
//   /signup    -> create an account (role, name, email OTP, password)
//   /forgot-password -> buyer password reset by email OTP
//   /app       -> protected app shell (redirects to /login if not signed in)
//   /health    -> Phase 2 backend/DB health check
export default function App() {
  const { user, loading } = useAuth();
  const path = window.location.pathname;

  if (path.startsWith("/health")) return <HealthCheck />;

  // Wait for the auth bootstrap (token -> user) before deciding guarded routes.
  if (loading && (path.startsWith("/app") || path.startsWith("/login"))) {
    return (
      <div className="auth-wrap">
        <div className="auth-card">
          <p className="muted">Loading…</p>
        </div>
      </div>
    );
  }

  if (path.startsWith("/signup")) return <Signup />;
  if (path.startsWith("/forgot-password")) return <ForgotPassword />;

  if (path.startsWith("/login")) {
    if (user) {
      window.location.replace("/app");
      return null;
    }
    return <Login />;
  }

  if (path.startsWith("/app")) {
    if (!user) {
      window.location.replace("/login");
      return null;
    }
    return <AppShell />;
  }

  return <Landing />;
}

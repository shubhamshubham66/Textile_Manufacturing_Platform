import { createContext, useContext, useEffect, useState } from "react";
import { apiFetch, getToken, setToken } from "../lib/api.js";

// Holds the logged-in user + role menu. The menu comes from the backend
// (role-to-menu config lives in ONE place server-side), never hard-coded per role
// in the UI.
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [menu, setMenu] = useState([]);
  const [loading, setLoading] = useState(true);

  // On load, if a token exists, resolve the current user.
  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      if (!getToken()) {
        setLoading(false);
        return;
      }
      try {
        const data = await apiFetch("/api/auth/me");
        if (!cancelled) {
          setUser(data.user);
          setMenu(data.menu || []);
        }
      } catch {
        setToken(null); // stale/invalid token
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  async function login(email, password) {
    const data = await apiFetch("/api/auth/login", {
      method: "POST",
      auth: false,
      body: { email, password },
    });
    setToken(data.token);
    setUser(data.user);
    setMenu(data.menu || []);
    return data.user;
  }

  async function logout() {
    try {
      await apiFetch("/api/auth/logout", { method: "POST" });
    } catch {
      // ignore network/expiry errors on logout
    }
    setToken(null);
    setUser(null);
    setMenu([]);
    window.location.assign("/login");
  }

  return (
    <AuthContext.Provider value={{ user, menu, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

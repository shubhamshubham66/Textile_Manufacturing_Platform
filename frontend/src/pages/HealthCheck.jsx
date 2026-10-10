import { useEffect, useState } from "react";

// Backend/DB health check (from Phase 2). Kept at /health so it stays available
// for demos and debugging while the landing page is the default route.
export default function HealthCheck() {
  const [state, setState] = useState({ status: "loading" });

  async function checkHealth() {
    setState({ status: "loading" });
    try {
      const res = await fetch("/api/health");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setState({ status: "ok", data });
    } catch (err) {
      setState({ status: "error", error: String(err) });
    }
  }

  useEffect(() => {
    checkHealth();
  }, []);

  return (
    <div className="container">
      <h1>Everest Textile Mills</h1>
      <p className="muted">
        Textile Manufacturing System — backend health check
      </p>

      <div className="card">
        {state.status === "loading" && (
          <p>
            <span className="badge loading">Checking…</span> Contacting backend…
          </p>
        )}

        {state.status === "error" && (
          <>
            <p>
              <span className="badge error">Offline</span> Could not reach the
              backend.
            </p>
            <p className="muted">{state.error}</p>
            <p className="muted">
              Is the backend running on <code>http://localhost:8000</code>?
            </p>
          </>
        )}

        {state.status === "ok" && (
          <>
            <p>
              <span
                className={`badge ${
                  state.data.database.connected ? "ok" : "error"
                }`}
              >
                {state.data.status.toUpperCase()}
              </span>{" "}
              {state.data.service} v{state.data.version}
            </p>
            <ul className="muted">
              <li>
                Database:{" "}
                {state.data.database.connected
                  ? `connected (${state.data.database.dialect})`
                  : `NOT connected — ${state.data.database.error}`}
              </li>
              <li>Server time: {state.data.time}</li>
            </ul>
          </>
        )}

        <button onClick={checkHealth}>Re-check</button>
        <p className="muted" style={{ marginTop: "1rem" }}>
          <a href="/">← Back to landing page</a>
        </p>
      </div>
    </div>
  );
}

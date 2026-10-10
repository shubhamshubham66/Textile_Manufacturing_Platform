import { createContext, useContext, useEffect, useRef, useState } from "react";
import { apiFetch } from "../lib/api.js";

// Live updates for the logged-in app.
//
// One Server-Sent Events connection per tab (/api/live/stream). Every change the
// server reports is re-broadcast as a window event, and pages that care call
// useLive(topics, load) to quietly reload their data. Changes meant for people
// also land in the bell and show as a short toast.
//
// If the connection drops (network, proxy timeout, server restart) it takes a
// fresh one-minute ticket, reconnects with backoff and asks every page to
// reload once, so nothing missed while offline stays stale.

const LiveCtx = createContext(null);
const EVT = "etm:live";
const MAX_NOTES = 30;

// Set while a page's loader is being called because of a live change, so the
// loader can skip its full-page "Loading…" state (see isLiveRefresh below).
let liveRefreshing = false;
export function isLiveRefresh() {
  return liveRefreshing;
}

export function LiveProvider({ children }) {
  const [status, setStatus] = useState("connecting"); // connecting | live | offline
  const [updatedAt, setUpdatedAt] = useState(null);
  const [notes, setNotes] = useState([]);
  const [unread, setUnread] = useState(0);
  const [toasts, setToasts] = useState([]);
  const esRef = useRef(null);

  useEffect(() => {
    let stopped = false;
    let retry = 0;
    let timer = null;

    function addNote(n, toast) {
      const note = { key: `${n.id || "a"}-${n.message}-${Math.random()}`, ...n };
      setNotes((list) => [note, ...list].slice(0, MAX_NOTES));
      if (toast) {
        setUnread((u) => u + 1);
        setToasts((t) => [...t, note].slice(-3));
        setTimeout(() => setToasts((t) => t.filter((x) => x.key !== note.key)), 5000);
      }
    }

    async function loadAlerts() {
      try {
        const d = await apiFetch("/api/live/alerts");
        setNotes((list) => [
          ...list.filter((n) => !n.current),
          ...d.alerts.map((a, i) => ({ ...a, key: `cur-${i}-${a.message}`, current: true })),
        ]);
      } catch {
        /* the bell just stays as it is */
      }
    }

    async function connect() {
      if (stopped) return;
      setStatus((s) => (s === "live" ? "live" : "connecting"));
      let ticket;
      try {
        ticket = (await apiFetch("/api/live/ticket", { method: "POST" })).ticket;
      } catch {
        return scheduleReconnect();
      }
      if (stopped) return;
      const es = new EventSource(`/api/live/stream?ticket=${encodeURIComponent(ticket)}`);
      esRef.current = es;

      es.addEventListener("hello", () => {
        retry = 0;
        setStatus("live");
        setUpdatedAt(Date.now());
        // (Re)connected: reload everything once in case we missed changes.
        window.dispatchEvent(new CustomEvent(EVT, { detail: { topic: "*" } }));
        loadAlerts();
      });
      es.addEventListener("change", (e) => {
        let data;
        try {
          data = JSON.parse(e.data);
        } catch {
          return;
        }
        setUpdatedAt(Date.now());
        window.dispatchEvent(new CustomEvent(EVT, { detail: data }));
        if (data.notify && data.message) addNote(data, true);
      });
      es.onerror = () => {
        es.close();
        if (esRef.current === es) esRef.current = null;
        scheduleReconnect();
      };
    }

    function scheduleReconnect() {
      if (stopped) return;
      setStatus("offline");
      retry += 1;
      const wait = Math.min(30000, 1000 * 2 ** Math.min(retry, 5));
      clearTimeout(timer);
      timer = setTimeout(connect, wait);
    }

    connect();
    return () => {
      stopped = true;
      clearTimeout(timer);
      esRef.current?.close();
    };
  }, []);

  const value = {
    status,
    updatedAt,
    notes,
    unread,
    toasts,
    markRead: () => setUnread(0),
    dismissToast: (key) => setToasts((t) => t.filter((x) => x.key !== key)),
  };
  return <LiveCtx.Provider value={value}>{children}</LiveCtx.Provider>;
}

export function useLiveStatus() {
  return useContext(LiveCtx);
}

// Call `reload` (debounced) whenever a change on one of `topics` arrives.
// Example: useLive(["machines", "production"], load)
export function useLive(topics, reload) {
  const fn = useRef(reload);
  fn.current = reload;
  const key = topics.join(",");

  useEffect(() => {
    const wanted = new Set(key.split(","));
    let t = null;
    function onLive(e) {
      const topic = e.detail?.topic;
      if (topic !== "*" && !wanted.has(topic)) return;
      clearTimeout(t);
      t = setTimeout(() => {
        liveRefreshing = true;
        try {
          fn.current?.();
        } finally {
          // The loader's synchronous start (where it sets "Loading…") has run.
          liveRefreshing = false;
        }
      }, 400);
    }
    window.addEventListener(EVT, onLive);
    return () => {
      window.removeEventListener(EVT, onLive);
      clearTimeout(t);
    };
  }, [key]);
}

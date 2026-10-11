import { useEffect, useRef, useState } from "react";
import { getToken } from "../../lib/api.js";
import "./chat-widget.css";

// Floating AI chat widget. The browser calls ONLY our backend
// (POST /api/chatbot/message) — never Dify directly. It attaches the auth token
// if present (logged-in mode gives role-scoped answers); works logged out too
// (public FAQ/how-to mode).
//
// Opens on click, or when any page dispatches: window event "etm:open-chat".

// The published Dify chat app, shown inside the bubble. Override with
// VITE_DIFY_CHAT_URL; set it to an empty string to use the backend-proxy chat
// below instead (which adds role-scoped live data).
const DIFY_CHAT_URL =
  import.meta.env.VITE_DIFY_CHAT_URL ?? "https://udify.app/chatbot/k7RDaKn0bDbN2TCf";

const SESSION_KEY = "etm_chat_session";

function getSessionId() {
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id =
      (crypto.randomUUID && crypto.randomUUID()) ||
      `s-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

// Two little AI eyes on the bubble: they blink, and the pupils look toward
// the cursor (they stay still for people who ask for reduced motion).
function BotEyes() {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return undefined;
    let raf = 0;
    const onMove = (e) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const r = el.getBoundingClientRect();
        const dx = e.clientX - (r.left + r.width / 2);
        const dy = e.clientY - (r.top + r.height / 2);
        const d = Math.hypot(dx, dy) || 1;
        const k = Math.min(1, d / 160);
        el.style.setProperty("--px", `${((dx / d) * 3 * k).toFixed(2)}px`);
        el.style.setProperty("--py", `${((dy / d) * 2.5 * k).toFixed(2)}px`);
      });
    };
    window.addEventListener("mousemove", onMove);
    return () => {
      window.removeEventListener("mousemove", onMove);
      cancelAnimationFrame(raf);
    };
  }, []);
  return (
    <span className="cw-eyes" ref={ref} aria-hidden>
      <i className="cw-eye" />
      <i className="cw-eye" />
    </span>
  );
}

function BubbleFace() {
  return (
    <>
      <BotEyes />
      <span className="cw-bubble-name">ev-tx</span>
    </>
  );
}

export default function ChatWidget() {
  return DIFY_CHAT_URL ? <DifyChat /> : <ProxyChat />;
}

// Dify's own chat page in a panel. Mounted on first open and kept mounted
// (just hidden) so the conversation survives closing the panel.
function DifyChat() {
  const [open, setOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const openHandler = () => setOpen(true);
    window.addEventListener("etm:open-chat", openHandler);
    return () => window.removeEventListener("etm:open-chat", openHandler);
  }, []);
  useEffect(() => {
    if (open) setLoaded(true);
    if (!open) return undefined;
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div className="cw-mount">
      {loaded && (
        <div
          className="cw-panel cw-panel-dify"
          role="dialog"
          aria-label="AI assistant"
          hidden={!open}
        >
          {/* No header of our own: Dify's chat shows its own title bar.
              Close with the ev-tx bubble or the Esc key. */}
          <iframe
            className="cw-frame"
            src={DIFY_CHAT_URL}
            title="Everest AI assistant"
            allow="microphone"
          />
        </div>
      )}
      <button
        className="cw-bubble"
        type="button"
        aria-label={open ? "Close AI assistant" : "Open AI assistant"}
        aria-expanded={open}
        title={open ? "Close the chat" : "Ask the AI assistant"}
        onClick={() => setOpen((v) => !v)}
      >
        <BubbleFace />
      </button>
    </div>
  );
}

function ProxyChat() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      from: "bot",
      text: "Hi! I'm the Everest assistant. Ask me how to track an order, how to log in, or how the 5-step process works.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const listRef = useRef(null);

  useEffect(() => {
    const openHandler = () => setOpen(true);
    window.addEventListener("etm:open-chat", openHandler);
    return () => window.removeEventListener("etm:open-chat", openHandler);
  }, []);

  useEffect(() => {
    // Auto-scroll to the latest message.
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, loading, open]);

  async function send(e) {
    e?.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    setMessages((m) => [...m, { from: "user", text }]);
    setInput("");
    setError("");
    setLoading(true);

    try {
      const headers = { "Content-Type": "application/json" };
      const token = getToken(); // this tab's login
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch("/api/chatbot/message", {
        method: "POST",
        headers,
        body: JSON.stringify({ message: text, session_id: getSessionId() }),
      });

      const data = await res.json().catch(() => null);
      if (!res.ok) {
        const msg =
          data?.error?.message || `Assistant unavailable (HTTP ${res.status}).`;
        throw new Error(msg);
      }
      setMessages((m) => [
        ...m,
        { from: "bot", text: data?.reply || "(no reply)" },
      ]);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="cw-mount">
      {open && (
        <div className="cw-panel" role="dialog" aria-label="AI assistant">
          <div className="cw-head">
            <span className="cw-dot" /> ev-tx
            <button
              className="cw-close"
              aria-label="Close chat"
              onClick={() => setOpen(false)}
            >
              ×
            </button>
          </div>

          <div className="cw-body" ref={listRef}>
            {messages.map((m, i) => (
              <div key={i} className={`cw-msg cw-${m.from}`}>
                {m.text}
              </div>
            ))}
            {loading && <div className="cw-msg cw-bot cw-typing">Typing…</div>}
            {error && <div className="cw-error">{error}</div>}
          </div>

          <form className="cw-input" onSubmit={send}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question…"
              aria-label="Message"
              disabled={loading}
            />
            <button
              type="submit"
              className="cw-send"
              disabled={loading || !input.trim()}
            >
              Send
            </button>
          </form>
        </div>
      )}

      <button
        className="cw-bubble"
        type="button"
        aria-label="Open AI assistant"
        title="Ask the AI assistant"
        onClick={() => setOpen((v) => !v)}
      >
        <BubbleFace />
      </button>
    </div>
  );
}

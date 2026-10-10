import { useEffect, useRef, useState } from "react";
import "./chat-widget.css";

// Floating AI chat widget. The browser calls ONLY our backend
// (POST /api/chatbot/message) — never Dify directly. It attaches the auth token
// if present (logged-in mode gives role-scoped answers); works logged out too
// (public FAQ/how-to mode).
//
// Opens on click, or when any page dispatches: window event "etm:open-chat".

const SESSION_KEY = "etm_chat_session";
const TOKEN_KEY = "etm_token"; // same key the app auth uses

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

export default function ChatWidget() {
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
      const token = localStorage.getItem(TOKEN_KEY);
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
            <span className="cw-dot" /> Everest Assistant
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
        💬
      </button>
    </div>
  );
}

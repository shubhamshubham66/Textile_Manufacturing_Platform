import { useEffect, useState } from "react";

// Floating chat bubble — MOUNT POINT ONLY (no chat logic here).
//
// The actual chatbot is owned by the mini developer (chatbot/ and
// backend/chatbot/, branch mini/chatbot). It must talk to our backend endpoint
// POST /api/chatbot/message and NEVER call Dify directly from the browser.
//
// This component reserves the on-screen slot and exposes a tiny "open" signal so
// other pages (e.g. the buyer portal "Ask AI" button) can request it to open:
//   window.dispatchEvent(new Event("etm:open-chat"))
// When the mini developer wires the real widget, they replace the panel body
// below — the open/close plumbing is already here.
export default function ChatBubble() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const openHandler = () => setOpen(true);
    window.addEventListener("etm:open-chat", openHandler);
    return () => window.removeEventListener("etm:open-chat", openHandler);
  }, []);

  return (
    <div className="chat-bubble-mount">
      {open && (
        <div className="chat-panel" role="dialog" aria-label="AI assistant">
          <div className="chat-panel-head">
            <span>AI assistant</span>
            <button
              className="chat-panel-close"
              aria-label="Close"
              onClick={() => setOpen(false)}
            >
              ×
            </button>
          </div>
          <div className="chat-panel-body muted">
            {/* Mini developer's chat widget mounts here. It posts to
                /api/chatbot/message (never Dify directly). */}
            The assistant is being connected. This panel is the mount point for
            the chatbot widget (built separately).
          </div>
        </div>
      )}
      <button
        className="chat-bubble"
        type="button"
        title="AI assistant"
        aria-label="Open AI assistant"
        onClick={() => setOpen((v) => !v)}
      >
        💬
      </button>
    </div>
  );
}

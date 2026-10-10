// Floating chat bubble — PLACEHOLDER / MOUNT POINT ONLY.
//
// The actual chatbot is owned by the mini developer (chatbot/ and
// backend/chatbot/, branch mini/chatbot). It must talk to our backend endpoint
// POST /api/chatbot/message and NEVER call Dify directly from the browser.
//
// This component only reserves the on-screen slot so the bubble appears on every
// page. Do not implement the chat logic here — the mini developer will replace
// the body of this mount point.
export default function ChatBubble() {
  return (
    <div className="chat-bubble-mount" aria-hidden>
      <button
        className="chat-bubble"
        type="button"
        title="AI assistant (coming soon)"
        aria-label="Open AI assistant"
        disabled
      >
        💬
      </button>
    </div>
  );
}

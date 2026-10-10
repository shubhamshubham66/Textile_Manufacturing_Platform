// AI assistant section: 3 how-to steps + a sample chat preview.
// This is marketing/explainer content only — the real chatbot is built by the
// mini developer and reached via our backend /api/chatbot/message.
const STEPS = [
  {
    n: 1,
    title: "Ask in plain words",
    text: "Type a question like you'd ask a colleague — no menus to hunt through.",
  },
  {
    n: 2,
    title: "It reads live data",
    text: "Logged in, the assistant answers from real factory data, limited to your role.",
  },
  {
    n: 3,
    title: "Act on the answer",
    text: "Get stock warnings, order status and a daily owner summary without digging.",
  },
];

const CHAT = [
  {
    from: "user",
    text: "Which machines are idle right now and what's it costing?",
  },
  {
    from: "bot",
    text: "3 machines are idle: Spin-02, Weave-03, Dye-02. Idle cost so far today ≈ ₹2,350. Spin-03 is in breakdown (motor fault).",
  },
  { from: "user", text: "Is there enough blue yarn for order ORD-2003?" },
  {
    from: "bot",
    text: "No — ORD-2003 needs 300 kg Cotton 40s (Blue) but only 90 kg is in stock. Raise a purchase for ~210 kg.",
  },
];

export default function AiSection() {
  return (
    <section id="ai" className="section section-alt">
      <div className="section-inner">
        <h2 className="section-title">Ask the AI assistant</h2>
        <p className="section-sub">
          A chat helper on every page — public FAQ before login, your live data
          after.
        </p>

        <div className="ai-layout">
          <ol className="ai-steps">
            {STEPS.map((s) => (
              <li key={s.n}>
                <span className="ai-step-no">{s.n}</span>
                <div>
                  <h3>{s.title}</h3>
                  <p>{s.text}</p>
                </div>
              </li>
            ))}
          </ol>

          <div className="chat-preview" role="img" aria-label="Sample chat">
            <div className="chat-head">
              <span className="dot" /> Everest Assistant
            </div>
            <div className="chat-body">
              {CHAT.map((msg, i) => (
                <div key={i} className={`chat-msg ${msg.from}`}>
                  {msg.text}
                </div>
              ))}
            </div>
            <div className="chat-foot muted">Sample conversation</div>
          </div>
        </div>
      </div>
    </section>
  );
}

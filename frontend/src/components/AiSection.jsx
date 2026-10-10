// AI assistant: how to use it in three steps, and a sample conversation.
// The live assistant is the chat bubble (it talks to our backend, never to Dify
// directly); the button below opens it.
const STEPS = [
  {
    title: "Open the chat bubble",
    text: "It's in the corner of every page. Before login it answers how-to questions.",
  },
  {
    title: "Ask in plain words",
    text: "“Which machines are idle?” or “Is there enough blue yarn for ORD-2003?”",
  },
  {
    title: "Get answers from live data",
    text: "After login it reads real factory data, limited to your role. Buyers only see their own orders.",
  },
];

const CHAT = [
  { from: "user", text: "Which machines are idle right now, and what's it costing?" },
  {
    from: "bot",
    text: "Spin-02, Weave-03 and Dye-02 are idle, and Spin-03 is down with a motor fault. That's about ₹3,400 lost today.",
  },
  { from: "user", text: "Is there enough blue yarn for ORD-2003?" },
  {
    from: "bot",
    text: "No. ORD-2003 needs 600 kg of Cotton 40s (Blue) and 90 kg is in stock. Raise a purchase for about 510 kg.",
  },
];

export default function AiSection() {
  return (
    <section id="ai" className="lp-section lp-section-tint">
      <div className="lp-inner lp-ai">
        <div>
          <div className="lp-head lp-head-left">
            <h2>Ask the mill a question</h2>
            <p>An assistant that knows your stock, machines and orders.</p>
          </div>
          <ol className="lp-ai-steps">
            {STEPS.map((s, i) => (
              <li key={s.title}>
                <span className="lp-ai-no">{i + 1}</span>
                <div>
                  <h3>{s.title}</h3>
                  <p>{s.text}</p>
                </div>
              </li>
            ))}
          </ol>
          <button
            type="button"
            className="lp-btn lp-btn-primary"
            onClick={() => window.dispatchEvent(new Event("etm:open-chat"))}
          >
            Open the assistant
          </button>
        </div>

        <figure className="lp-chat" aria-label="Sample conversation">
          <div className="lp-chat-head">
            <i /> Everest Assistant
          </div>
          <div className="lp-chat-body">
            {CHAT.map((m, i) => (
              <p key={i} className={`lp-msg lp-msg-${m.from}`}>
                {m.text}
              </p>
            ))}
          </div>
          <figcaption>Sample conversation with demo data</figcaption>
        </figure>
      </div>
    </section>
  );
}

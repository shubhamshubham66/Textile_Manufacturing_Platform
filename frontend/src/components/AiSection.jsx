import { useState } from "react";

// Interactive showcase topics demonstrating real-world textile factory queries
const PRESET_TOPICS = [
  {
    id: "floor",
    label: "Floor & Machines",
    icon: "🏭",
    badge: "Idle Loss USP",
    question: "Which machines are idle right now, and what is it costing?",
    time: "Just now",
    answer: {
      title: "Real-Time Machine Stoppage & Loss Analysis",
      summary: "3 machines are currently non-productive, incurring ₹3,404 loss today.",
      stats: [
        { label: "Idle / Breakdown", value: "3 Machines", variant: "danger" },
        { label: "Rupees Lost", value: "₹3,404 today", variant: "warn" },
        { label: "Top Cause", value: "Motor fault (Spin-03)", variant: "primary" },
      ],
      details:
        "Spin-02, Weave-03 and Dye-02 are idle (shift changeover). Spin-03 has been stopped for 4.2 hours waiting for motor overhaul. Loss is calculated as hourly cost × downtime.",
      actionLabel: "View Live Floor Telemetry →",
      target: "features",
    },
  },
  {
    id: "yarn",
    label: "Yarn & Inventory",
    icon: "🧵",
    badge: "Auto Stock Check",
    question: "Is there enough blue yarn for confirmed Order ORD-2003?",
    time: "1 min ago",
    answer: {
      title: "Material Sufficiency Verification",
      summary: "Shortfall detected. 510 kg additional Cotton 40s needed before weaving.",
      stats: [
        { label: "Required for Order", value: "600 kg", variant: "primary" },
        { label: "In-Stock Balance", value: "90 kg (Safe)", variant: "warn" },
        { label: "Purchase Deficit", value: "510 kg Short", variant: "danger" },
      ],
      details:
        "ORD-2003 requires 600 kg Cotton 40s (Navy Blue). Only 90 kg is present in Bin A-14. Auto-generated purchase requisition ready for Vardhman Textiles (lead time: 2 days).",
      actionLabel: "Open Purchase Requisition →",
      target: "features",
    },
  },
  {
    id: "qc",
    label: "Quality & Dispatch",
    icon: "🔍",
    badge: "Roll Traceability",
    question: "Show quality inspection yield and rolls ready for dispatch today.",
    time: "3 mins ago",
    answer: {
      title: "Roll Grading & Dispatch Readiness",
      summary: "42 of 45 fabric rolls passed quality grading (93.3% first-pass yield).",
      stats: [
        { label: "A-Grade Passed", value: "42 Rolls", variant: "success" },
        { label: "Rework / Rejected", value: "3 Rolls", variant: "danger" },
        { label: "Ready to Dispatch", value: "14 Rolls", variant: "primary" },
      ],
      details:
        "14 passed rolls are staged at the loading bay with barcodes scanned for Buyer Raymond Ltd. A-Grade certificate and GST Invoice #INV-8821 ready for printing.",
      actionLabel: "Review Pickable Rolls →",
      target: "features",
    },
  },
  {
    id: "finance",
    label: "Wages & Profit",
    icon: "💰",
    badge: "Live P&L",
    question: "What is this month's net profit margin and worker wage total?",
    time: "5 mins ago",
    answer: {
      title: "Monthly Factory Profit & Loss Reconciliation",
      summary: "Net profit margin is 18.4% on ₹24,80,000 booked revenue.",
      stats: [
        { label: "Month Revenue", value: "₹24,80,000", variant: "success" },
        { label: "Wages & Overtime", value: "₹3,42,000", variant: "primary" },
        { label: "Net Factory Profit", value: "₹4,56,320", variant: "warn" },
      ],
      details:
        "Yarn procurement bills: ₹14.2L, machine depreciation & electricity: ₹2.6L. Total 28 workers clocked in with overtime calculated via digital punch register.",
      actionLabel: "Explore Full P&L Statement →",
      target: "features",
    },
  },
];

export default function AiSection() {
  const [activeTab, setActiveTab] = useState(0);
  const activeTopic = PRESET_TOPICS[activeTab];

  function openLiveChat() {
    window.dispatchEvent(new Event("etm:open-chat"));
  }

  function handleActionClick(targetId, e) {
    e.preventDefault();
    document.getElementById(targetId)?.scrollIntoView({ behavior: "smooth" });
  }

  return (
    <section id="ai" className="lp-section lp-ai-section">
      <div className="lp-inner">
        {/* Section Header */}
        <div className="lp-ai-header">
          <div className="lp-ai-eyebrow">
            <span className="lp-ai-sparkle">✨</span>
            <span>Domain-Trained Textile Factory AI Copilot</span>
          </div>
          <h2>Ask your mill anything. Get live operational answers.</h2>
          <p>
            No more walking the weaving floor, flipping through store registers, or calling
            supervisors. The Everest AI Copilot talks directly to your database, telemetry sensors,
            and role accounts.
          </p>
        </div>

        {/* Interactive Showcase Grid */}
        <div className="lp-ai-showcase">
          {/* Left Column: Interactive Capability Selector */}
          <div className="lp-ai-controls">
            <h3 className="lp-ai-controls-title">Try real factory questions</h3>
            <p className="lp-ai-controls-sub">
              Click any operational topic below to see how the assistant answers with live data:
            </p>

            <div className="lp-ai-tabs">
              {PRESET_TOPICS.map((topic, idx) => {
                const isActive = activeTab === idx;
                return (
                  <button
                    key={topic.id}
                    type="button"
                    className={`lp-ai-tab-btn ${isActive ? "is-active" : ""}`}
                    onClick={() => setActiveTab(idx)}
                  >
                    <span className="lp-ai-tab-icon">{topic.icon}</span>
                    <div className="lp-ai-tab-meta">
                      <div className="lp-ai-tab-title-row">
                        <strong>{topic.label}</strong>
                        <span className="lp-ai-tab-badge">{topic.badge}</span>
                      </div>
                      <span className="lp-ai-tab-preview">{topic.question}</span>
                    </div>
                    <span className="lp-ai-tab-chevron" aria-hidden>
                      {isActive ? "●" : "›"}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Feature Highlights Pills */}
            <div className="lp-ai-features-strip">
              <div className="lp-ai-feat-pill">
                <span>⚡</span> Sub-second response
              </div>
              <div className="lp-ai-feat-pill">
                <span>🔒</span> Role-isolated security
              </div>
              <div className="lp-ai-feat-pill">
                <span>📊</span> Real-time SQL telemetry
              </div>
              <div className="lp-ai-feat-pill">
                <span>🗣️</span> English & Hindi queries
              </div>
            </div>

            {/* Direct Action Launchers */}
            <div className="lp-ai-cta-group">
              <button
                type="button"
                className="lp-btn lp-btn-primary lp-ai-launch-btn"
                onClick={openLiveChat}
              >
                <span>✨ Launch Live AI Assistant</span>
              </button>
              <a href="/login" className="lp-btn lp-btn-outline">
                Test Drive with Demo Account
              </a>
            </div>
          </div>

          {/* Right Column: High-End Interactive AI Chat Simulator */}
          <div className="lp-ai-window" role="region" aria-label="Interactive AI Simulator">
            {/* Window Top Bar */}
            <div className="lp-ai-win-head">
              <div className="lp-ai-win-dots">
                <span className="dot dot-red" />
                <span className="dot dot-yellow" />
                <span className="dot dot-green" />
              </div>

              <div className="lp-ai-win-title">
                <span className="lp-ai-win-pulse" />
                <strong>Everest Copilot AI</strong>
                <span className="lp-ai-win-version">v2.4 · Live RAG</span>
              </div>

              <div className="lp-ai-win-status">
                <span className="lp-ai-status-pill">● Database Synced</span>
              </div>
            </div>

            {/* Chat Body */}
            <div className="lp-ai-win-body">
              {/* User Message Bubble */}
              <div className="lp-ai-bubble lp-ai-bubble-user">
                <div className="lp-ai-bubble-header">
                  <span className="lp-ai-user-avatar">👤</span>
                  <span className="lp-ai-sender-name">Mill Owner / Floor Supervisor</span>
                  <span className="lp-ai-msg-time">{activeTopic.time}</span>
                </div>
                <div className="lp-ai-user-text">{activeTopic.question}</div>
              </div>

              {/* Bot Response Bubble */}
              <div className="lp-ai-bubble lp-ai-bubble-bot">
                <div className="lp-ai-bubble-header">
                  <span className="lp-ai-bot-avatar">🤖</span>
                  <span className="lp-ai-sender-name">Everest Textile Copilot</span>
                  <span className="lp-ai-model-tag">FastAPI + Dify Engine</span>
                </div>

                <div className="lp-ai-bot-content">
                  {/* Summary Callout */}
                  <div className="lp-ai-summary-bar">
                    <span className="lp-ai-summary-icon">💡</span>
                    <p>
                      <strong>{activeTopic.answer.title}:</strong> {activeTopic.answer.summary}
                    </p>
                  </div>

                  {/* 3 Live KPI Cards */}
                  <div className="lp-ai-stats-grid">
                    {activeTopic.answer.stats.map((st) => (
                      <div
                        key={st.label}
                        className={`lp-ai-stat-card is-${st.variant}`}
                      >
                        <span className="lp-ai-stat-label">{st.label}</span>
                        <strong className="lp-ai-stat-value">{st.value}</strong>
                      </div>
                    ))}
                  </div>

                  {/* Details paragraph */}
                  <p className="lp-ai-details-text">{activeTopic.answer.details}</p>

                  {/* In-chat action button */}
                  <div className="lp-ai-action-footer">
                    <a
                      href={`#${activeTopic.answer.target}`}
                      className="lp-ai-action-link"
                      onClick={(e) => handleActionClick(activeTopic.answer.target, e)}
                    >
                      {activeTopic.answer.actionLabel}
                    </a>
                  </div>
                </div>
              </div>
            </div>

            {/* Window Interactive Input Strip */}
            <div className="lp-ai-win-foot" onClick={openLiveChat}>
              <div className="lp-ai-input-fake">
                <span className="lp-ai-input-icon">💬</span>
                <span className="lp-ai-input-placeholder">
                  Type your factory question or click to launch live assistant…
                </span>
                <button
                  type="button"
                  className="lp-ai-send-btn"
                  aria-label="Send query"
                  onClick={openLiveChat}
                >
                  ➤
                </button>
              </div>

              {/* Quick suggestion prompt chips */}
              <div className="lp-ai-quick-prompts">
                <span className="lp-ai-quick-label">Try asking:</span>
                <button
                  type="button"
                  className="lp-ai-chip"
                  onClick={() => setActiveTab(0)}
                >
                  “Which machines are idle?”
                </button>
                <button
                  type="button"
                  className="lp-ai-chip"
                  onClick={() => setActiveTab(1)}
                >
                  “Check yarn for ORD-2003”
                </button>
                <button
                  type="button"
                  className="lp-ai-chip"
                  onClick={() => setActiveTab(2)}
                >
                  “Passed rolls today”
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

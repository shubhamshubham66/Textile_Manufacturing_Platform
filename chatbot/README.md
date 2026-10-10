# chatbot/ — AI assistant (Dify)

AI assistant integration — **mini developer only**, branch `mini/chatbot`.

**Golden rule:** the browser must **never** call Dify directly. Flow is always:

```
Chat UI (frontend) → our backend POST /api/chatbot/message → Dify chat-messages API
```

Keys live in `.env` (`DIFY_API_KEY`, `DIFY_BASE_URL`), used **server-side only**.
Never commit secrets.

---

## What's in this track

| Area      | Path                                              | Purpose |
| --------- | ------------------------------------------------- | ------- |
| Dify app  | `chatbot/system_prompt.md`, `chatbot/faq_knowledge_base.md` | C1: prompt + KB to configure the Dify app |
| Backend   | `backend/chatbot/` (`router.py`, `dify_client.py`, `sessions.py`, `context.py`) | C2 + C4: proxy route + role-scoped data |
| Frontend  | `frontend/src/components/chatbot/ChatWidget.jsx` + `chat-widget.css` | C3: floating chat widget |

---

## C1 — Dify app setup (manual, in the Dify console)

1. Create a **Chatbot** app in Dify (blocking mode is fine).
2. Paste `chatbot/system_prompt.md` into the app's Instruction/Prompt.
3. Create a **Knowledge Base**, upload `chatbot/faq_knowledge_base.md`, and attach
   it to the app so it answers product FAQ/how-to.
4. Publish the app and copy its **API key** and **base URL** into `.env`:
   ```
   DIFY_API_KEY=app-xxxxxxxx
   DIFY_BASE_URL=https://api.dify.ai/v1
   ```
   (For a self-hosted Dify, use your own base URL ending in `/v1`.)

Public mode safety: the system prompt forbids returning private factory data
unless a role-scoped "live data" block is supplied by our backend (logged-in mode).

## C2 — Backend proxy (`backend/chatbot/`)

- `POST /api/chatbot/message` — request `{ message, session_id }`, response
  `{ reply }`.
- `dify_client.py` calls Dify `POST {DIFY_BASE_URL}/chat-messages` (blocking) with
  `Authorization: Bearer {DIFY_API_KEY}`. Field mapping (verified against Dify's
  Chat App "Send Chat Message" docs): our `message` → Dify `query`; reply ←
  Dify `answer`. Handles timeouts (504) and upstream errors (502/400/503) with the
  uniform `{ "error": { "code", "message" } }` shape.
- `sessions.py` keeps `session_id → conversation_id` so multi-turn context works.

**Wiring (main developer, one line in `backend/app/main.py`):**
```python
from chatbot.router import router as chatbot_router
app.include_router(chatbot_router)
```
> The chatbot owner does not edit `app/main.py` (outside the chatbot folders). This
> single include is the only shared-file change needed; coordinate it with the main
> developer during merge.

## C3 — Chat widget (`frontend/src/components/chatbot/ChatWidget.jsx`)

- Floating bubble on every page; message list, input, loading + error states.
- Calls **only** `/api/chatbot/message` (never Dify). Attaches the auth token when
  present (logged-in mode); works logged out (public FAQ mode).
- Generates and stores a `session_id` in `localStorage`.
- Opens on click or on the `window` event `etm:open-chat` (so a page's "Ask AI"
  button can open it with `window.dispatchEvent(new Event("etm:open-chat"))`).

**Mounting (main developer):** render `<ChatWidget />` once near the app root (e.g.
in the top-level layout / `App`), replacing the placeholder `ChatBubble` mount:
```jsx
import ChatWidget from "./components/chatbot/ChatWidget.jsx";
// ...render <ChatWidget /> once so it appears on every page
```

## C4 — Logged-in, role-scoped answers (`backend/chatbot/context.py`)

- Public mode (no/invalid token): **no** private data — FAQ/how-to only.
- Logged-in mode: a short role-scoped facts block is attached to the Dify query,
  limited by role. **A buyer only ever sees their own orders/invoices.** Owner,
  store manager, floor supervisor and accountant get role-appropriate summaries.

---

## Run / test (networked host)

```bash
cd backend && ./run.sh            # installs httpx etc., starts API
# set DIFY_API_KEY / DIFY_BASE_URL in .env first
# then POST a message:
curl -s localhost:8000/api/chatbot/message \
  -H 'Content-Type: application/json' \
  -d '{"message":"How do I track an order?","session_id":"demo-1"}'
```

Without Dify keys set, the route returns a clean 503 ("Chatbot is not configured")
rather than crashing — handy for wiring the UI before Dify is ready.

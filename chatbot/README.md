# chatbot/

AI assistant (Dify) integration — **mini developer only**, branch `mini/chatbot`.

Rules:

- The browser must **never** call Dify directly. Flow:
  `Chat UI → our backend /api/chatbot/message → Dify API`.
- Keys live in `.env` (`DIFY_API_KEY`, `DIFY_BASE_URL`), used server-side only.
- Do not edit this folder if you are not the chatbot owner.

No feature code yet — placeholder for Phase 1 (Repo Foundation).

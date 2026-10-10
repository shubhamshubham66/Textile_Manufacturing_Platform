# PROJECT STATE — Context Ledger

Single source of truth for the current state of the project. Update this at the end
of every phase. Keep it short and factual.

**Last updated:** Phase 3 (Landing Page) — 10 Oct 2026
**Current phase:** Phase 3 — Landing Page (public)

---

## 1. Stack

Decided in Phase 2. **Odoo is not required.**

| Layer    | Choice                                        | Status    |
| -------- | --------------------------------------------- | --------- |
| Frontend | React + Vite                                  | Scaffolded |
| Backend  | FastAPI (Python)                              | Scaffolded |
| ORM      | SQLAlchemy 2.x                                | Done      |
| Database | SQLite (dev default) / PostgreSQL (demo/prod) | Modelled  |
| AI       | Dify (backend-only)                           | Confirmed |
| Odoo     | Not used                                      | Decided   |

---

## 2. Pages

- **Public landing page (`/`)** — Phase 3. Navbar (logo, section links, Demo,
  Login; hamburger on mobile), Hero, About (problem/solution + unique point),
  How it works (5 steps), Features (6 cards incl. idle-loss USP), AI section (3
  steps + sample chat), Footer (Contact, Demo login, GitHub). Floating chat-bubble
  **mount point only** (ChatBubble.jsx — mini dev fills it in).
- **Health check (`/health`)** — Phase 2 backend/DB check, kept for demos.
- Planned (later phases): Login, Orders, Yarn store, Production, Quality, Dispatch,
  Payments, Attendance & wages, Owner reports, Buyer portal, real chat bubble.

---

## 3. APIs

See `API_CONTRACT.md` for full request/response details.

| Method | Path                   | Purpose                        | Status  |
| ------ | ---------------------- | ------------------------------ | ------- |
| GET    | `/api/health`          | Liveness + DB connectivity     | Implemented (not runtime-tested here) |
| GET    | `/`                    | Service info / links           | Implemented (not runtime-tested here) |
| POST   | `/api/chatbot/message` | AI assistant (mini dev, later) | Defined (contract only) |

---

## 4. Database

**Status: schema designed + ORM models written; create/seed scripts ready.**
Approved as an ER diagram before creation (Phase 2, task 5).

Tables (18): `roles`, `users`, `buyers`, `orders`, `order_items`, `yarn_stock`,
`yarn_receipts`, `suppliers`, `purchase_orders`, `machines`,
`machine_status_logs`, `production_logs`, `rolls`, `quality_inspections`,
`dispatches`, `dispatch_items`, `invoices`, `payments`, `employees`, `attendance`,
`wages`.

- Models: `backend/app/models.py` (portable across SQLite + Postgres).
- Create tables: `python -m app.init_db`.
- Seed demo data: `python -m app.seed`.
- Idle-loss USP supported by `machine_status_logs` (start/end/reason) +
  `machines.hourly_cost`.
- No double dispatch: `dispatch_items.roll_id` is UNIQUE + roll status
  `dispatched`.

---

## 5. Auth & Roles

**Not implemented yet** (planned for a later phase). Roles seeded: owner,
store_manager, floor_supervisor, quality_inspector, accountant, buyer. Demo users
exist with placeholder password markers (`demo-hash:<pw>`); real hashing comes with
the auth phase. A buyer login links to a buyer via `users.buyer_id`.

---

## 6. Completed Features

- **Phase 1 — Repo Foundation:** docs, folders, `.gitignore`, `.env.example`,
  Git rules. (PR #1)
- **Phase 2 — Stack, Setup & Database (code complete, not runtime-tested here):**
  - Stack decided: React+Vite / FastAPI / SQLAlchemy / SQLite|Postgres. Odoo out.
  - Backend scaffold: `backend/app/{config,database,main,models,init_db,seed}.py`,
    `requirements.txt`, one-command `run.sh`, `/api/health` endpoint.
  - Frontend scaffold: Vite + React, health-check screen with loading/ok/error,
    `/api` proxy to backend.
  - DB models for all 18 tables + create + seed scripts.
- **Phase 3 — Landing Page (code complete, not runtime-tested here):**
  - Components: `Navbar, Hero, About, HowItWorks, Features, AiSection, Footer,
    ChatBubble` + pages `Landing`, `HealthCheck`. Path-based routing in `App.jsx`.
  - Responsive (hamburger menu on mobile; logo + Login stay visible), consistent
    design system in `index.css`.
  - All navbar links scroll to real sections (verified ids match). No dead buttons.
  - Chat bubble is a disabled mount point only — mini dev builds the chatbot.
  - JSX/CSS validated with Prettier (parses + formatted).

---

## 7. Pending Tasks

- Run end-to-end on a networked host: install deps, `init_db`, `seed`, start both
  servers, confirm health check shows DB connected. **(acceptance for Phase 2)**
- Auth + role-based access.
- Feature modules (Orders, Yarn, Production, Quality, Dispatch, Payments, Wages,
  Reports, Buyer portal).
- Chatbot `/api/chatbot/message` (mini dev, `backend/chatbot/`).
- Public landing page + floating chat bubble.

---

## 8. Known Bugs

- **Cannot run/verify in the current sandbox** (`INTEGRATIONS_ONLY`): PyPI, npm and
  a Postgres server are unreachable, so dependency install and the acceptance test
  were not executed here. Python modules were byte-compiled (syntax valid). Must be
  verified on a networked host.

---

## 9. Commands

```bash
# Backend
cd backend && ./run.sh                 # venv + install + run API (http://localhost:8000)
source .venv/bin/activate
python -m app.init_db                  # create tables
python -m app.seed                     # load demo data

# Frontend
cd frontend && npm install && npm run dev   # http://localhost:5173

# DB engine switch (optional): set DATABASE_URL in .env to a postgresql+psycopg2 URL
```

---

## 10. Deployment

Not decided. Local for development/demo. Backend 8000, frontend 5173; frontend
proxies `/api` to the backend.

---

## 11. Demo Flow

Target end-to-end narrative for live judging (the 6 scenes). Seed data is staged to
support it: 6 orders across stages (draft → closed), one low-stock yarn, idle +
breakdown machine logs for the idle-loss figure, 30 rolls with mixed quality
results, one completed dispatch + invoice + partial payment, employees + attendance
+ pending wages.

1. Yarn arrives → recorded in store, live stock updates.
2. New order → yarn-sufficiency check.
3. Production → assign machine, update status, log output; idle-loss shown in ₹.
4. Quality → inspect rolls (pass/rework/reject).
5. Buyer portal → track order status.
6. Dispatch → pick passed rolls, confirm (one transaction), print invoice.
7. Owner reports → cost per order, machine report, profit/loss.

# PROJECT STATE — Context Ledger

Single source of truth for the current state of the project. Update this at the end
of every phase. Keep it short and factual.

**Last updated:** Phase 10 (Testing & Polish) — 10 Oct 2026
**Current phase:** Phase 10 — Testing & Polish

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

| Method | Path                        | Purpose                          | Status  |
| ------ | --------------------------- | -------------------------------- | ------- |
| GET    | `/api/health`               | Liveness + DB connectivity       | Implemented (not runtime-tested here) |
| GET    | `/`                         | Service info / links             | Implemented (not runtime-tested here) |
| POST   | `/api/auth/login`           | Login → JWT + user + menu        | Implemented (not runtime-tested here) |
| GET    | `/api/auth/me`              | Current user + role menu         | Implemented (not runtime-tested here) |
| POST   | `/api/auth/logout`          | Stateless logout                 | Implemented (not runtime-tested here) |
| GET    | `/api/auth/_demo/payments`  | Demo 403 enforcement (owner/accountant only) | Implemented (not runtime-tested here) |
| GET    | `/api/orders`               | List orders (status filter + search) | Implemented (not runtime-tested here) |
| POST   | `/api/orders`               | Create order (draft) + yarn item | Implemented (not runtime-tested here) |
| GET    | `/api/orders/_meta/buyers`  | Buyers for the order form        | Implemented (not runtime-tested here) |
| GET    | `/api/orders/{id}`          | Order detail                     | Implemented (not runtime-tested here) |
| GET    | `/api/orders/{id}/check-yarn` | Yarn enough / short by X       | Implemented (not runtime-tested here) |
| POST   | `/api/orders/{id}/confirm`  | Confirm order (→ production)     | Implemented (not runtime-tested here) |
| GET    | `/api/yarn/stock`           | Live stock + low-stock flag      | Implemented (not runtime-tested here) |
| POST   | `/api/yarn/receipts`        | Receive yarn (auto stock update) | Implemented (not runtime-tested here) |
| POST   | `/api/yarn/purchase`        | Raise purchase order             | Implemented (not runtime-tested here) |
| GET    | `/api/yarn/purchase`        | List purchase orders             | Implemented (not runtime-tested here) |
| GET    | `/api/yarn/suppliers`       | Suppliers for forms              | Implemented (not runtime-tested here) |
| GET    | `/api/production/machines`  | Machines: status, order, progress | Implemented (not runtime-tested here) |
| GET    | `/api/production/orders`    | Assignable orders                | Implemented (not runtime-tested here) |
| POST   | `/api/production/machines/{id}/assign` | Assign order + stage  | Implemented (not runtime-tested here) |
| POST   | `/api/production/machines/{id}/status` | Change status (logs + reason) | Implemented (not runtime-tested here) |
| POST   | `/api/production/output`    | Log metres produced              | Implemented (not runtime-tested here) |
| GET    | `/api/production/output/today` | Today's output per machine    | Implemented (not runtime-tested here) |
| PATCH  | `/api/production/machines/{id}/hourly-cost` | Set hourly cost | Implemented (not runtime-tested here) |
| GET    | `/api/production/idle-loss` | Idle loss ₹ per machine + total (USP) | Implemented; math verified vs hand calc |
| POST   | `/api/quality/rolls`        | Create roll (Pending)            | Implemented (not runtime-tested here) |
| GET    | `/api/quality/rolls`        | List rolls (status/order filter) | Implemented (not runtime-tested here) |
| POST   | `/api/quality/rolls/{id}/inspect` | Pass/rework/reject + defect | Implemented (not runtime-tested here) |
| GET    | `/api/quality/defect-report` | Counts by defect/machine/order  | Implemented (not runtime-tested here) |
| GET    | `/api/dispatch/orders`      | Orders with passed rolls         | Implemented (not runtime-tested here) |
| GET    | `/api/dispatch/orders/{id}/pickable` | Passed, undispatched rolls | Implemented (not runtime-tested here) |
| POST   | `/api/dispatch/confirm`     | One-txn dispatch + invoice       | Implemented; invoice math verified; UNIQUE guard |
| GET    | `/api/dispatch`             | List dispatches                  | Implemented (not runtime-tested here) |
| GET    | `/api/dispatch/finished-stock` | On-shelf vs dispatched        | Implemented (not runtime-tested here) |
| GET    | `/api/dispatch/invoice/{id}` | Invoice JSON (rolls listed)     | Implemented (not runtime-tested here) |
| GET    | `/api/dispatch/invoice/{id}/pdf` | Invoice PDF                 | Implemented (not runtime-tested here) |
| POST   | `/api/payments/buyer`       | Record buyer payment (invoice status) | Implemented (not runtime-tested here) |
| POST   | `/api/payments/supplier`    | Pay supplier                     | Implemented (not runtime-tested here) |
| GET    | `/api/payments/dues`        | Pending dues (receivable/payable) | Implemented; ties out vs seed |
| POST   | `/api/attendance`           | Mark attendance                  | Implemented (not runtime-tested here) |
| POST   | `/api/wages/calculate`      | Calculate wages (days×rate+OT)   | Implemented (not runtime-tested here) |
| POST   | `/api/wages/{id}/pay`       | Pay wage                         | Implemented (not runtime-tested here) |
| GET    | `/api/reports/cost-per-order` | Yarn+wages+machine per order   | Implemented (not runtime-tested here) |
| GET    | `/api/reports/machines`     | Output + idle loss per machine   | Implemented (not runtime-tested here) |
| GET    | `/api/reports/profit-loss`  | Month P&L                        | Implemented; ties out vs seed |
| GET    | `/api/reports/dashboard`    | Owner dashboard cards            | Implemented (not runtime-tested here) |
| GET    | `/api/buyer/orders`         | My orders (own only) + stage/ETA | Implemented; isolation test written |
| GET    | `/api/buyer/orders/{id}`    | Track my order (404 if not mine) | Implemented; isolation test written |
| GET    | `/api/buyer/invoices`       | My invoices (own only)           | Implemented; isolation test written |
| GET    | `/api/buyer/invoices/{id}/pdf` | My invoice PDF (404 if not mine) | Implemented; isolation test written |
| POST   | `/api/chatbot/message`      | AI assistant (mini dev, later)   | Defined (contract only) |

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

**Implemented (Phase 4).**

- Passwords hashed with **bcrypt** (passlib). Stateless **JWT** bearer auth
  (`JWT_SECRET` in `.env`, insecure dev default).
- Endpoints: `/api/auth/login`, `/api/auth/me`, `/api/auth/logout`, plus a demo
  protected endpoint `/api/auth/_demo/payments`.
- **One RBAC config** (`backend/app/rbac.py`) defines role → menu and (derived)
  resource → allowed roles. Frontend renders menus from `/api/auth/me`; backend
  enforces with `require_resource(...)` / `require_roles(...)` → **403** when
  forbidden. No per-role duplicated code.
- Roles: owner, store_manager, floor_supervisor, quality_inspector, accountant,
  buyer. Demo users seeded (credentials in README "Demo logins"). Buyer login links
  to a buyer via `users.buyer_id`.

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
- **Phase 4 — Login & Roles (code complete, not runtime-tested here):**
  - Backend: `security.py` (bcrypt + JWT), `rbac.py` (one role→menu/resource
    config), `deps.py` (`get_current_user`, `require_roles`, `require_resource`),
    `routers/auth.py` (login/me/logout + demo 403 endpoint). Uniform error shape in
    `main.py`. Seed now bcrypt-hashes demo passwords.
  - Frontend: `pages/Login.jsx` (validation + clear errors + demo-fill),
    `pages/AppShell.jsx` (sidebar from backend menu, topbar: bell placeholder,
    profile name+role, Logout), `auth/AuthContext.jsx`, `lib/api.js`. Routing in
    `App.jsx` guards `/app` (→ `/login`) and `/login` (→ `/app`).
  - API_CONTRACT updated with auth endpoints + role map. README "Demo logins".
  - Backend byte-compiles; frontend validated with Prettier.
- **Phase 5 — Orders & Yarn Store (code complete, not runtime-tested here):**
  - Backend: `routers/orders.py` (list/create/detail/check-yarn/confirm + buyers)
    and `routers/yarn.py` (stock/receipts/purchase/suppliers). All role-guarded via
    `require_resource`. Config adds `YARN_KG_PER_METER` (0.2) + default reorder
    level. Yarn receipt updates stock in one transaction and can close a PO.
  - Frontend: `pages/app/{Orders,YarnStore,Stock,Purchase}.jsx` with validation,
    loading/empty/error states. AppShell now dispatches menu resources → real pages
    (others still prototype placeholders).
  - API_CONTRACT: orders + yarn endpoints documented.
  - Yarn estimation: required_kg = quantity_meters × 0.2 (configurable), matched by
    colour against stock.
- **Phase 6 — Production & Idle Loss (code complete; math verified):**
  - Model: `machines` gains `current_order_id` + `current_stage`.
  - Backend: `services/production.py` (progress + idle-loss math) and
    `routers/production.py` (machines list, assign, update-status with log
    open/close + required reason for idle/breakdown, log output, today's output,
    hourly-cost PATCH, idle-loss dashboard with top reasons).
  - Frontend: `pages/app/Machines.jsx` (status/order/progress + inline assign,
    update-status, hourly-cost) and `pages/app/Production.jsx` (idle-loss card,
    log output, today's output).
  - Idle-loss USP: loss = Σ(idle/breakdown window hours) × hourly_cost. **Verified
    against hand calculations** (standalone assertion run). Order progress =
    produced metres / ordered metres (capped 100).
  - Seed: running machines assigned current orders/stages matching their output.
- **Phase 7 — Quality & Dispatch (code complete; critical math verified):**
  - Backend: `routers/quality.py` (new roll/list/inspect/defect-report) and
    `routers/dispatch.py` (pickable/confirm/list/finished-stock/invoice JSON+PDF),
    plus `services/dispatch.py` (the one-transaction confirm).
  - **No double dispatch — two layers:** app check (roll must be `pass`, reject
    `dispatched`) + DB `UNIQUE(dispatch_items.roll_id)`; IntegrityError → 409 and
    full rollback.
  - Only `pass` rolls are pickable/dispatchable (backend-enforced, not just UI).
  - Invoice auto-created in the same txn: `metres × rate + tax` (tax rate
    configurable, demo 5%). **Invoice math verified vs hand calc.**
  - PDF invoice via reportlab lists the exact rolls. Dispatch added to Store
    manager menu (new `dispatch` resource).
  - Frontend: `pages/app/Quality.jsx` (new roll, inspect modal, Pending/Passed/
    Failed tabs, defect report) and `pages/app/Dispatch.jsx` (pick passed rolls,
    confirm, finished stock, dispatch list, print invoice PDF).
- **Phase 8 — Payments, Attendance & Reports (code complete; money math verified):**
  - Backend: `routers/payments.py` (buyer/supplier payments, dues, invoice-status
    recompute), `routers/wages.py` (attendance upsert, wage calc days×rate+OT, pay),
    `routers/reports.py` + `services/reports.py` (cost-per-order, machine report,
    P&L, dashboard).
  - Costing: cost/order = yarn (linked receipts) + wages + machine, where wages &
    machine cost are allocated by each order's output-metre share. P&L = payments in
    − supplier out − wages.
  - **Verified vs seed by hand:** invoice ₹44,100; buyer-in ₹26,460; supplier-out
    ₹180,000; wages ₹10,350; P&L −₹163,890; buyer due ₹17,640.
  - Frontend: `pages/app/{Payments,Attendance,Wages,Reports,Dashboard}.jsx`.
    Dashboard has KPI cards + a CSS bar chart (no chart dependency). AppShell now
    renders all 13 module resources.
- **Phase 9 — Buyer Portal (code complete; isolation logic verified + test):**
  - Backend: `deps.get_current_buyer` (buyer + linked buyer_id, else 403) and
    `routers/buyer.py` (my orders w/ stage+progress+ETA, track one order, my
    invoices, invoice PDF). **Every query scoped to `buyer_id`**; cross-buyer
    single-resource access → 404 (no existence leak).
  - Stage flow Confirmed→Weaving→Dyeing→Checking→Ready to ship→Shipped mapped from
    order status; progress reuses the production service.
  - **Explicit cross-buyer test:** `backend/tests/test_buyer_isolation.py` (two
    buyers; each sees only their own orders/invoices; cross access → 404). Logic
    also verified by a standalone simulation.
  - Frontend: `pages/app/MyOrders.jsx` (list + track stepper + Ask AI) and
    `pages/app/Invoices.jsx` (list + PDF). ChatBubble is now openable (mount point
    only) and rendered on app pages too; "Ask AI" fires `etm:open-chat`.
  - NOTE: chatbot widget itself is still the mini developer's — not implemented.
- **Phase 10 — Testing & Polish (no new features):**
  - `backend/tests/flow_simulation.py` — DB-logic end-to-end of the full demo flow
    + edge cases (**19/19 pass**): new order, yarn check, receive yarn, assign,
    output/progress, rolls, inspect, atomic dispatch+invoice, buyer payment, P&L;
    edges: non-passed dispatch, double dispatch (app + DB UNIQUE), negative qty,
    empty list, wrong login, cross-buyer access.
  - Audits: every endpoint except `/login` is role-guarded (403); frontend lint =
    0 undefined-var errors; prettier clean; no dead buttons / placeholder prose.
  - Fixes (smallest reliable): notifications bell dead-disabled → working
    empty-state popover; flow-sim empty-list guard. No unrelated changes.
  - Polish: one-click **Try as owner / buyer** demo login + full one-click role
    list on the Login page. `docs/TEST_REPORT.md` added.

---

## 7. Pending Tasks

- **Run live on a networked host** (the only remaining gate — everything is
  code-complete + DB-logic/static verified): install deps, `init_db`, `seed`, start
  both servers, run `pytest`, and do the browser/HTTP demo pass.
- Wire the chatbot (2 shared-file lines — see `chatbot/README.md`) + create the
  Dify app with the provided prompt/KB and keys.
- Optional: move session store / machine-cost allocation to stricter models if
  desired (documented assumptions).

---

## 8. Known Bugs

- **Live app not runnable in this sandbox** (`INTEGRATIONS_ONLY`): PyPI/npm/Postgres
  unreachable, so real HTTP + browser + PDF + Dify were **not** executed here.
  Verified instead by DB-logic simulation (19/19), compilation, and lint. Must be
  confirmed on a networked host.
- No open logic bugs found in Phase 10. The notifications-bell dead button was
  fixed.

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

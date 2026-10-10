# PROJECT STATE — Context Ledger

Single source of truth for the current state of the project. Update this at the end
of every phase. Keep it short and factual.

**Last updated:** Phase 11 (Live run, fixes & deploy prep) — 10 Oct 2026
**Current phase:** Phase 11 — Deploy (Render + Vercel)

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
| POST   | `/api/chatbot/message`      | AI assistant proxy → Dify        | Wired; tested live with a stub Dify (public + role-scoped) |

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
- Endpoints: `/api/auth/login`, `/api/auth/me`, `/api/auth/logout`. (The Phase 4
  demo endpoint `/api/auth/_demo/payments` was removed once the real
  `/api/payments/*` endpoints shipped; they enforce the same 403.)
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
- **Phase 11 — Live run, fixes & deploy prep (all executed on a networked host):**
  - Ran for real on SQLite **and PostgreSQL 17**: HTTP smoke test of every
    endpoint + full demo flow + RBAC/edge cases **72/72 pass on both**; pytest
    4/4; flow simulation 19/19; all 17 role pages open in a browser with no errors.
  - Fixed: login used `EmailStr` → app failed to import (`email-validator`
    missing) and every `@everest.test` demo login returned 400. Now a plain,
    trimmed, lowercased string.
  - Fixed: PostgreSQL in a non-UTC server timezone shifted every timestamp
    (idle-loss hours wrong). Sessions are pinned to UTC.
  - Fixed: buyer portal / chatbot showed 0% for orders already past production
    (now 100% from `in_quality` onward). Negative money shows as `−₹1,58,890`;
    stage labels readable.
  - Startup creates tables and loads demo data **only if the DB is empty**
    (`AUTO_CREATE_TABLES`, `SEED_IF_EMPTY`); restarts keep data.
    `postgres://` / `postgresql://` URLs normalised for psycopg2.
  - Chatbot wired: `chatbot_router` included; `ChatBubble` renders the real
    `ChatWidget`. Without Dify keys the route returns a clean 503.
  - Deploy config: `render.yaml` (API + free Postgres), `frontend/vercel.json`
    (`/api` → Render, SPA fallback), `DEPLOY.md`.

---

## 7. Pending Tasks

- Deploy: Render Blueprint, then Vercel (see `DEPLOY.md`). Update the `/api`
  rewrite in `frontend/vercel.json` if Render's service URL has a suffix.
- Create the Dify app (prompt + KB in `chatbot/`) and set `DIFY_API_KEY` on Render.
- Optional: move session store / machine-cost allocation to stricter models if
  desired (documented assumptions).

---

## 8. Known Bugs

- No open bugs from the Phase 11 live run. Not yet tested against the real Dify
  service (needs the Dify app + key).
- (Resolved in Phase 13) The seed previously showed a loss and yarn ₹0 per order.
  The October-2026 seed now nets a small **profit (+₹15,610)** and links yarn
  receipts to orders so cost-per-order shows real yarn cost.

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

Render (FastAPI + free PostgreSQL via `render.yaml`) and Vercel (frontend, root
`frontend/`, `vercel.json` proxies `/api` to Render). Steps in `DEPLOY.md`.
Locally: backend 8000, frontend 5173; Vite proxies `/api` to the backend.

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

## Phase 12 — Landing page redesign
- New public landing look (indigo/haldi palette, Archivo + IBM Plex Sans), styles in `frontend/src/landing.css`, all scoped under `.lp` / `lp-*`.
- Hero has a live-looking floor board with a ticking ₹ idle-loss counter (respects reduced motion).
- Sections: About (before → after), How it works (5 steps with roles), Features (idle-loss USP), AI help (opens chat bubble), Footer with demo logins.
- Mobile: hamburger menu, logo + Login always visible; checked at 1366px and 390px with no horizontal overflow.

## Phase 12b — Landing hero with mill photo
- Hero now: soft grid panel, "One system to run our whole mill" (single-company wording), Login + "See what it does" buttons, mill-floor photo on the right (`frontend/public/images/mill-floor.jpg`, 270 KB).
- Rest of the landing (About, How it works, Features, AI, Footer) unchanged.
- About section: weaving-floor photo (`frontend/public/images/weaving-floor.jpg`) on the left with a numbered list of 5 points on the right; old before/after list removed.

## Phase 12c — Landing sections per spec
- Hero buttons: Login + Watch demo (scrolls to How it works).
- About: "About Everest Textile Mills" intro, The problem (5 points), The solution box.
- How it works: staircase cards over a mill photo (`frontend/public/images/winding-floor.jpg`), last step (Ship) dark.
- New demo strip (`CtaStrip.jsx`): Try as owner / Try as buyer → `/login?demo=owner|buyer` logs straight in.
- Login page: `?demo=<role>` auto-signs in with that demo account.

## Phase 12d — How it works: warehouse photo
- Background is now a warehouse photo (`frontend/public/images/warehouse.jpg`), kept bright; heading at the top, five equal cards in the lower half.
- Cards are flat, muted colours (cotton, haldi, sage, madder, blue-grey) instead of the glass staircase; subheading bold for readability.

## Phase 12e — Owner section photo
- "What the owner gets" section: photo of two managers (`frontend/public/images/owners-review.jpg`) shown in full, idle-loss card overlapping its lower edge (builds on PR #19's layout).
- Added the sixth benefit "Attendance, no register" (new `IconCalendar`); "lost today" label made readable on the amber chip.

## Phase 13 — Owner month-end workflow (Dashboard, Reports, Orders, Payments)

**One costing definition (used on every owner screen):**
- Order cost = yarn + wages + machine.
  - Yarn = Σ receipts linked to the order (kg × rate); fallback = required-kg ×
    average purchase rate for that yarn (fixes "Yarn ₹0").
  - Wages = total month wages × order's share of production output (m).
  - Machine = Σ `machines.power_overhead_cost` (power+overhead only, **no operator
    wage**) × output share. New column `power_overhead_cost` ≈ 60% of `hourly_cost`;
    falls back to 60% of `hourly_cost` when unset. This stops wages being counted
    twice.
- Order margin (estimate) = revenue (invoiced, else output×rate) − cost. Labelled
  "estimate".
- **Month net (cash basis)** = buyer payments received − supplier bills paid −
  wages, within the month. The Dashboard card and Reports › Profit/loss use this
  one definition, so they match exactly.
- Idle loss = idle+breakdown hours × full `hourly_cost` (unchanged).

**What changed:**
- Backend `services/reports.py`: month-windowed; real yarn cost; machine cost from
  `power_overhead_cost`; new `wages_report` + `idle_loss_by_reason`; cash-basis P&L.
- Backend `routers/reports.py`: every endpoint takes `?start&end` (defaults to the
  current month); new `GET /api/reports/wages`; dashboard returns `machine_count`
  and `idle_loss_by_reason`.
- Backend `routers/payments.py`: supplier payment rejects amounts over the
  outstanding bill unless `is_advance`; dues now carry dates + `days_overdue`.
- Backend `routers/orders.py`: new `GET /api/orders/{id}/track` (owner) for the
  order tracker (stage, progress, late flag, rolls + inspection + machine).
- Backend `models.py`: `machines.power_overhead_cost`.
- Seed: one realistic **October 2026** month; receipts linked to orders; small
  cash **profit (+₹15,610)**; `backend/tests/verify_month_math.py` checks the
  numbers by hand (runs without FastAPI/network).
- Frontend: month selector on Dashboard + Reports; Dashboard "Profit or loss
  (this month)" card with sign-aware colour and "this month, N machines" copy
  (removed "our unique metric"); waterfall + stage bars (clickable) + idle-reason
  chart; Reports cost-per-order (real yarn, totals row, stacked chart), machine
  report (running h, top reason, totals row, output chart), month P&L summary,
  new **Wages** tab; Payments due tracker (ageing) + styled selects + Indian money
  (2 dp) + supplier advance checkbox + dates in history; Orders dd/mm/yyyy
  deadline, grey disabled "Confirmed", order tracker side panel.
- Shared, **additive** files touched: `frontend/src/lib/format.js` (added `qty`,
  `hrs`, `ddmmyyyy`, month helpers, 2-dp `inr`; existing exports kept) and
  `frontend/src/pages/AppShell.jsx` (an inert `etm:navigate` listener). New files:
  `frontend/src/owner.css`, `components/owner/MonthPicker.jsx`,
  `components/owner/Charts.jsx`.

**Charts:** dependency-free SVG/CSS (no chart library added — npm registry is
blocked in the build sandbox, and this keeps the app installable). Each chart has
a title, units, tooltips and an aria-label text alternative.

**Known limits / not verified:**
- Backend was **not run** in this environment (no PyPI/npm network to install
  FastAPI/Vite). Logic verified by `verify_month_math.py` (pure Python) and
  prettier parse of all JSX; HTTP/browser testing is pending on a networked host.
- Machine `power_overhead_cost` 60% split is a documented assumption; adjust per
  machine if real power/overhead figures are available.
- Photos: owner empty states use text only (no new images added); wire real mill
  photos into empty states when files are provided.

## Phase 13 — Signup with email OTP
- New page `/signup` (`frontend/src/pages/Signup.jsx`): Role (Admin = owner, Store manager, Floor supervisor, Quality inspector, Accountant, Buyer) → Name → Email → Send OTP → Verify → New + Confirm password → Create account. Stays on a success screen with a "Go to sign in" button (no auto-redirect). Login page links to it.
- Backend `backend/app/routers/signup.py`: `POST /api/auth/signup/send-otp`, `/verify-otp`, `POST /api/auth/signup`. 6-digit code stored only as a bcrypt hash in new table `email_otps`; 10-min expiry, 5 wrong tries, 60 s resend wait, single use. Verify returns a short-lived email token that cannot be used as a login token. Buyer signups also create their buyer record.
- Email via Brevo HTTP API (`backend/app/services/email.py`); needs `BREVO_API_KEY` + `MAIL_FROM_EMAIL` on Render. `SIGNUP_DEV_OTP=true` shows the code on screen for local dev only.
- Tests: `backend/tests/test_signup.py` (8 cases).

## Phase 13b — Fix: owner reports HTTP 500 on Render
- Cause: PR #21 added `machines.power_overhead_cost`; the Render database was created earlier and `create_all` never adds columns to existing tables, so every query on machines failed ("column does not exist") — owner dashboard, reports, floor machines, quality rolls.
- Fix: `backend/app/schema_sync.py` runs after `create_all` on startup and only ADDS missing model columns (with their default). No drops or changes. Test: `backend/tests/test_schema_sync.py`.
- App pages now follow the URL (`/app/reports` etc.): refresh stays on the page, Back works, deep links open the right page.
- Verified on a Postgres DB built with the old code: 0 errors across all 17 role pages.

## Phase 14 — Real-time data workflow
- Live updates over Server-Sent Events. `backend/app/live.py` turns committed changes (machine status, order stage, yarn stock + low-stock crossing, new rolls / inspections, production logs, payments, invoices/dispatch, attendance/wages) into events; a rolled-back change sends nothing. `backend/app/routers/live.py`: `POST /api/live/ticket` (60 s ticket, not a login token), `GET /api/live/stream?ticket=` (per-role filtered; buyers only see their own orders/payments; 15 s heartbeat), `GET /api/live/alerts` (what needs attention now).
- Frontend `src/live/LiveContext.jsx`: one stream per tab, auto-reconnect with backoff + full reload after reconnect. `useLive(topics, load)` on all 14 data pages reloads quietly (no "Loading…" flash). Top bar: "● Live · updated Xs ago"; bell with unread count and list; short toasts for alerts.
- In-process event bus: fine for the single Uvicorn worker on Render; several workers would need Redis pub/sub.
- Tests: `backend/tests/test_live.py` (6). Verified with separate owner / floor / quality / buyer browsers on Postgres.

## Phase 13c — Signup without role
- `/signup` now asks only Name, Email, OTP, New + Confirm password. Every new account is a Buyer with its own buyer record (least access). The API ignores any `role` sent, so nobody can make themselves Admin. Staff roles are to be given by the owner.

## Phase 15 — Owner login + Team (create manager)
- Owner account comes from `OWNER_EMAIL` / `OWNER_PASSWORD` / `OWNER_NAME` env vars (`backend/app/bootstrap.py`): created on start, password re-synced if changed, promoted to owner if that email existed with another role. Password stored as a bcrypt hash only.
- New role `manager` (menu: Home placeholder for now); `ensure_roles` adds missing roles to an existing database.
- Users have an optional `login_id` (e.g. MGR-001; column auto-added on old DBs by schema_sync). Login accepts Gmail or login ID.
- Owner menu has **Team** (`/app/team`): create manager (name, login ID, password + confirm, optional Gmail) and list managers. Dashboard has a "＋ Create manager" button. API: `GET/POST /api/team/managers` (owner only).
- Tests: `backend/tests/test_team.py` (4); 25 backend tests pass.

## Phase 16 — Owner month-end audit and fixes
Audit of R1–R7 (owner scene) found four wrong/partial items; fixed:
- **R1 / R3 / R5 month window:** cost per order, machine hours, idle loss (report, Dashboard card and by-reason chart) now count only what falls inside the selected month. Before, an empty month (Sep 2026) showed ₹1,58,800 of yarn cost and ₹3,400 idle loss.
- **R1 machine cost:** was Σ machine ₹/hr × output share (an hourly rate used as a total). Now running hours in the month × power+overhead ₹/hr, split by the machine's metres per order.
- **R1 yarn:** linked receipts received in the month; orders with no linked receipt get a marked estimate (was "—"/₹0 for ORD-2007).
- **R5 month net:** used wages accrued (₹10,350) while labelled "wages paid". Now wages PAID in the month (₹8,100); wages due shown separately. October net ₹17,860.
- **R7 seed:** no future-dated records (production 11–12 Oct, payment 15 Oct, wages paid 13 Oct moved to ≤ 10 Oct); running windows behind every production log; status windows closed in the past so figures don't drift.
- Wages split across orders rounds to paise with the remainder on the largest share, so per-order wages add up exactly to the total.
- UI: "est" marker on estimated yarn, wages-due line on Dashboard and Profit / loss, sticky table headers on Reports.
- Definitions: `backend/app/services/reports.py` docstring and `docs/OWNER_MONTH_END_HANDCHECK.md`. Tests: `backend/tests/test_owner_reports.py` (acceptance checks 1–7); `backend/tests/verify_month_math.py` (plain arithmetic).
- Shared file touched (additive): `backend/app/services/production.py` gets `log_hours_in_window` and an optional `window` on `idle_loss_for_machine` (floor screens call it without a window, unchanged).


## Task 3 — Master data screens (owner)

- New owner resource **`master_data`** (menu "Master data") + router
  `backend/app/routers/master.py`: add + edit **buyers, suppliers, machines,
  employees**, and **correct a yarn receipt**. Owner only (403 for others).
  - Machine: `power_overhead_cost` must be ≤ `hourly_cost` (the rest is the
    operator wage).
  - Receipt correction adjusts stock by (new − old) kg; never below zero.
- Orders: **edit** (`PUT /api/orders/{id}`) and **cancel**
  (`POST /api/orders/{id}/cancel`) — allowed only before production
  (`draft`/`confirmed`), else 409. New order status **`cancelled`**.
- `live.py`: events for new machine + buyer/supplier/employee/machine edits
  (refresh the relevant screens; new machine notifies the owner).
- Frontend: `pages/app/MasterData.jsx` (tabs: Buyers / Suppliers / Machines /
  Employees / Yarn receipts, each with add/edit dialogs, validation, live
  refresh). Orders page gains Edit (dialog) + Cancel. `format.js` labels
  `cancelled`.
- Tests: `backend/tests/test_master_data.py` (CRUD, 409 duplicates, machine
  power ≤ hourly, RBAC 403, order edit/cancel-before-production rules, receipt
  stock adjust).
- Not runtime-tested in this sandbox (no PyPI/npm); byte-compiles + prettier
  clean; run `pytest tests` on a networked host.

## Task — Owner dashboard as one read-only "closing the books" screen

- The owner **Dashboard** is now a single read-only screen (sections A–G):
  month selector + "Updated hh:mm:ss" + Refresh + **30s visible polling** (plus
  the existing SSE live refresh); Month summary band (buyer in − bills − wages
  paid = net) with a plain **verdict sentence** and a waterfall; **order history**
  with group chips (Awaiting/Confirmed/Ongoing/Completed/Cancelled) + counts,
  search, progress %, late flag, row→**order slip** side panel; **cost per order**
  (+ Margin %); **machine production** (+ totals + chart); **money in one place**
  (wages / raw-material bills / buyer payments) whose totals **equal the band
  exactly**.
- Owner **Orders page is now READ-ONLY**: no New-order form, Check yarn, Confirm,
  Edit or Cancel — only list + Track. (Backend order endpoints are untouched, so
  nothing breaks; they are just not surfaced to the owner.)
- New owner-only (resource "reports") read-only endpoints in
  `routers/reports.py` + `services/owner_closing.py`:
  `/api/reports/orders`, `/orders/{id}/slip`, `/orders/{id}/slip/pdf` (reportlab,
  no new dependency), `/bills`, `/buyer-payments`. All month-windowed, 403 for
  non-owner.
- Seed: added **ORD-2008 (cancelled)** so the Cancelled group has real data;
  net stays +₹17,860. Hand-check table extended in
  `docs/OWNER_MONTH_END_HANDCHECK.md`.
- Frontend new files: `components/owner/usePolling.js`,
  updated `pages/app/Dashboard.jsx`, `pages/app/Orders.jsx`, `owner.css`
  (band/chips/verdict/slip + a **print stylesheet** so the slip prints cleanly).
- Tests: `backend/tests/test_owner_closing.py` (history groups+counts, slip ==
  cost, band == section G, empty month zeros, slip PDF is a PDF, non-owner 403).

### Known limits (this task)
- **No order-level "Rejected" status / reject reason / created_by / confirmed_by**
  yet — the owner history shows a "Cancelled" group, not "Rejected". A reject
  flow + store-manager order create/confirm/reject + owner 403 on write is a
  separate change (not done here, per the read-only-only scope agreed).
- Not runtime-tested in this sandbox (no PyPI/npm). Byte-compiles, prettier
  clean, band↔section-G tie-out verified by a standalone script. Run
  `pytest tests` on a networked host.
- Render junk records (ORD-2007-type test rows, ₹20cr supplier payment) are
  removed via `RESET_DATA=empty` (PR #31) or by voiding (PR #30) — no new code.

## Task — Production Manager dashboard

New role **`production_manager`** (menu label "Production manager") with its own
12-screen control panel for the production floor. Built by cloning the
Supermanager pattern (RBAC-driven menu + `require_resource` guards + live SSE +
activity log). No other dashboard, auth, DB schema or the tech stack changed.

**Backend**
- `rbac.py`: added `ROLE_PRODUCTION_MANAGER`, 12 menu items with their own
  `pm_*` resources (Dashboard, Production Orders, Production Planning,
  Production Stages, Machine Management, Worker & Task Assignment, Production
  Monitoring, Material Requests, QC Handover, Production Reports, Notifications,
  Activity Logs). `RESOURCE_ACCESS` is derived, so each `pm_*` resource is
  reachable only by this role (verified: other roles get 403).
- `departments.py`: production department is now run by the production manager
  (`DEPT_ROLE["production"]`), so the auto "Produce …" instruction on order
  confirmation routes to it; the floor supervisor still shares the machine
  screens.
- `services/prod_manager.py`: read-only aggregations (dashboard cards, order
  rows, machine rows, material shortages vs confirmed-order needs, QC-pending
  batches, rework/reject rolls, production tasks). Reuses the existing
  production service for progress + idle-loss math. All figures from live
  tables — no dummy values.
- `routers/prod_manager.py` (`/api/prod/*`): dashboard; orders (read-only);
  planning (`POST /plan` assigns machine+stage+target, moves confirmed→in
  production); stages; machines (`POST /machines/{id}/status` with required
  reason for idle/breakdown); workers + tasks (create / assign / status, writes
  `TaskUpdate`); monitoring + `POST /output` (metres + waste); materials
  (`POST /materials` raises a `PurchaseRequest` into the existing store/approval
  workflow + notifies Supermanager/store); QC handover (`POST /qc/handover`
  creates pending rolls and moves order→in_quality; `POST /qc/rework/{roll}`
  creates a rework task, only for rolls QC marked rework); reports; notifications
  + `POST /notify-delay` to the Supermanager; activity log. Every endpoint is
  guarded by `require_resource("pm_*")`. **Permission boundaries enforced on the
  backend:** this role has no endpoint to confirm orders, inspect/approve QC,
  edit payments, change stock quantities or dispatch — those stay 403 (verified).
- `live.py`: `production_manager` added to the machines/production/orders/yarn/
  quality/wages/tasks/purchase/notifications topics and to Task/QC notify lists,
  so its screens refresh and its bell fires on relevant commits. Writing
  ProductionLog/MachineStatusLog/Task/Roll already emits events via the existing
  flush hooks — no new topic needed.
- `main.py`: registered `prod_manager_router`.
- `bootstrap.ensure_roles` adds the role to existing/live DBs on restart (role
  is in `ALL_ROLES`); `seed.py` adds a demo login `production@everest.test` /
  `production123` (department=production), points production workers to it, and
  seeds three production worker tasks.

**Frontend** (reuses the shared `components/super/kit.jsx` and `super.css`)
- `pages/app/prod/ProdDashboard.jsx` — the seven required cards (Active orders,
  Today's target vs actual, Machine status, Worker tasks, Material shortages,
  Delayed orders, Pending QC handover) + lists.
- `pages/app/prod/ProdOrders.jsx` — Orders, Planning (plan dialog), Stages.
- `pages/app/prod/ProdFloor.jsx` — Machine management, Worker & task assignment,
  Monitoring (+ log-output dialog).
- `pages/app/prod/ProdOps.jsx` — Material requests, QC handover (+ rework),
  Reports, Notifications (+ report-a-delay), Activity logs.
- `AppShell.jsx`: imported the pages, added the 12 `pm_*` entries to `PAGES` and
  the role label. `components/super/icons.jsx`: added `pm_*` sidebar icons.

**Tests / verification**
- `backend/tests/test_prod_manager.py` (RBAC isolation across all 12 pages +
  403 for other roles, dashboard cards, planning + wrong-machine 400, machine
  status reason rule, worker task create/assign/status, output logging,
  material request → shows in store queue, QC handover → rolls pending + order
  in_quality, PM cannot inspect QC / see payments / dispatch, rework-only rule,
  reports, notify-delay).
- Not runtime-tested in this sandbox (no PyPI/npm to install FastAPI/Vite).
  Backend byte-compiles; RBAC/department wiring verified by a standalone script;
  all JSX prettier-clean. Run `pytest tests/test_prod_manager.py` on a networked
  host.

## Task — Sales & Dispatch Manager dashboard

New role **`sales_manager`** ("Sales & Dispatch manager") with a 13-screen panel,
built on the same RBAC-driven pattern as the Production Manager. Reuses the
existing atomic dispatch engine; no other dashboard, auth, DB schema or stack
changed beyond additive columns.

**Backend**
- `rbac.py`: `ROLE_SALES_MANAGER` + 13 isolated `sd_*` resources (Dashboard,
  Buyer Orders, Buyer Management, Order Status Tracking, QC-Approved Stock,
  Dispatch Planning, Create Delivery Challan, Dispatch History, Invoice Details,
  Delivery Confirmation, Notifications, Reports, Activity Logs). Verified only
  this role can reach them.
- `departments.py`: dispatch department now run by `sales_manager`.
- `models.py`: additive `Dispatch` columns — `challan_no`, `vehicle_no`,
  `transporter`, `driver_phone`, `delivery_address`, `delivery_note`,
  `delivered_at`, `dispatched_by_user_id`; new order status
  `partially_dispatched`. `schema_sync` adds the columns to existing DBs.
- `services/sales_manager.py`: read-only aggregations (dashboard cards, order
  rows with ready/dispatched metres, QC-approved stock, buyer dues, dispatch
  rows). All from live tables.
- `routers/sales_manager.py` (`/api/sales/*`): dashboard; buyer orders & buyer
  management (read-only); order tracking; QC-approved stock; dispatch planning
  + `POST /dispatch` which **reuses the existing atomic `confirm_dispatch`**
  (QC-'pass'-only, UNIQUE roll guard → no double dispatch, auto-invoice) then
  attaches challan + logistics and sets `dispatched`/`partially_dispatched`;
  dispatch history; read-only invoices; delivery confirmation
  (`/dispatch/{id}/status`, `/dispatch/{id}/deliver` → order `closed`=Delivered);
  notifications + read; reports; activity. Partial dispatch allowed only with an
  explicit `partial` flag; selecting non-approved rolls is rejected (400).
- Notifications wired to the required events: QC-pass now also notifies SALES +
  Supermanager (`live.py`); dispatch created → Supermanager + Accounts; delivery
  confirmed → Supermanager + Accounts (payment follow-up).
- `live.py`: `sales_manager` added to orders/quality/payments/notifications/tasks
  topics; Dispatch/Invoice events routed to it.
- `main.py`: registered `sales_manager_router`.

**Auth fix (also resolves the earlier "Not authenticated" / login failures)**
- `render.yaml`: `JWT_SECRET` changed from `generateValue: true` to `sync: false`
  — Render was regenerating the secret on every blueprint sync, invalidating all
  logged-in tokens (that was the real cause of the 401s). Set it once in the
  dashboard; sessions now survive deploys.
- `bootstrap.ensure_demo_managers`: ensures `production@everest.test` and
  `sales@everest.test` logins exist on ANY database (seed only runs on an empty
  DB), so these roles can be demoed/logged-in after a deploy. Called from
  `prepare_database` after `ensure_roles`.
- `seed.py`: adds the `sales_manager` role + demo login for fresh DBs.

**Frontend** (reuses the shared super kit + super.css)
- `pages/app/sales/SalesDashboard.jsx` — the seven required cards (Total Buyer
  Orders, Pending Dispatches, QC-Approved Stock, Orders Ready for Dispatch,
  Dispatched Orders, Delayed Deliveries, Pending Buyer Payments) + lists.
- `SalesOrders.jsx` — Buyer Orders, Buyer Management, Order Tracking, QC-Approved
  Stock.
- `SalesDispatch.jsx` — Dispatch Planning + Create Delivery Challan (roll picker
  with partial-dispatch acknowledgement + logistics), Dispatch History, Delivery
  Confirmation.
- `SalesOps.jsx` — Invoice Details (read-only + PDF link), Notifications, Reports,
  Activity Logs.
- `AppShell.jsx` + `icons.jsx`: 13 `sd_*` pages/icons + role label wired.

**Tests / verification**
- `backend/tests/test_sales_manager.py`: RBAC isolation (13 pages, 403 for other
  roles), dashboard cards, QC-only stock, full/partial dispatch + challan +
  invoice, double-dispatch blocked, non-approved roll rejected, delivery
  confirmation, read-only invoices, cannot-confirm-orders / cannot-edit-payments
  / cannot-inspect-QC, reports.
- Backend byte-compiles; RBAC/department wiring verified by a standalone script;
  all JSX prettier-clean. Not runtime-tested in the sandbox (no PyPI/npm); run
  `pytest tests/test_sales_manager.py` on a networked host.

## Task — Accounts & Finance Manager dashboard

New role **`accounts_manager`** ("Accounts & Finance manager") with a 12-screen
panel. Reuses the existing, proven finance backend (payments/wages/attendance/
reports) rather than duplicating it; adds its own `am_*` screens for the
dashboard, invoices, overtime, expenses, reports, notifications and activity.
No other dashboard/auth/stack changed beyond additive Payment columns.

**Backend**
- `rbac.py`: `ROLE_ACCOUNTS_MANAGER` + 12 menu items. Buyer Payments, Supplier
  Bills & Payments → existing `payments` resource; Worker Attendance →
  `attendance`; Salary & Wage Management → `wages` (so the existing endpoints
  work unchanged, with their duplicate/overpayment guards). New isolated
  `am_dashboard/am_invoices/am_overtime/am_prod_expenses/am_expenses/am_reports/
  am_notifications/am_activity` resources.
- `departments.py`: accounts department run by `accounts_manager`.
- `models.py`: additive `Payment` columns `category`, `note`, `reference`,
  `recorded_by_user_id` (schema_sync adds them to existing DBs) — used to record
  "other expenses" as outgoing payments so the P&L stays consistent.
- `services/accounts_manager.py`: dashboard cards (total sales, receivables,
  payables, monthly expenses, wages, profit/loss) + ageing receivables/payables,
  reusing `services/reports.py` so figures tie out with the owner's P&L.
- `routers/accounts_manager.py` (`/api/accounts/*`): dashboard; sales invoices
  (with dispatch link + PDF); overtime (derived from verified attendance >8h);
  production expenses (cost per order, read-only from reports); other expenses
  (`POST /expenses` records an outgoing payment in a txn + audit log +
  duplicate-reference guard; >=₹50k notifies the Supermanager); financial
  reports (`?period=day|month|year` → income/expense/cash-flow/P&L); notifications
  + read; activity. All guarded by `require_resource("am_*")`.
- `live.py`: `accounts_manager` added to payments/wages/notifications/tasks/orders
  topics. `sales_manager.py`: dispatch-invoice and delivery notifications now
  also go to the accounts_manager (payment follow-up).
- `main.py`: registered `accounts_manager_router`. `bootstrap.ensure_demo_managers`
  + `seed.py`: demo login `accounts-manager@everest.test` / `accounts123`.

**Frontend** (reuses the shared super kit; Buyer/Supplier Payments, Attendance,
Wages screens are the EXISTING Payments/Attendance/Wages pages via shared keys)
- `pages/app/accounts/AccountsDashboard.jsx` — the six cards (Total Sales,
  Pending Buyer Payments, Supplier Payments Due, Monthly Expenses, Worker Wages,
  Monthly Profit/Loss) + ageing receivables/payables + month-net band.
- `AccountsPages.jsx` — Sales Invoices, Overtime, Production Expenses, Other
  Expenses (record form + duplicate guard), Financial Reports (day/month/year),
  Notifications, Activity Logs.
- `AppShell.jsx` + `icons.jsx`: 8 `am_*` pages/icons + role label wired.

**Tests / verification**
- `backend/tests/test_accounts_manager.py`: RBAC isolation (am_* 403 for others),
  shared payment/wage endpoints usable, 12-item menu, six dashboard cards,
  invoices, production-expense totals, expense record + duplicate-reference 409,
  major-expense notification, day/month/year reports, cannot-confirm-orders /
  cannot-dispatch / cannot-inspect-QC.
- Backend byte-compiles; RBAC/department wiring verified by a standalone script;
  all JSX prettier-clean. Not runtime-tested in the sandbox (no PyPI/npm); run
  `pytest tests/test_accounts_manager.py` on a networked host.

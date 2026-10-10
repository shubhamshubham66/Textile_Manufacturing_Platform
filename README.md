# Everest Textile Mills — Textile Manufacturing System

One unified web platform that replaces notebooks, paper slips, registers and phone
calls for a fabric factory — covering yarn intake, production, quality, dispatch,
payments, wages, reporting, an AI assistant and a buyer portal.

> Hackathon project. Deadline: **11 Oct 2026, 10:00 AM IST**. Priority is a
> working, demonstrable, reliable product. Working features matter more than extra
> complexity.

---

## Problem Statement (summary)

Everest Textile Mills buys yarn, turns it into fabric on spinning, weaving and
dyeing machines, checks the fabric for defects, and sells finished rolls to buyers.
Many buyers order at once, each with its own fabric type, colour, quantity and
deadline. Today everything runs on paper:

- Raw material stock → notebook
- Machine and order status → checked by walking the floor
- Quality checks → paper slips
- Order updates for buyers → phone calls
- Worker attendance and wages → register

The result: orders get delayed, machines sit idle, and nobody knows the real cost
of a single roll of fabric.

### The 6 scenes the system must solve

1. **Yarn arrives at the gate** — record quantity, type, colour and linked order
   before it goes into the store. Show live stock, warn before it runs low, and
   show on a new order whether yarn is enough or more must be ordered.
2. **Production floor** — yarn moves through spinning, weaving and dyeing. Show
   which order is on which machine, how far along it is, which machines are idle or
   broken, and how much fabric each machine produced today.
3. **Quality check** — inspect rolls for defects (holes, colour mismatch, uneven
   weaving). Each roll is Pass, Rework or Reject, traceable to its order and
   machine. Keep a record of passed, failed and pending rolls.
4. **Buyer asks about an order** — the buyer can see whether the order is being
   woven, being checked, or ready to ship, without anyone going to the floor.
5. **Dispatch** — pack, count and load finished rolls for the right buyer in the
   right quantity, with a matching invoice. Show finished stock and what has gone
   out. No double dispatch.
6. **Owner closes the books** — actual cost per order, output per machine, total
   wages paid, raw-material bills and buyer payments come together to show profit
   or loss for the month.

### Our unique point

**Idle machine loss in money.** Log machine status (running, idle, breakdown) with
timestamps and reason, then show `idle hours × hourly cost` as a rupee loss on the
dashboard.

---

## Planned Modules

1. **Orders** — New order, Check yarn, Confirm order
2. **Yarn store** — Yarn received, Stock list (low-stock alert), Raise purchase
3. **Production** — Assign machine, Update status (running/idle/breakdown), Log output
4. **Quality** — New roll (linked to order and machine), Inspect roll (pass/rework/reject), Defect report
5. **Dispatch** — Pick rolls (only passed), Confirm dispatch (updates roll status, cuts stock and creates invoice in ONE transaction), Print invoice
6. **Payments** — Record buyer payment, Pay supplier, Pending dues
7. **Attendance & wages** — Mark attendance, Calculate wages, Pay wages (feeds into order cost)
8. **AI assistant (Dify)** — Ask question, Smart alerts, Daily owner summary
9. **Buyer portal** — Track order, View invoice, Ask AI
10. **Owner reports** — Cost per order, Machine report, Profit or loss

---

## Tech Stack

Decided in Phase 2 (Odoo is **not** required for this hackathon).

| Layer     | Choice            |
| --------- | ----------------- |
| Frontend  | React + Vite      |
| Backend   | FastAPI (Python)  |
| ORM       | SQLAlchemy 2.x    |
| Database  | SQLite (dev default) / PostgreSQL (demo/prod) — same models work on both |
| AI        | Dify (backend-only, via `/api/chatbot/message`) |
| Odoo      | Not used          |

---

## Setup

Prerequisites: Python 3.11+ and Node 18+. The first run needs internet access to
install dependencies (PyPI + npm). By default the app uses a local **SQLite** file,
so no database server is required to get started.

```bash
# 1. Clone
git clone https://github.com/shubhamshubham66/Textile_Manufacturing_Platform.git
cd Textile_Manufacturing_Platform

# 2. Environment
cp .env.example .env   # then fill in values (never commit .env)
```

### Backend (one command)

```bash
cd backend
./run.sh
```

`run.sh` creates a virtualenv, installs `requirements.txt`, and starts the API on
<http://localhost:8000> (interactive docs at `/docs`, health at `/api/health`).

First-time database setup (creates tables + loads demo data):

```bash
cd backend
source .venv/bin/activate          # created by run.sh
python -m app.init_db              # create all tables
python -m app.seed                 # load demo data (5 buyers, 8 machines, 6 orders, 30 rolls, ...)
```

To use PostgreSQL instead of SQLite, set `DATABASE_URL` in `.env`, e.g.:

```
DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/textile
```

### Frontend (one command)

```bash
cd frontend
npm install && npm run dev
```

Starts Vite on <http://localhost:5173>. `/api/*` is proxied to the backend on 8000,
and the home screen shows a live backend + database health check.

Environment variables live in `.env` (see `.env.example`). **Never commit secrets.**

---

## Demo logins

Throwaway demo accounts created by the seed script (`python -m app.seed`). These
are **demo-only credentials for judging**, hashed with bcrypt in the database — not
real passwords. Set a strong `JWT_SECRET` in `.env` for any real deployment.

| Role              | Email                   | Password      |
| ----------------- | ----------------------- | ------------- |
| Owner             | `owner@everest.test`    | `owner123`    |
| Store manager     | `store@everest.test`    | `store123`    |
| Floor supervisor  | `floor@everest.test`    | `floor123`    |
| Quality inspector | `quality@everest.test`  | `quality123`  |
| Accountant        | `accounts@everest.test` | `accounts123` |
| Production manager | `production@everest.test` | `production123` |
| Sales & Dispatch manager | `sales@everest.test` | `sales123` |
| Buyer             | `buyer@everest.test`    | `buyer123`    |

> Demo manager logins (`production@everest.test`, `sales@everest.test`) are also
> ensured on startup for an already-populated database, so they work after a
> deploy even though the seed only runs on an empty database.

Each role sees only its own menu, and the backend enforces role access (forbidden
requests return `403`), not just by hiding menus.

---

## Team Roles

| Area                              | Owner                                        |
| --------------------------------- | -------------------------------------------- |
| `main`, shared files, final merge | Main developer                               |
| Chatbot (`chatbot/`, `backend/chatbot/`) | Mini developer (works on `mini/chatbot`) |

Application user roles (menus and data access depend on role): **Owner, Store
manager, Floor supervisor, Quality inspector, Accountant, Buyer.**

---

## Contributing

### Branches

- `main` — protected. **No direct pushes.** Owned by the main developer, who does
  the final merge.
- `feature/<name>` — all normal feature work branches off `main`.
- `mini/chatbot` — the mini developer's branch for chatbot work only.

### Folder ownership

- `backend/` — main developer (except `backend/chatbot/`)
- `frontend/` — main developer
- `chatbot/` and `backend/chatbot/` — **mini developer only.** Do not edit these if
  you are not the chatbot owner.
- `docs/` — shared

### Before every push

Always rebase on the latest `main` first:

```bash
git pull --rebase origin main
```

Use small, clear commits. Open a pull request into `main`; do not push to `main`
directly.

---

## AI Assistant Rules

- Built with **Dify**. The browser must **never** call Dify directly.
- Flow: `Chat UI → our backend /api/chatbot/message → Dify API`.
- **Public mode** (before login): product FAQ and how-to only. No private factory data.
- **Logged-in mode**: live data answers, limited by role (a buyer sees only their own orders).
- Keys only in `.env` (`DIFY_API_KEY`, `DIFY_BASE_URL`). Never commit secrets.

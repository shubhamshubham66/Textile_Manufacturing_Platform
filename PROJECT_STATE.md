# PROJECT STATE — Context Ledger

Single source of truth for the current state of the project. Update this at the end
of every phase. Keep it short and factual.

**Last updated:** Phase 1 (Repo Foundation) — 10 Oct 2026
**Current phase:** Phase 1 — Repo Foundation

---

## 1. Stack

**To be decided.** Frontend, backend, database and whether Odoo is required are not
yet decided. No stack assumptions have been made in code.

| Layer    | Choice          | Status    |
| -------- | --------------- | --------- |
| Frontend | _to be decided_ | Pending   |
| Backend  | _to be decided_ | Pending   |
| Database | _to be decided_ | Pending   |
| AI       | Dify            | Confirmed |
| Odoo     | _to be decided_ | Pending   |

---

## 2. Pages

_None yet._ Planned (public + app):

- Public: Landing (Home, About, How it works, Features, AI help, Demo, Login)
- App: Orders, Yarn store, Production, Quality, Dispatch, Payments, Attendance &
  wages, Owner reports, Buyer portal
- Floating AI chat bubble on every page

---

## 3. APIs

See `API_CONTRACT.md` for full request/response details.

| Method | Path                   | Purpose                       | Status  |
| ------ | ---------------------- | ----------------------------- | ------- |
| POST   | `/api/chatbot/message` | Send a message to AI assistant | Defined (contract only) |

---

## 4. Database

_Not decided._ No schema, migrations or models yet.

---

## 5. Auth & Roles

_Not implemented._ Planned roles: Owner, Store manager, Floor supervisor, Quality
inspector, Accountant, Buyer. Menus and data access will depend on role. A buyer
sees only their own orders.

---

## 6. Completed Features

- **Phase 1 — Repo Foundation (in progress):**
  - `README.md`, `PROJECT_STATE.md`, `API_CONTRACT.md`
  - Folder skeleton: `backend/`, `frontend/`, `chatbot/`, `docs/`
  - `.gitignore`, `.env.example`
  - Contributing / Git rules documented

---

## 7. Pending Tasks

- Decide tech stack, database, and Odoo (yes/no) — **blocking**.
- Fill setup commands in `README.md` once the stack is chosen.
- Build feature modules (Orders, Yarn, Production, Quality, Dispatch, Payments,
  Attendance & wages, Reports, Buyer portal).
- Implement `/api/chatbot/message` backend (mini developer).
- Public landing page + floating chat bubble.
- Auth and role-based access control.

---

## 8. Known Bugs

_None._

---

## 9. Commands

_Placeholders — to be filled once the stack is decided._

```bash
# install   — TBD
# run dev   — TBD
# test      — TBD
# build     — TBD
```

---

## 10. Deployment

_Not decided._ Hosting / demo environment TBD.

---

## 11. Demo Flow

_To be defined._ Target end-to-end narrative for live judging (the 6 scenes):

1. Yarn arrives → recorded in store, live stock updates.
2. New order → yarn-sufficiency check.
3. Production → assign machine, update status, log output; idle-loss shown in ₹.
4. Quality → inspect rolls (pass/rework/reject).
5. Buyer portal → track order status.
6. Dispatch → pick passed rolls, confirm (one transaction), print invoice.
7. Owner reports → cost per order, machine report, profit/loss.

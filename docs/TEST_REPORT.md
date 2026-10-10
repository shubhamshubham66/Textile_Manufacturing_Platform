# Phase 10 — Test Report

**Date:** 10 Oct 2026
**Environment note:** The build sandbox has **no network** (`INTEGRATIONS_ONLY`),
so FastAPI/React/PostgreSQL cannot be installed and the **live HTTP/browser app
cannot be run here**. Results below are therefore from:

- **Simulated (DB logic):** `backend/tests/flow_simulation.py` exercises the real
  schema + business rules against SQLite via the standard library — the same logic
  the routers/services implement. **19/19 checks pass.**
- **Static:** compilation (`py_compile`), lint (`eslint` no-undef = 0 errors),
  formatting (`prettier`), and endpoint-guard audits.
- **Not tested (needs networked host):** real HTTP requests, the browser UI,
  PDF rendering, and the live Dify chatbot.

Labels: **Tested** (executed here) · **Simulated** (DB-logic executed here, not
HTTP) · **Not tested** (requires a networked host) · **Blocked**.

---

## Feature test table

| # | Feature | Result | Notes |
|---|---------|--------|-------|
| 1 | New order | Simulated | Order + yarn-requirement item created; `flow_simulation` check 1. |
| 2 | Yarn check (enough / short) | Simulated | White: need 400kg, have 820 → enough. Blue: need 600, have 90 → short 510. Checks 2a/2b. |
| 3 | Receive yarn → stock up | Simulated | +500kg White → 1320kg. Check 3. |
| 4 | Assign machine | Simulated | Order→machine link, order→in_production. Check 4. |
| 5 | Log output → progress | Simulated | 1000/2000m → 50%. Check 5. |
| 6 | Create rolls (pending) | Simulated | 5 rolls pending. Check 6. |
| 7 | Inspect (pass/rework/reject) | Simulated | 4 pass, 1 reject. Check 7. |
| 8 | Dispatch (atomic) + invoice | Simulated | 4×50m @95 → subtotal 19000, tax 950, total 19950; rolls→dispatched. Checks 8a/8b. |
| 9 | Buyer payment | Simulated | 60% part payment → invoice `part_paid`. Check 9. |
| 10 | Owner profit/loss | Simulated | P&L = in − out − wages. Check 10; full seed figures tie out by hand (Phase 8). |
| — | Idle-machine loss (₹) | Tested | Math verified vs hand calc (Phase 6 standalone assertions). |
| — | Invoice = Σ rolls × rate × (1+tax) | Tested | Verified (Phase 7 + flow sim 8a). |
| 2 (roles) | Each role → own menu only | Static | Menu comes from one RBAC config via `/api/auth/me`; no per-role UI branching. Needs HTTP run to confirm visually. |
| 2 (roles) | Forbidden API → 403 | Static + Simulated | Audit: every endpoint except `/login` is guarded by `require_resource`/`require_roles`/`get_current_buyer`. Buyer isolation returns 404 (no leak). `tests/test_buyer_isolation.py` (pytest) written. |
| 3 | Edge: dispatch non-passed roll | Simulated | Rejected (400 "only passed rolls"). Check E1. |
| 3 | Edge: double dispatch | Simulated | App check (409) **and** DB `UNIQUE(dispatch_items.roll_id)` → IntegrityError + rollback. Checks E2/E2b. |
| 3 | Edge: negative/zero quantity | Simulated + Static | Pydantic `gt=0` on quantity fields; sim check E3. |
| 3 | Edge: empty roll list | Simulated | Backend guards with 400 "Select at least one roll"; sim check E4. |
| 3 | Edge: wrong login | Simulated | bcrypt verify fails → 401; sim check E5 (stand-in). |
| 3 | Edge: cross-buyer access | Simulated + Static | Scoped queries; buyer 2 cannot read buyer 1's order → 404. Check E6 + isolation test. |
| 4 | Bug fixes (smallest reliable) | Tested | Fixed: notifications bell was a dead disabled button → now a working empty-state popover. (Also fixed the flow-sim's own missing empty-list guard.) No unrelated changes. |
| 5 | Responsive / loading / empty / error / no dead buttons | Static | Lint 0 errors; prettier clean. No TODO/placeholder prose except the (now-working) bell. Responsive breakpoints present. Visual pass pending on a networked host. |
| 6 | Realistic demo data | Tested | Seed has Indian names/cities/phones, 5 buyers, 8 machines, 6 orders across stages, 30 rolls, idle/breakdown logs, a dispatch+invoice+payment. |
| 6 | One-click "Try as owner / buyer" | Tested (code) | Login page now has prominent one-click demo buttons + a full one-click role list. Parses/lints clean; live click pending networked host. |
| 7 | This report | Tested | You're reading it. |
| C (chatbot) | Dify proxy + widget | Not tested | Needs network + Dify keys; merged via PR #10, needs 2 wiring lines (see chatbot/README). |

---

## How to run the checks

```bash
# DB-logic end-to-end + edge cases (no deps needed):
python backend/tests/flow_simulation.py        # expect 19/19

# On a networked host — real HTTP + browser:
cd backend && ./run.sh && (source .venv/bin/activate && python -m app.seed)
pytest tests/test_buyer_isolation.py -v         # cross-buyer isolation
cd ../frontend && npm install && npm run dev     # open http://localhost:5173
```

## Remaining risk / what must still be verified live
- Full HTTP request/response for every endpoint (only DB-logic + static done here).
- Browser rendering, responsive layout, PDF download, and the Dify chatbot.
- The chatbot's two shared-file wiring lines (backend include + `<ChatWidget/>` mount).

# API Contract

The agreed contract between frontend, backend and chatbot. **Update this before or
alongside implementing any endpoint** so both sides stay in sync.

Conventions:

- All request and response bodies are JSON (`Content-Type: application/json`).
- All paths are prefixed with `/api`.
- Monetary values are in INR.
- Timestamps are ISO 8601 (UTC).
- Errors use the shape in the [Error format](#error-format) section below.

---

## POST /api/chatbot/message

Send a user message to the AI assistant. The browser calls **our backend only** —
the backend forwards to Dify. The browser must never call Dify directly.

### Request

```json
{
  "message": "How do I create a new order?",
  "session_id": "abc-123"
}
```

| Field        | Type   | Required | Description                                           |
| ------------ | ------ | -------- | ----------------------------------------------------- |
| `message`    | string | yes      | The user's message.                                   |
| `session_id` | string | yes      | Conversation/session id to keep context across turns. |

### Response — 200 OK

```json
{
  "reply": "Go to Orders and click New order..."
}
```

| Field   | Type   | Description                      |
| ------- | ------ | -------------------------------- |
| `reply` | string | The assistant's reply text.      |

### Notes

- **Public mode** (no auth): answers product FAQ and how-to only. No private data.
- **Logged-in mode**: live data, limited by role (a buyer sees only their own orders).
- Keys (`DIFY_API_KEY`, `DIFY_BASE_URL`) live in `.env`, used server-side only.

---

## POST /api/auth/login

Validate credentials and issue a JWT bearer token. Public (no auth).

### Request

```json
{ "email": "owner@everest.test", "password": "owner123" }
```

| Field      | Type   | Required | Description     |
| ---------- | ------ | -------- | --------------- |
| `email`    | string | yes      | Must be valid.  |
| `password` | string | yes      | Non-blank.      |

### Response — 200 OK

```json
{
  "token": "<jwt>",
  "token_type": "bearer",
  "user": { "id": 1, "name": "Ramesh Shah", "email": "owner@everest.test", "role": "owner", "buyer_id": null },
  "menu": [{ "label": "Dashboard", "path": "/app/dashboard", "resource": "dashboard" }]
}
```

| Field        | Type   | Description                                         |
| ------------ | ------ | --------------------------------------------------- |
| `token`      | string | JWT; send as `Authorization: Bearer <token>`.       |
| `user`       | object | id, name, email, role, buyer_id (null unless buyer). |
| `menu`       | array  | Role-based menu items (from the one RBAC config).    |

### Errors

| Status | Code             | When                               |
| ------ | ---------------- | ---------------------------------- |
| 400    | VALIDATION_ERROR | Missing/invalid email or password. |
| 401    | UNAUTHENTICATED  | Wrong email or password.           |
| 403    | FORBIDDEN        | Account disabled.                  |

---

## GET /api/auth/me

Return the current user, role and role-based menu. Requires a bearer token.

### Response — 200 OK

```json
{
  "user": { "id": 1, "name": "Ramesh Shah", "email": "owner@everest.test", "role": "owner", "buyer_id": null },
  "menu": [{ "label": "Dashboard", "path": "/app/dashboard", "resource": "dashboard" }]
}
```

### Errors

| Status | Code            | When                                |
| ------ | --------------- | ----------------------------------- |
| 401    | UNAUTHENTICATED | Missing, invalid or expired token.  |

---

## POST /api/auth/logout

Stateless logout — the client discards its token. Requires a bearer token.

### Response — 200 OK

```json
{ "message": "Logged out" }
```

---

## Orders (role: owner — resource `orders`)

All endpoints require a bearer token and the `owner` role (else 403).

### GET /api/orders

List orders. Optional `?status=<status>` and `?q=<search>` (order no / fabric /
colour). Returns an array of order objects:

```json
{
  "id": 3, "order_no": "ORD-2003", "buyer_id": 3, "buyer_name": "Delhi Garments Co",
  "fabric_type": "Denim", "colour": "Blue", "quantity_meters": 3000, "unit": "meters",
  "unit_price": 120, "deadline": "2026-10-24", "status": "in_quality",
  "created_at": "2026-10-10T..."
}
```

### POST /api/orders

Create a new order (status `draft`). Also records a yarn requirement order item
(`quantity_meters × YARN_KG_PER_METER` kg).

```json
{ "buyer_id": 1, "fabric_type": "Cotton Shirting", "colour": "White",
  "quantity_meters": 2000, "unit_price": 95, "deadline": "2026-10-24",
  "yarn_type": "Cotton 30s" }
```

| Field             | Type   | Required | Notes                       |
| ----------------- | ------ | -------- | --------------------------- |
| `buyer_id`        | int    | yes      | Must exist (else 400).      |
| `fabric_type`     | string | yes      | Non-blank.                  |
| `colour`          | string | yes      | Non-blank.                  |
| `quantity_meters` | number | yes      | > 0.                        |
| `unit_price`      | number | yes      | ≥ 0 (rate per metre, ₹).    |
| `deadline`        | date   | no       | ISO date.                   |
| `yarn_type`       | string | no       | Yarn feeding the order.     |

Returns the created order (201).

### GET /api/orders/_meta/buyers

Buyers for the New order form: `[{ "id": 1, "name": "Mumbai Fashion House" }]`.

### GET /api/orders/{id}

Single order (404 if not found).

### GET /api/orders/{id}/check-yarn

Compare required yarn vs. available stock (same colour).

```json
{
  "order_id": 3, "colour": "Blue", "required_kg": 600, "available_kg": 90,
  "enough": false, "short_by_kg": 510, "suggested_purchase_kg": 510,
  "message": "Short by 510.00 kg — only 90.00 kg of Blue yarn in stock..."
}
```

### POST /api/orders/{id}/confirm

Set status to `confirmed` (available for production). `409` if the order is in a
state that cannot be confirmed. Returns the updated order.

### PUT /api/orders/{id}

Edit an order (owner). Allowed **only before production** (status `draft` or
`confirmed`), else **409**. Body: `buyer_id, fabric_type, colour,
quantity_meters, unit_price, deadline`. Keeps the order's yarn-requirement item
in step with the new colour/quantity. Returns the updated order.

### POST /api/orders/{id}/cancel

Cancel an order (owner). Allowed only for `draft`/`confirmed` (else **409**).
Sets status to `cancelled`; the order stays on record but leaves the active
pipeline. Returns the updated order.

### GET /api/orders/{id}/track

Owner order tracker (owner only). Current stage + progress + late flag + the
order's rolls with inspection result and the machine that made them:
```json
{
  "order_no": "ORD-2003", "buyer_name": "Delhi Garments Co",
  "fabric_type": "Denim", "colour": "Blue", "quantity_meters": 3000,
  "status": "in_quality", "stage_index": 3,
  "stage_flow": ["draft","confirmed","in_production","in_quality","ready_to_ship","dispatched","closed"],
  "progress_percent": 100.0, "deadline": "2026-10-26", "late": false,
  "rolls": [ { "roll_no": "R-0015", "length_meters": 50, "status": "pass",
               "result": "pass", "defect_type": "none", "machine": "Dye-01" } ]
}
```
`late` is `true` when the deadline has passed and progress < 100% (and the order
is not yet dispatched/closed). `404` if the order does not exist.

---

## Yarn store (role: store_manager — resources `yarn` / `stock` / `purchase`)

### GET /api/yarn/stock

Live stock with low-stock flag:

```json
{ "id": 3, "yarn_type": "Cotton 40s", "colour": "Blue", "quantity_kg": 90,
  "reorder_level_kg": 150, "unit_cost": 200, "low_stock": true,
  "updated_at": "2026-10-10T..." }
```

`low_stock` is true when `quantity_kg ≤ reorder_level_kg` (or the configured
`DEFAULT_REORDER_LEVEL_KG` when a row has no level).

### POST /api/yarn/receipts

Record a yarn receipt; **stock updates automatically** (matches an existing
type+colour row or creates one) in a single transaction. If `purchase_order_id`
is given and that PO is `raised`, it is marked `received`.

```json
{ "supplier_id": 1, "yarn_type": "Cotton 30s", "colour": "White",
  "quantity_kg": 500, "unit_cost": 180, "order_id": 1, "purchase_order_id": null }
```

| Field               | Type   | Required | Notes                          |
| ------------------- | ------ | -------- | ------------------------------ |
| `yarn_type`         | string | yes      | Non-blank.                     |
| `colour`            | string | yes      | Non-blank.                     |
| `quantity_kg`       | number | yes      | > 0.                           |
| `unit_cost`         | number | no       | ≥ 0.                           |
| `supplier_id`       | int    | no       | Must exist if given (400).     |
| `order_id`          | int    | no       | Linked order; exist if given.  |
| `purchase_order_id` | int    | no       | Fulfils this PO if `raised`.   |

Returns the updated stock row (201).

### POST /api/yarn/purchase

Raise a purchase order (status `raised`) for a supplier when yarn is short.

```json
{ "supplier_id": 3, "yarn_type": "Cotton 40s", "colour": "Blue",
  "quantity_kg": 510, "unit_cost": 200 }
```

Returns the created PO (201). `GET /api/yarn/purchase` lists POs.

### GET /api/yarn/suppliers

Suppliers for the receive/purchase forms: `[{ "id": 1, "name": "Gujarat Yarn Supply" }]`.

---

## Production (role: floor_supervisor — resources `machines` / `production`)

### GET /api/production/machines

Every machine with status, assigned order and progress:

```json
{ "id": 4, "name": "Weave-01", "type": "weaving", "current_status": "running",
  "hourly_cost": 400, "status_since": "2026-10-10T...", "current_order_id": 3,
  "current_order_no": "ORD-2003", "current_stage": "weaving",
  "progress_percent": 36.7 }
```

### GET /api/production/orders

Assignable orders (confirmed / in_production / in_quality) for the assign form.

### POST /api/production/machines/{id}/assign

Link an order + stage to a machine. Moves a `confirmed` order to `in_production`.

```json
{ "order_id": 3, "stage": "weaving" }
```

`stage` ∈ spinning|weaving|dyeing. Returns the updated machine.

### POST /api/production/machines/{id}/status

Change status; writes a `machine_status_log` row (timestamped) and **closes the
previous open window**. A **reason is required** for `idle` and `breakdown`.

```json
{ "status": "idle", "reason": "No yarn" }
```

| Field    | Type   | Required | Notes                                        |
| -------- | ------ | -------- | -------------------------------------------- |
| `status` | string | yes      | running\|idle\|breakdown.                    |
| `reason` | string | cond.    | Required when status is idle or breakdown.   |

`400 VALIDATION_ERROR` if idle/breakdown without a reason. Returns the machine.

### POST /api/production/output

Log metres produced (per machine/shift). Updates order progress.

```json
{ "machine_id": 4, "order_id": 3, "output_meters": 600, "shift": "morning" }
```

Response: `{ "ok": true, "order_no": "ORD-2003", "logged_meters": 600,
"order_progress_percent": 40.0 }`.

### GET /api/production/output/today

Today's output per machine: `[{ "machine_id": 4, "machine_name": "Weave-01",
"output_meters_today": 600 }]`.

### PATCH /api/production/machines/{id}/hourly-cost

Admin setting — hourly cost (power + wage + overhead), ₹/hr: `{ "hourly_cost": 400 }`.

### GET /api/production/idle-loss

Idle-machine loss (our USP): per-machine idle/breakdown hours × hourly cost, a
grand total, and the top reasons by lost hours.

```json
{
  "total_loss_rupees": 4525.0,
  "total_lost_hours": 11.5,
  "per_machine": [
    { "machine_id": 3, "machine_name": "Spin-03", "current_status": "breakdown",
      "hourly_cost": 250, "idle_hours": 0, "breakdown_hours": 4,
      "lost_hours": 4, "loss_rupees": 1000 }
  ],
  "top_reasons": [ { "reason": "Motor fault", "hours": 4.0 } ]
}
```

Loss = Σ(window hours) × hourly_cost over idle/breakdown logs; open windows run to
"now". Verified against hand calculations.

---

## Quality (role: quality_inspector — resources `quality` / `rolls`)

### GET /api/quality/_meta

Orders, machines and defect types for the new-roll / inspect forms.

### POST /api/quality/rolls

Create a roll (status `pending`, auto unique `roll_no`).

```json
{ "order_id": 3, "machine_id": 4, "length_meters": 50 }
```

Returns the roll (201).

### GET /api/quality/rolls

List rolls. Optional `?status=pending|pass|rework|reject|dispatched` and
`?order_id=`.

### POST /api/quality/rolls/{id}/inspect

Record an inspection; sets the roll status.

```json
{ "result": "reject", "defect_type": "hole", "notes": "edge tear" }
```

| Field         | Type   | Required | Notes                                            |
| ------------- | ------ | -------- | ------------------------------------------------ |
| `result`      | string | yes      | pass\|rework\|reject.                            |
| `defect_type` | string | cond.    | none\|hole\|colour_mismatch\|uneven_weaving\|other. Required (≠none) for rework/reject; must be none for pass. |
| `notes`       | string | no       | Free text.                                       |

`409` if the roll is already dispatched. Returns the updated roll.

### GET /api/quality/defect-report

Counts by defect, machine and order (rework+reject), plus roll-status tallies, so
a cause can be traced.

---

## Dispatch (role: store_manager — resource `dispatch`)

### GET /api/dispatch/orders

Orders with at least one passed, not-yet-dispatched roll:
`[{ "order_id": 1, "order_no": "ORD-2001", "buyer_name": "...", "passed_rolls": 8 }]`.

### GET /api/dispatch/orders/{id}/pickable

**ONLY** passed rolls of this order that are not yet dispatched (what may be picked):

```json
{ "order_id": 1, "order_no": "ORD-2001", "unit_price": 95,
  "rolls": [{ "id": 10, "roll_no": "R-0001", "length_meters": 50 }] }
```

### POST /api/dispatch/confirm

Confirm a dispatch in **one database transaction**: validate rolls (must belong to
the order and be `pass`), mark them `dispatched`, create the dispatch record +
items (reduces finished-on-shelf stock), and auto-create the invoice
(`metres × rate + tax`). Any failure rolls everything back.

```json
{ "order_id": 1, "roll_ids": [10, 11, 12] }
```

Response:

```json
{ "dispatch_no": "DSP-3002", "invoice_no": "INV-4002", "total_rolls": 3,
  "total_meters": 150, "subtotal": 14250, "tax": 712.5, "total": 14962.5 }
```

| Status | Code      | When                                                        |
| ------ | --------- | ----------------------------------------------------------- |
| 400    | VALIDATION_ERROR | A roll isn't `pass`, or doesn't belong to the order. |
| 409    | CONFLICT  | A roll is already dispatched — **double dispatch prevented** (also enforced by a UNIQUE DB constraint on `dispatch_items.roll_id`). |

### GET /api/dispatch

List dispatches with their invoice numbers.

### GET /api/dispatch/finished-stock

Per order: rolls/metres **on shelf** (passed, not dispatched) vs **dispatched**.

### GET /api/dispatch/invoice/{id}

Invoice JSON with the exact rolls listed, subtotal, tax, total.

### GET /api/dispatch/invoice/{id}/pdf

The invoice as a PDF (`application/pdf`, inline) listing the exact rolls.

---

## Payments (roles: owner, accountant — resource `payments`)

### GET /api/payments/_meta
Invoices (with paid/balance/status) and suppliers for the forms.

### POST /api/payments/buyer
Record a buyer payment against an invoice; recomputes invoice status
(unpaid → part_paid → paid). `400` if amount exceeds the balance, `409` if already
fully paid.
```json
{ "invoice_id": 1, "amount": 10000, "method": "bank" }
```

### POST /api/payments/supplier
Pay a supplier (yarn bills): `{ "supplier_id": 1, "amount": 50000, "method": "bank",
"is_advance": false }`.
Server-side validation: `amount > 0`; the amount may **not exceed the supplier's
outstanding bill** (Σ raised/received PO value − Σ payments) unless `is_advance`
is `true`. A `400 VALIDATION_ERROR` is returned otherwise with a clear message.
Response adds `outstanding_after` and `is_advance`.

### GET /api/payments
Payment history (incoming + outgoing), newest first; each row includes `paid_at`.

### GET /api/payments/dues
Pending dues with ageing:
```json
{
  "buyers_owe_us": [
    { "buyer_name": "Delhi Garments Co", "invoice_no": "INV-4002",
      "invoice_date": "2026-10-14", "due": 17640.0,
      "days_overdue": 12, "overdue": false }
  ],
  "we_owe_suppliers": [
    { "supplier_name": "Punjab Cotton Co", "bill_date": "2026-10-06",
      "due": 80000.0, "days_overdue": 20, "overdue": false }
  ],
  "total_receivable": 17640.0,
  "total_payable": 80000.0
}
```
`overdue` is `true` when the bill/invoice is more than 30 days old.

---

## Attendance & Wages (role: accountant — resources `attendance` / `wages`)

### GET /api/wages/employees
Employees + today's attendance status.

### POST /api/attendance
Mark attendance (upsert per employee+day):
```json
{ "employee_id": 1, "status": "present", "shift": "morning", "hours_worked": 8 }
```
`status` ∈ present|absent|half_day.

### GET /api/attendance?date=YYYY-MM-DD
Attendance rows (optional date filter).

### POST /api/wages/calculate
Compute a wage record per employee for a period:
`amount = (present=1, half_day=0.5) × daily_wage + overtime(hours>8 × ₹80/hr)`.
```json
{ "period_start": "2026-10-04", "period_end": "2026-10-10" }
```

### GET /api/wages
List wage records. ### POST /api/wages/{id}/pay — mark a wage paid (409 if already paid).

---

## Owner reports (role: owner — resources `reports` / `dashboard`)

All report endpoints accept an optional month window `?start=YYYY-MM-DD&end=YYYY-MM-DD`.
When omitted they default to the **current calendar month**. Every response echoes
the resolved `start` / `end`. All return **403** for non-owner roles.

### GET /api/reports/cost-per-order?start=&end=
`{ "start", "end", "rows": [ ... ] }`, one row per order with activity in the
window (metres made, linked yarn received, or an invoice); an empty month
returns `rows: []`. Each row: `output_meters`, `yarn_cost`, `yarn_basis`
(`"linked"` | `"estimate"`), `wage_cost`, `machine_cost`, `total_cost`
(= yarn + wages + machine), `revenue_est`, `margin_est`.
- **Yarn** = receipts linked to the order received in the window (kg × rate).
  With no linked receipt at all: an estimate from metres made this month
  (required kg × share made × average purchase rate, or metres × 0.2 kg/m ×
  average rate for the colour).
- **Wages** = wages accrued in the window split by metres made; the rounding
  remainder goes to the largest share so the rows add up to the total exactly.
- **Machine** = per machine, running hours in the window × `power_overhead_cost`
  (power + overhead, **excludes operator wages**), split across the orders it
  made metres for. Wages are never counted twice.

### GET /api/reports/machines?start=&end=
`{ "start", "end", "machines": [ ... ], "totals": { ... } }`. Each machine row:
`total_output_meters`, `running_hours`, `idle_hours`, `breakdown_hours`,
`idle_loss_rupees`, `top_idle_reason`. Hours count only the part of each status
window inside the month (open windows up to now). `totals` sums the numeric
columns.

### GET /api/reports/profit-loss?start=&end=
Month cash-basis net:
```json
{ "start": "2026-10-01", "end": "2026-10-31",
  "buyer_payments_in": 225960, "supplier_payments_out": 200000,
  "wages": 8100, "wages_accrued": 10350, "wages_due": 2250,
  "profit_or_loss": 17860, "is_profit": true }
```
`profit = buyer payments received − raw material bills paid − wages PAID`, all
inside the window. `wages_due` (worked in the window, not yet paid) is context
only and is not in the net.

### GET /api/reports/wages?start=&end=
Owner wages view (owner only):
```json
{ "start", "end", "total_wages": 10350, "total_paid": 8100, "total_unpaid": 2250,
  "paid_in_month": 8100,
  "per_employee": [ { "employee", "role_on_floor", "days_present", "daily_wage",
                      "amount", "status", "period_start", "period_end" } ],
  "per_order": [ { "order_no", "output_meters", "wages_allocated" } ] }
```
`per_order` uses the same split as cost-per-order, so the two tie out exactly.

### GET /api/reports/dashboard?start=&end=
Key cards + charts data: `machine_count`, `orders_by_stage` and `low_stock_count` +
`low_stock` (current snapshot), `idle_loss_rupees` and `idle_loss_by_reason`
(`[{reason, loss_rupees}]`) for the window (same numbers as the Machine report),
and `profit_loss` (the same object as `/profit-loss`, so the Dashboard card and
the Reports P&L always match).

---

## Buyer portal (role: buyer — resources `my_orders` / `invoices`)

Every endpoint resolves the logged-in buyer via the token and scopes all data to
their `buyer_id`. A buyer can **never** see another buyer's data — single-resource
lookups that don't belong to the buyer return **404** (so existence isn't leaked).

### GET /api/buyer/orders
The buyer's own orders with a buyer-facing stage, progress and ETA:
```json
{ "id": 1, "order_no": "ORD-2001", "fabric_type": "Cotton Shirting",
  "colour": "White", "quantity_meters": 2000, "status": "in_production",
  "stage": "Weaving", "stage_index": 1, "progress_percent": 36.7,
  "expected_delivery": "2026-10-24" }
```
Stage flow: Confirmed → Weaving → Dyeing → Checking → Ready to ship → Shipped
(mapped from internal order status).

### GET /api/buyer/orders/{id}
Track one of the buyer's own orders (adds `stage_flow` for the stepper). **404** if
the order isn't theirs.

### GET /api/buyer/invoices
The buyer's own invoices (invoice_no, order_no, subtotal, tax, total, status).

### GET /api/buyer/invoices/{id}/pdf
The buyer's own invoice as a PDF. **404** if the invoice isn't theirs.

> Cross-buyer isolation is covered by `backend/tests/test_buyer_isolation.py`.

---

### Role → menu / resource map (one config, enforced server-side)

| Role              | Menu (resource)                                                     |
| ----------------- | ------------------------------------------------------------------- |
| owner             | Dashboard, Orders, Reports, Payments                                |
| store_manager     | Yarn store (yarn), Stock (stock), Purchase (purchase), Dispatch (dispatch) |
| floor_supervisor  | Production, Machines                                                |
| quality_inspector | Quality, Rolls                                                      |
| accountant        | Payments, Attendance, Wages                                         |
| buyer             | My orders (my_orders), Invoices                                     |

Backend enforcement uses `require_resource("<resource>")` / `require_roles(...)`;
the frontend renders menus from the same config returned by `/api/auth/me`.

---

## Master data (role: owner — resource `master_data`)

Owner-only (403 for other roles). Add + edit the mill's reference records so
judges can enter real data live. Each save fires the matching live event.

| Method | Path                              | Purpose                                   |
| ------ | --------------------------------- | ----------------------------------------- |
| GET    | `/api/master/buyers`              | List buyers                               |
| POST   | `/api/master/buyers`              | Add a buyer (409 on duplicate name)       |
| PUT    | `/api/master/buyers/{id}`         | Edit a buyer                              |
| GET    | `/api/master/suppliers`           | List suppliers                            |
| POST   | `/api/master/suppliers`           | Add a supplier (409 on duplicate name)    |
| PUT    | `/api/master/suppliers/{id}`      | Edit a supplier                           |
| GET    | `/api/master/machines`            | List machines                             |
| POST   | `/api/master/machines`            | Add a machine (status starts `idle`)      |
| PUT    | `/api/master/machines/{id}`       | Edit a machine                            |
| GET    | `/api/master/employees`           | List employees                            |
| POST   | `/api/master/employees`           | Add an employee                           |
| PUT    | `/api/master/employees/{id}`      | Edit an employee                          |
| GET    | `/api/master/yarn-receipts`       | List yarn receipts (for correction)       |
| PUT    | `/api/master/yarn-receipts/{id}`  | Correct a receipt; stock adjusts by delta |

Fields:
- **Buyer**: `name` (req), `contact_person`, `phone`, `email`, `address`,
  `credit_limit ≥ 0`.
- **Supplier**: `name` (req), `phone`, `email`, `address`.
- **Machine**: `name` (req), `type` ∈ spinning|weaving|dyeing, `hourly_cost ≥ 0`,
  `power_overhead_cost ≥ 0` and **≤ hourly_cost** (400 otherwise — the rest is
  the operator wage).
- **Employee**: `name` (req), `role_on_floor`, `daily_wage ≥ 0`, `phone`.
- **Yarn receipt correction**: `quantity_kg > 0`, `unit_cost ≥ 0`, `order_id`
  (nullable). The stock row changes by `new_qty − old_qty`; a correction that
  would push stock below zero is rejected (400).

## Error format

All endpoints return this shape on error (non-2xx):

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description of what went wrong."
  }
}
```

| Field           | Type   | Description                                  |
| --------------- | ------ | -------------------------------------------- |
| `error.code`    | string | Stable machine-readable code.                |
| `error.message` | string | Human-readable description.                  |

Common status codes: `400` validation, `401` unauthenticated, `403` forbidden
(role), `404` not found, `409` conflict (e.g. double dispatch), `500` server error.

---

## Template — adding a new endpoint

Copy this block for every new endpoint and fill it in.

````markdown
## METHOD /api/path

One-line description of what it does and who may call it (role/auth).

### Request

```json
{
  "field": "value"
}
```

| Field   | Type   | Required | Description |
| ------- | ------ | -------- | ----------- |
| `field` | string | yes      | ...         |

### Response — 200 OK

```json
{
  "field": "value"
}
```

| Field   | Type   | Description |
| ------- | ------ | ----------- |
| `field` | string | ...         |

### Errors

| Status | Code             | When                        |
| ------ | ---------------- | --------------------------- |
| 400    | VALIDATION_ERROR | Invalid or missing input.   |
| 403    | FORBIDDEN        | Role not permitted.         |

### Notes

- Any extra behaviour, side effects, transactions, etc.
````

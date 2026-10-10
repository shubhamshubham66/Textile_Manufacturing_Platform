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

## GET /api/auth/_demo/payments

Demo endpoint proving backend role enforcement. Only `owner` and `accountant`
(roles permitted for the `payments` resource) succeed; all other roles get **403**.
Replace with the real payments endpoints in a later phase.

### Response — 200 OK

```json
{ "ok": true, "resource": "payments", "accessed_by": { "user": "Ramesh Shah", "role": "owner" } }
```

### Errors

| Status | Code            | When                                   |
| ------ | --------------- | -------------------------------------- |
| 401    | UNAUTHENTICATED | No/invalid token.                      |
| 403    | FORBIDDEN       | Role not permitted for the resource.   |

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

### Role → menu / resource map (one config, enforced server-side)

| Role              | Menu (resource)                                                     |
| ----------------- | ------------------------------------------------------------------- |
| owner             | Dashboard, Orders, Reports, Payments                                |
| store_manager     | Yarn store (yarn), Stock (stock), Purchase (purchase)               |
| floor_supervisor  | Production, Machines                                                |
| quality_inspector | Quality, Rolls                                                      |
| accountant        | Payments, Attendance, Wages                                         |
| buyer             | My orders (my_orders), Invoices                                     |

Backend enforcement uses `require_resource("<resource>")` / `require_roles(...)`;
the frontend renders menus from the same config returned by `/api/auth/me`.

---

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

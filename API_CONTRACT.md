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

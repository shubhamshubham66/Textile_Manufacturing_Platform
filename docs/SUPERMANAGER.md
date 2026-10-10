# Supermanager control panel

The Supermanager (role key `manager`, shown as "Supermanager") runs the mill
day to day. The owner only views. Department managers are the existing staff
logins:

| Department | Login role (screens) |
| --- | --- |
| Purchase & Raw Material | store_manager |
| Production | floor_supervisor |
| Quality Control (QC) | quality_inspector |
| Store / Inventory | store_manager |
| Sales & Dispatch | store_manager |
| Accounts & Finance | accountant |

## Order workflow

1. A buyer sends a request (My orders → Request an order). It is saved as
   `pending_review`, and the Supermanager gets a notification and an alert.
2. The Supermanager opens **Review**. This shows:
   - **missing information**: rate, deadline, quantity;
   - **yarn**: stock vs need;
   - **capacity**: working looms × the m/day setting × days left, compared
     with the orders already ahead.
3. The Supermanager then does one of these:
   - **Confirm** (refused while information is missing);
   - **Reject** (a reason is required);
   - **Ask for clarification**, which sends the order to `clarification`.
     The buyer replies and the order goes back to `pending_review`.
4. On confirmation each department gets an instruction (task):
   - Purchase, only if yarn is short;
   - Store, Production, QC and Dispatch.
5. Department managers see these under **My tasks**. There they hand each
   task to a worker and post progress updates.
6. The order then moves through production → QC → dispatch as before, and
   is complete after dispatch.

## Data

| Change | What it is |
| --- | --- |
| New tables | `tasks`, `task_updates`, `activity_logs`, `app_settings` |
| New columns | `users.department`; `employees.department`, `manager_user_id`, `is_active`; `orders.review_note`, `reviewed_by_user_id`, `reviewed_at`, `buyer_note`; `tasks.worker_employee_id` |
| Existing databases | The new columns are added on startup by `schema_sync`, which only ever adds columns. |

- **Activity log** (`app/activity.py`): written automatically in the same
  transaction as the change.
  - Records order status, stock quantity, QC decisions, dispatch, attendance,
    logins, workers, tasks, payments and voids.
  - "Who" comes from the signed-in user.

## Not tracked

- **Late arrival, leave and check-out times.** The attendance screen does not
  record them, so they are not shown.
- **Worker logins.** Workers have no login of their own; their department
  manager records their work.

## API (all under `/api/super`, Supermanager only)

`overview`, `search`, `managers` (+ edit, active, reset-password), `workers`
(+ edit, active), `tasks` (+ edit, updates), `production`, `inventory`,
`quality`, `dispatch`, `attendance` (+ `attendance/exception`), `accounts`,
`alerts`, `activity`, `settings`.

Other endpoints:

| Endpoint | Who | Purpose |
| --- | --- | --- |
| `GET /api/orders/{id}/review` | Supermanager | Review checks |
| `POST /api/orders/{id}/confirm` | Supermanager | Confirm |
| `POST /api/orders/{id}/reject` | Supermanager | Reject |
| `POST /api/orders/{id}/clarify` | Supermanager | Ask for clarification |
| `GET /api/tasks/mine`, `POST /api/tasks/{id}/progress` | Department managers | My tasks |
| `POST /api/buyer/orders`, `PUT /api/buyer/orders/{id}` | Buyer | Request, reply |

Tests: `backend/tests/test_supermanager.py`.

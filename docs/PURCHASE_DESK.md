# Purchase & Raw Material desk (Store manager)

The store manager (role `store_manager`) runs yarn buying, suppliers, incoming
material and stock. The menu has 11 desk pages plus Dispatch, which the
store also runs:

| Page | What it does |
| --- | --- |
| Dashboard | Live cards (suppliers, POs, pending POs, stock kg, low-stock items, today's receipts), to-do strip, stock by colour, low stock, instructions, pending POs, recent receipts, stock activity |
| Suppliers | Add/edit, contact, address, yarn types supplied, activate/deactivate, purchase + delivery history |
| Raw material inventory | Yarn type, colour, kg, reserved for orders, available, minimum level, storage location, search/filter, movement history |
| Purchase requests | Supermanager instructions → request; manual requests; status pending → approved/rejected → ordered → received |
| Purchase orders | Only from an approved request; supplier, price, tax, delivery date; partial/complete delivery tracking |
| Material receiving | Record delivery (PO, qty, damaged, batch, date); shortage/excess/damage/wrong-yarn flagged; validate or reject |
| Low-stock alerts | Below minimum, required qty, already on order, suggested reorder, one-click request |
| Production requirements | Yarn needed by confirmed/upcoming orders vs stock, shortages, delay risk, share with Supermanager + Production |
| Reports | Purchase history, supplier performance (fill rate, on-time, delay, damage), consumption, stock valuation, monthly summary |
| Notifications | Instructions, approvals/rejections, deliveries due/overdue, low stock, receiving discrepancies |
| My tasks | Instructions from the Supermanager |

## Rules enforced on the server

1. **No purchase without approval.**
   - A purchase order needs an **approved** purchase request.
   - The Supermanager approves or rejects on Inventory › "Purchase requests to approve". A rejection needs a reason.
   - Settings › "Auto-approve purchase requests up to (kg)" can auto-approve small requests. The default is 0, meaning every request needs approval.
   - The old direct `POST /api/yarn/purchase` returns 409.
2. **The PO quantity is capped.** A PO may not exceed the approved quantity by more than 10%.
3. **Stock changes only on validation.**
   - A recorded delivery does not change stock.
   - Validating it adds received − damaged.
   - Rejecting it (a reason is required) adds nothing, and the record is kept.
4. **Every stock change is recorded.** Each one writes a `stock_movements` row (kind, change, balance, reference, who) and an activity-log entry, automatically.
5. **History is kept.** Nothing is deleted: requests and POs are cancelled, deliveries are rejected.
6. **Inactive suppliers** cannot receive new purchase orders.

## Data (additive)

- **New tables:** `purchase_requests`, `stock_movements`, `notifications`.
- **New columns:**
  - `suppliers`: `contact_person`, `yarn_types`, `is_active`
  - `yarn_stock`: `location`
  - `purchase_orders`: `purchase_request_id`, `tax_percent`, `expected_date`, `created_by_user_id`
  - `yarn_receipts`: `status`, `batch_no`, `damaged_kg`, `discrepancy`, `discrepancy_note`, `recorded_by_user_id`, `validated_by_user_id`, `validated_at`
- Older receipts default to `validated`, because they already updated stock.

## Assumptions

- **Reserved yarn** = metres still to be spun × 0.2 kg/m for confirmed and in-production orders, matched to stock by **colour**.
- **Consumption** in reports is an estimate from spinning output.

Tests: `backend/tests/test_purchase.py`.

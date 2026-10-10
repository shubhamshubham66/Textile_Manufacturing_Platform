# Owner month-end — hand-check (October 2026 seed)

This document lets you verify the owner numbers **by hand** against the seed
(`backend/app/seed.py`). Re-run `python -m app.seed` to load exactly this data,
then open the owner screens with the month set to **October 2026**.

A pure-arithmetic check (no server needed) is in
`backend/tests/verify_month_math.py` — run `python backend/tests/verify_month_math.py`.

---

## Definitions used everywhere (one set)

- **Order cost = yarn + wages + machine.**
  - Yarn = Σ(receipt kg × rate) for receipts **linked to the order**; if none are
    linked, required-kg × average purchase rate for that yarn.
  - Wages = total wages in the month × the order's share of production output (m).
  - Machine = Σ machines' **power+overhead** ₹/hr × the order's output share.
    Operator wages are **not** in machine cost (they are the Wages term), so
    wages are never double-counted. Seed `power_overhead_cost` ≈ 60% of
    `hourly_cost`.
- **Order margin (estimate) = revenue (invoiced, else output×rate) − cost.**
- **Month net (cash basis) = buyer payments received − supplier bills paid −
  wages, within the month.**
- **Idle loss = idle+breakdown hours × full `hourly_cost`** (an idle machine
  wastes the whole machine-hour, operator included).

---

## Shared bases for October 2026

| Quantity | Value |
| --- | --- |
| Total production output (all orders) | **5,430 m** |
| Total wages accrued in the month | **₹10,350.00** |
| Machine power+overhead basis (Σ power_overhead_cost) | **₹1,830.00 /hr** |

Output per order (from production logs): ORD-2001 2000 m, ORD-2002 1200 m,
ORD-2003 1100 m, ORD-2004 830 m, ORD-2007 300 m, ORD-2005/2006 0 m.

---

## Hand-check: 2 orders

### ORD-2001 (closed, invoiced ₹1,99,500)

| Component | Working | Value |
| --- | --- | --- |
| Yarn | linked receipt 400 kg × ₹180 | **₹72,000.00** |
| Wages | 10,350 × (2000 / 5430) | **₹3,812.15** |
| Machine | 1,830 × (2000 / 5430) | **₹674.03** |
| **Total cost** | 72,000 + 3,812.15 + 674.03 | **₹76,486.18** |
| Revenue (est) | invoiced total | **₹1,99,500.00** |
| **Margin (est)** | 199,500 − 76,486.18 | **₹1,23,013.82** |

### ORD-2002 (dispatched, invoiced ₹44,100)

| Component | Working | Value |
| --- | --- | --- |
| Yarn | linked receipt 240 kg × ₹140 | **₹33,600.00** |
| Wages | 10,350 × (1200 / 5430) | **₹2,287.29** |
| Machine | 1,830 × (1200 / 5430) | **₹404.42** |
| **Total cost** | 33,600 + 2,287.29 + 404.42 | **₹36,291.71** |
| Revenue (est) | invoiced total (300 m × 140 + 5%) | **₹44,100.00** |
| **Margin (est)** | 44,100 − 36,291.71 | **₹7,808.29** |

> Note: ORD-2003 shows yarn ₹18,000 (only 90 kg linked, the rest was short and
> re-ordered). ORD-2007 shows yarn as "—" (no linked receipt / order item) — this
> is correct, not the old ₹0 bug: orders **with** linked yarn now show real cost.

---

## Hand-check: the month total

| Line | Working | Value |
| --- | --- | --- |
| Buyer payments received | 1,99,500 (INV-4001 full) + 26,460 (INV-4002 60%) | **+₹2,25,960.00** |
| Raw material bills paid | 1,80,000 (Gujarat) + 20,000 (South India) | **−₹2,00,000.00** |
| Wages (month) | 2,475 + 2,700 + 2,925 + 2,250 | **−₹10,350.00** |
| **Month net (cash basis)** | 225,960 − 200,000 − 10,350 | **+₹15,610.00 (profit)** |

**Acceptance:** the Dashboard "Profit or loss (this month)" card and
Reports › Profit / loss must both show **+₹15,610.00** for October 2026, and
they use the same definition so they match exactly.

---

## Idle loss (unchanged logic, dated into October)

Idle/breakdown windows (×8 h total mix) × each machine's full hourly cost. The
Machine report shows per-machine idle loss and a totals row; the Dashboard shows
idle loss grouped by reason (No order assigned, Waiting for yarn, Motor fault,
Shift changeover, Cleaning). Figures depend on "now vs window end"; all seeded
windows here are **closed**, so the number is stable regardless of when you run it.

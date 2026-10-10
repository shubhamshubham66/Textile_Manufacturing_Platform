# Owner month-end — hand-check (October 2026 seed)

Verify the owner numbers **by hand** against the seed (`backend/app/seed.py`).
Load exactly this data with `python -m app.seed` (fresh database), then open the
owner screens with the month set to **October 2026**.

- Plain arithmetic, no server: `python backend/tests/verify_month_math.py`
- Same numbers asserted against the real API: `pytest backend/tests/test_owner_reports.py`

All seeded records are dated 1–10 October 2026 and every machine status window
is closed, so the figures do not drift with the time of day.

---

## Definitions used everywhere (one set)

Every figure is for the selected month only.

- **Order cost = yarn + wages + machine.**
  - **Yarn** = yarn receipts linked to the order and received in the month,
    Σ kg × ₹/kg. An order with **no** linked receipt gets an **estimate**
    (marked "est" in the table): required yarn × share of the order made this
    month × average purchase rate, or, with no order items, metres made ×
    `YARN_KG_PER_METER` (0.2) × the average rate for its colour.
  - **Wages** = wages accrued in the month, split across orders by metres
    made. The paise left over from rounding go to the largest share, so the
    split always adds up to the total.
  - **Machine** = for each machine, running hours in the month ×
    power+overhead ₹/hr (`power_overhead_cost`), split across the orders it
    made metres for. Operator wages are not in it (they are the wages term), so
    wages are never counted twice.
- **Order margin (estimate)** = revenue − cost; revenue = invoiced in the month,
  else metres made × unit price.
- **Month net (cash basis)** = buyer payments received − raw material bills
  paid − **wages paid**, all inside the month. Wages worked but not yet paid
  are shown separately as **wages due** and are not in the net.
- **Idle loss** = idle + breakdown hours in the month × the machine's full
  `hourly_cost` (an idle machine wastes the whole machine-hour).

---

## Inputs for October 2026

| Input | Value |
| --- | --- |
| Metres made (production logs) | ORD-2001 2,000 · ORD-2002 1,200 · ORD-2003 1,100 · ORD-2004 830 · ORD-2007 300 · **total 5,430** |
| Wages accrued (05–09 Oct, 4.5 days each) | Imran 2,475 · Kavita 2,700 · Suresh 2,925 · Anita 2,250 = **₹10,350** |
| Wages paid on 10 Oct | Imran, Kavita, Suresh = **₹8,100** (Anita ₹2,250 due) |
| Weave-01 | running 10 h (5 Oct) + 6 h (9 Oct) = 16 h × ₹240 = **₹3,840**; made ORD-2001 2,000 m, ORD-2003 600 m |
| Weave-02 | running 8 h (6 Oct) + 4 h (9 Oct) = 12 h × ₹240 = **₹2,880**; made ORD-2002 1,200 m, ORD-2004 450 m |
| Buyer payments received | INV-4001 1,99,500 + INV-4002 26,460 = **₹2,25,960** |
| Raw material bills paid | Gujarat 1,80,000 + South India 20,000 = **₹2,00,000** |

---

## Order ORD-2001 (closed, invoiced ₹1,99,500)

| Component | Working | Value |
| --- | --- | --- |
| Yarn | linked receipt 400 kg × ₹180 | **₹72,000.00** |
| Wages | 10,350 × 2,000 / 5,430 = 3,812.15, + ₹0.01 rounding remainder (largest share) | **₹3,812.16** |
| Machine | Weave-01 3,840 × 2,000 / 2,600 | **₹2,953.85** |
| **Total cost** | | **₹78,766.01** |
| Revenue (est) | invoiced | **₹1,99,500.00** |
| **Margin (est)** | 1,99,500 − 78,766.01 | **₹1,20,733.99** |

## Order ORD-2002 (dispatched, invoiced ₹44,100)

| Component | Working | Value |
| --- | --- | --- |
| Yarn | linked receipt 240 kg × ₹140 | **₹33,600.00** |
| Wages | 10,350 × 1,200 / 5,430 | **₹2,287.29** |
| Machine | Weave-02 2,880 × 1,200 / 1,650 | **₹2,094.55** |
| **Total cost** | | **₹37,981.84** |
| Revenue (est) | invoiced | **₹44,100.00** |
| **Margin (est)** | 44,100 − 37,981.84 | **₹6,118.16** |

ORD-2007 has no linked yarn receipt, so its yarn is an estimate (shown with
"est"): 300 m × 0.2 kg/m × average purchase rate.

---

## The month

| Line | Working | Value |
| --- | --- | --- |
| Buyer payments received | | **+₹2,25,960.00** |
| Raw material bills paid | | **−₹2,00,000.00** |
| Wages paid | | **−₹8,100.00** |
| **Month net (cash basis)** | 2,25,960 − 2,00,000 − 8,100 | **+₹17,860.00 (profit)** |
| Wages due (context, not in net) | Anita | ₹2,250.00 |

**Acceptance:** Dashboard "Profit or loss (this month)" and Reports › Profit /
loss both show **₹17,860.00** for October 2026 (same function), and **₹0.00**
for September 2026.

## Machines (October)

Output 5,430 m (= production logs), running 40 h, idle 7.5 h, breakdown 4 h,
idle loss ₹3,400.00 (Spin-02 5 h × 250, Spin-03 4 h × 250, Weave-03 1.5 h × 400,
Dye-02 1 h × 550). The totals row equals the sum of the rows, and the Dashboard
idle-loss card shows the same ₹3,400.00.

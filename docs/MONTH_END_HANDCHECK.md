# Owner month-end — hand-check (October 2026 seed)

These numbers come straight from `backend/app/seed.py`. After `python -m app.seed`,
the Owner screens for **October 2026** must match this table. All money in ₹.

## Definitions (one everywhere)
- **Order cost** = yarn + wages + machine.
  - **Yarn** = Σ(receipt.quantity_kg × receipt.unit_cost) for receipts linked to the order.
  - **Machine** = power + overhead only (hourly_cost has **no** operator wages),
    allocated by the order's output-metre share × Σ(machine.hourly_cost = 1380).
  - **Wages** = total wages paid in month (₹27,600) × output-metre share.
- **Margin (estimate)** = revenue (output_m × rate) − order cost.
- **Month net (cash)** = buyer payments in − raw-material bills paid − wages paid.

Total output metres (all orders) = **10,200 m**. Machine-cost basis = **₹1,380**.
Wages paid in month = **₹27,600**.

## Cost per order (hand-check 2 orders in detail)

### ORD-2003 (Denim, Blue) — detailed
- Yarn receipt: 600 kg × ₹205 = **₹1,23,000**
- Output = 1800 + 1500 = **3,300 m**; share = 3300/10200 = 0.32353
- Wages = 27,600 × 0.32353 = **₹8,929.41**
- Machine = 1,380 × 0.32353 = **₹446.47**
- **Total cost = ₹1,32,375.88**
- Revenue = 3,300 × ₹120 = **₹3,96,000** → **Margin = ₹2,63,624.12**

### ORD-2001 (Cotton Shirting, White) — detailed
- Yarn: 400 × ₹180 = **₹72,000**
- Output 2,000 m; share 0.19608 → Wages **₹5,411.76**, Machine **₹270.59**
- **Total cost = ₹77,682.35**; Revenue 2,000×₹95 = **₹1,90,000** → **Margin ₹1,12,317.65**

### All orders (expected)
| Order | Output m | Yarn | Wages | Machine | Total cost | Revenue | Margin |
|-------|---------:|-----:|------:|--------:|-----------:|--------:|-------:|
| ORD-2001 | 2000 | 72,000 | 5,411.76 | 270.59 | 77,682.35 | 1,90,000 | 1,12,317.65 |
| ORD-2002 | 1200 | 33,600 | 3,247.06 | 162.35 | 37,009.41 | 1,68,000 | 1,30,990.59 |
| ORD-2003 | 3300 | 1,23,000 | 8,929.41 | 446.47 | 1,32,375.88 | 3,96,000 | 2,63,624.12 |
| ORD-2004 | 1200 | 52,500 | 3,247.06 | 162.35 | 55,909.41 | 1,32,000 | 76,090.59 |
| ORD-2005 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| ORD-2006 | 300 | 28,800 | 811.76 | 40.59 | 29,652.35 | 39,000 | 9,347.65 |
| ORD-2007 | 2200 | 80,080 | 5,952.94 | 297.65 | 86,330.59 | 2,20,000 | 1,33,669.41 |

(ORD-2005 is confirmed but not yet produced → zeros shown as "—" in the UI.)

## Month net — October 2026 (the owner's answer)
| Line | Amount |
|------|-------:|
| Buyer payments in (INV-4001 full ₹1,76,400 + 50% of INV-4002 ₹2,31,000) | **+₹2,91,900.00** |
| Raw-material bills paid (72,000 + 33,600 + 80,080) | **−₹1,85,680.00** |
| Wages paid (4 staff × 6 days × 2 runs) | **−₹27,600.00** |
| **Net** | **+₹78,620.00 (PROFIT)** |

**Acceptance:** Dashboard "Profit or loss (this month)" and Reports → Profit / loss
must both show **₹78,620.00** for October 2026, and both equal
buyer_in − raw_bills − wages above.

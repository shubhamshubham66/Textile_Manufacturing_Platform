# Everest Textile Mills — FAQ Knowledge Base

Upload this file to the Dify app's Knowledge Base so the assistant can answer
product FAQ and how-to. It contains **no private factory data** — only how the
system works.

## What is Everest Textile Mills?
A single web platform that runs a fabric factory end to end — replacing notebooks,
paper slips, registers and phone calls. It covers yarn intake, production, quality,
dispatch, payments, wages, owner reporting, and a buyer portal.

## The 5-step process (order to shipment)
1. **Order** — a buyer places an order (fabric type, colour, quantity in metres,
   deadline, rate).
2. **Yarn** — yarn is received into the store; the system checks there is enough
   for the order and warns if stock is low.
3. **Make** — yarn runs through spinning, weaving and dyeing; machine status
   (running / idle / breakdown) and output are tracked live.
4. **Check** — each roll is inspected: Pass, Rework or Reject, traceable to its
   order and machine.
5. **Ship** — passed rolls are packed and dispatched with a matching invoice;
   finished stock and dispatches are tracked (no double dispatch).

## How do I log in?
Open the site and click **Login** (top-right). Enter your email and password. Your
menu depends on your role: Owner, Store manager, Floor supervisor, Quality
inspector, Accountant, or Buyer. If your login fails, check the email/password or
ask your administrator.

## How does a buyer track an order?
Log in as a buyer and open **My orders**. Each order shows its current stage
(Confirmed → Weaving → Dyeing → Checking → Ready to ship → Shipped), a progress
percentage, and the expected delivery date. Click **Track** for the full stage
view. Buyers can see **only their own** orders and invoices.

## How do I see or download an invoice?
Buyers: open **Invoices** and click **Download PDF** for any of your invoices.
Store managers can print the invoice from the **Dispatch** screen after a dispatch
is confirmed.

## What are the main modules?
- **Orders** — new order, check yarn, confirm.
- **Yarn store / Stock / Purchase** — receive yarn, see live stock + low-stock
  alerts, raise purchase orders.
- **Production / Machines** — assign machines, update status, log output, and see
  idle-machine loss in rupees.
- **Quality / Rolls** — create and inspect rolls, defect report.
- **Dispatch** — pick passed rolls, confirm dispatch, print invoice.
- **Payments / Attendance / Wages** — record payments, mark attendance, calculate
  and pay wages.
- **Owner reports / Dashboard** — cost per order, machine report, profit or loss.
- **Buyer portal** — my orders, track, invoices, ask AI.

## What is the "idle machine loss" feature?
The platform logs when each machine is running, idle or in breakdown, with
timestamps and a reason. It then shows idle hours × the machine's hourly cost as a
rupee loss — so the owner can see money lost to idle machines.

## How is yarn checked against an order?
When you check yarn for an order, the system estimates the yarn needed from the
order quantity and compares it to current stock of the same colour. It tells you
whether there is **enough** or how much you are **short by**, so you can raise a
purchase.

## Can the assistant see my factory data?
Only when you are **logged in**, and only data allowed for your role. A buyer can
see only their own orders and invoices. Before login, the assistant answers general
how-to and FAQ only — it cannot show private factory data.

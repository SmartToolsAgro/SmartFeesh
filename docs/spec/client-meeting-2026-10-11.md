# Client meeting, 2026-10-11

Reported by Mahmoud in Tunisian Arabic and answered point by point in the same session. Where this file
and `project-brief.md` disagree, **this file wins**. Points marked _provisional_ are our reading or a
default we chose; confirm them at the next meeting.

## The big change: profit per lot, not per month

Before, profit was shared with partner suppliers **once a month**, after the month-end closing. Now the
unit is the **lot** (one purchase, our `Batch`): each lot has its own costs and its own profit, and a
partnership is settled lot by lot.

## 1. Purchases and the average cost

- Every purchase is recorded with its weight and price. It goes into a cold room or is sold straight away.
- Buying the same product again two days later at another price makes **a new lot**. Each lot keeps its
  own cost (FIFO, Q7 unchanged).
- The owner also wants the **average purchase price** of a product (weighted by kg, over the stock still
  on hand) to decide the sale price. The average is information for pricing only; profit stays per lot.

## 2. Costs charged to a lot

A lot carries its own costs, added by hand or computed:

- fuel, transport, miscellaneous costs (typed on the lot);
- day labourers who worked on it (from the day-labour calendar, §6);
- monthly-paid employees who worked on it, at **days worked × monthly salary / 26**;
- cold-room cost for the days it spent in a cold room (§3);
- truck costs of the day (transport, labour, miscellaneous): when a truck carries several products from
  several lots, those costs are **split over the lots on board** and added to each as a cost
  (_provisional: by kg loaded_);
- general costs: **rent and the accountant are included too, split "like a salary"**: monthly amount / 26
  per day, and each day's amount split over the lots in stock that day (_by kg held: our reading_).

## 3. Cold-room cost per day

- The owner types the monthly electricity bill. The system splits it over the cold rooms, then over the
  days of the month, giving a **cost per cold room per day**.
- The client has 2 negative cold rooms (−20 °C) and 1 positive one (0 to 4 °C). A −20 °C room uses more
  power, so each cold room gets a **weight** in the split (default: equal weights, the owner can change
  them; confirmed).
- When several lots share a cold room on the same day, that day's cost is split **by kg held**, from the
  stock ledger.
- The bill arrives after the month. Until it is typed, the last month's daily rate is used as an
  estimate, and the lot's figures are corrected when the bill is entered (a lot already settled is not
  reopened; the difference goes to the next settlement, see D-041). Confirmed.

## 4. Profit of a lot (owner's own lots)

- A lot can be sold in pieces: some kg to one customer at one price, some to another at another price.
- Profit of the lot = everything it sold for − its purchase cost − all its costs (§2, §3).
- Spoiled product is a loss of the lot's owner(s); in a partnership the loss is shared.
- **When:** a lot is closed when it is **fully sold and everything is settled** (customers have paid,
  costs are in). Confirmed. This replaces Q9's month-end accrual for profit sharing.

## 5. Lots in partnership

- The owner and a partner buy a lot together: the owner puts x DT, the partner y DT. **The partner is a
  supplier.**
- Optional: charge the owner's monthly employees to the lot (days × salary / 26), plus day labourers,
  transport, cold room, fuel and miscellaneous, as in §2.
- Once the net profit is known, the owner gives the partner **a % of the net profit** and shows them a
  statement: "this is your share".
- **Loss:** the partner shares it; their % of the loss is **deducted from their capital** (Q3 unchanged).
- Confirmed: two rates (profit % and loss %, D-031); one partner per lot; when the lot closes the partner
  gets their capital back ± their share. **A supplier can be a partner in several lots** at once.

## 6. Day-labour calendar

- A calendar: pick a day, record who worked and how much each was paid.
- A day-labour cost typed on a lot appears in the calendar on that day automatically, and a day entered
  in the calendar can be linked to a lot. Same record, two ways in.
- A day can also be general work (organising the stock, the store, cleaning): not linked to a lot, it is
  a general cost.

## 7. Drivers and trucks

- A driver is **not tied to one truck**: truck X today, truck Y tomorrow.
- Both the office and the driver (from the phone) can choose the truck of the day.
- When a truck is loaded, the load carries the **price per kg of each product**, so the driver knows what
  to sell at. When the driver comes back, we see what was sold and what comes back.
- One driver per truck per day (confirmed).

## Still to confirm

- Truck costs of the day: split over the lots on board by kg loaded?
- Rent and accountant "like a salary": is each day's amount (monthly / 26) split over the lots in stock
  that day, as we read it, or charged in full to each lot?
- The actual weights of the −20 °C and 0–4 °C rooms (the owner sets them in the app).

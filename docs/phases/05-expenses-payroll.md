# Phase 5 · Expenses, lot costs, payroll & assets

**Goal:** every cost is in the app, correct and approved, and as much of it as possible is charged to
the lot it belongs to, ready for the lot result (Phase 6).
**Depends on:** Phase 4 live. **Questions:** Q6 answered (fixed monthly salaries, employer CNSS tracked,
6 to 10 employees). Client meeting 2026-10-11 (`docs/spec/client-meeting-2026-10-11.md`, D-041): lot
costs, cold-room cost per day, day-labour calendar, monthly employees at days × salary / 26.
_Coarse plan: detail each task when the phase starts._

---

### P5-T01 · Expenses · M
- [ ] Categories (personnel, day labour, transport, fuel, cold storage, handling, rent, accountant,
      administration, financial, miscellaneous).
- [ ] Expense: date, category, amount, payment method, receipt file, entered by, approval status.
- [ ] **Optional lot:** an expense typed on a lot (fuel, transport, misc.) is a cost of that lot.
      Without a lot it is a general cost (truck, location or "general" tag).
- [ ] Approval workflow; driver expenses from P3-T04 land here.

### P5-T02 · Cold-room cost per day · M
- [ ] Monthly electricity bill per company (or per meter), typed by the owner.
- [ ] A weight per cold room (default equal; −20 °C rooms may weigh more, D-041).
- [ ] Cost per cold room per day, then per lot by kg held that day, from the stock ledger.
- [ ] Before the bill is typed: estimate from the previous month; difference booked when it arrives.

### P5-T03 · Day-labour calendar · M
- [ ] Day labourers (name, phone, usual daily pay). Not employees: no payroll, no CNSS.
- [ ] Calendar screen: pick a day, add who worked, amount paid, optional lot, optional work type
      (organising stock, store, cleaning…).
- [ ] One record, two ways in: day labour typed on a lot shows in the calendar on that day, and a
      calendar entry linked to a lot shows on the lot.

### P5-T04 · Employees and salaries · M
- [ ] Employee profile, position, fixed monthly salary (Q6). No fixed truck (D-042).
- [ ] Monthly salary record (base, bonus, overtime, deductions, employer CNSS contributions) = expense.
- [ ] Salary payments = cash out. Unpaid salaries visible. The expense and the payment are separate records.
- [ ] **Days on a lot:** record that an employee worked n days on a lot → lot cost = n × monthly
      salary / 26 (client). Optional per lot.

### P5-T05 · General costs on lots · S
- [ ] Recurring monthly costs (rent, accountant, insurance); bills that cover several months spread
      over them.
- [ ] Split over the lots sold in the month by their sales (D-041, provisional), shown as one line on
      each lot.

### P5-T06 · Assets and depreciation · S
- [ ] Assets (trucks, cold room, equipment): value, residual value, useful life, method.
- [ ] Monthly depreciation entries generated automatically.

### P5-T07 · Loans · S (only if the client has loans)
- [ ] Loan schedule: interest = expense, principal = not an expense.

### P5-T08 · Screens · M
- [ ] Expenses list/approval, lot costs tab, day-labour calendar, cold-room cost, employees, payroll
      month view, assets.

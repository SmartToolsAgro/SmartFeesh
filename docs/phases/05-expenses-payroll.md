# Phase 5 · Expenses, payroll & assets

**Goal:** every cost of the month is in the app, correct and approved, ready for the month-end closing.
**Depends on:** Phase 4 live. **Questions:** Q6 (payroll).
_Coarse plan: detail each task when the phase starts._

---

### P5-T01 · Expenses · M
- [ ] Categories (personnel, transport, cold storage, handling, administration, financial).
- [ ] Expense: date, category, amount, payment method, receipt file, entered by, approval status.
- [ ] Optional tags: truck, location, batch, or "general". These feed the allocation engine (P6-T04).
- [ ] Approval workflow; driver expenses from P3-T04 land here.

### P5-T02 · Recurring and accrued costs · S
- [ ] Monthly recurring expenses (rent, insurance); bills that cover several months spread over them.

### P5-T03 · Employees and salaries · M · Q6
- [ ] Employee profile, position, assigned truck, pay type.
- [ ] Monthly salary record (base, bonus, overtime, deductions, employer contributions) = expense.
- [ ] Salary payments = cash out. Unpaid salaries visible. The expense and the payment are separate records.

### P5-T04 · Assets and depreciation · S
- [ ] Assets (trucks, cold room, equipment): value, residual value, useful life, method.
- [ ] Monthly depreciation entries generated automatically.

### P5-T05 · Loans · S (only if the client has loans)
- [ ] Loan schedule: interest = expense, principal = not an expense.

### P5-T06 · Screens · M
- [ ] Expenses list/approval, employees, payroll month view, assets.

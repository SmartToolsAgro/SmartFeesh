# Phase 6 · Partnerships, month-end closing & profit sharing → Milestone B

**Goal:** the most important feature. Close a month, compute each partner supplier's share with a clear
explanation, and pay it.
**Done when:** the month used in P0-T02 gives exactly the same result in the app, and a real month is
closed, approved and settled.
**Depends on:** Phase 5 and P0-T02. **Questions:** Q1, Q2, Q3, Q9 and Q11 are answered. One detail is
left for P0-T02 to settle: a loss larger than the supplier's remaining capital (Q3).
_Coarse plan: detail each task when the phase starts._

**Rules from the answers (2026-10-09/10):**
- Q1: each partner supplier gets a % of the net profit of **their own products**.
- Q2: shared costs are split **by nature**: storage costs by kg held in stock; fuel, salaries and
  administration by sales. These rules are verbal agreements, not written in the contracts.
- Q3: capital is **repaid through the profit share** (payments repay capital first, then count as
  profit). In a loss month the supplier **carries their % of the loss, deducted from their capital**.
- Q9: profit on **sales made** (accrual). The accountant checks the closing in the app with their own
  login, then the owner approves.
- Q11: a mix such as Symphonie Marine comes from a single supplier; it is shared like any other product.

---

### P6-T01 · Agreements (versioned) · M
- [ ] Agreement: supplier, type (ordinary purchase, consignment, commission, profit sharing, joint
      investment), dates, products/batches covered, profit %, investment %, profit basis, eligible expense
      categories, allocation method, settlement schedule.
- [ ] New version on every change; batches link to the agreement version in force at receipt.

### P6-T02 · Investments and capital · M
- [ ] Capital ledger per partner: contributions, recoveries, remaining capital. Separate from payables
      and from profit shares.
- [ ] A payment to a partner is allocated to capital recovery first, then to profit share (Q3). The
      balances stay separate; only the allocation order links them.
- [ ] Loss month: the partner's % of the loss is deducted from their capital (Q3). A loss larger than
      the remaining capital: rule to settle in P0-T02.

### P6-T03 · Month-end inventory valuation and COGS · M
- [ ] Stock value at month-end by batch; COGS of the month from sale-line snapshots.
- [ ] Profit is never "purchases − sales": unsold stock stays an asset.

### P6-T04 · Expense allocation engine · L → split
- [ ] Strategy per agreement or per expense category: by revenue, by gross profit, by nature (fuel by truck
      activity, electricity by storage use, spoilage to its batch…), manual by owner.
- [ ] Storage costs: kg held per supplier per day over the month, computed from the stock ledger (Q2).
- [ ] Every allocated dinar is traceable; total allocated equals total expense (no double counting).

### P6-T05 · Profit engine · L → split
- [ ] Pure functions: inputs (snapshotted month data + agreement version) → result with every step shown.
- [ ] Handles profit, zero, loss, unrecovered capital, expenses larger than gross profit.
- [ ] **Golden test:** reproduces `docs/spec/profit-sharing-worked-example.md` to the millime.

### P6-T06 · Monthly closing workflow · M
- [ ] The 10 steps from the brief (§7) with checks: unapproved expenses, unexplained cash differences,
      weight differences, open driver days.
- [ ] Two steps: accountant review, then owner approval (Q9).
- [ ] Approve → lock + snapshot. Reopen only with reason and audit; produces adjustment entries.

### P6-T07 · Settlements and payments to partners · S
- [ ] Payable shares; payments; three balances per partner (trade payable, capital, profit share).

### P6-T08 · Supplier statement PDF · S
- [ ] Monthly statement per partner: sales and costs included, allocations, %, share, payments, balance.

### P6-T09 · Screens · M
- [ ] Prototype's "Partage des bénéfices" and "Clôture mensuelle" pages with real data, plus drill-down
      from any number to the records behind it.

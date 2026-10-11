# Phase 6 · Lot profit, partnerships & month-end closing → Milestone B

**Goal:** the most important feature. Know the net profit of every lot, share a partnership lot's profit
or loss with the partner supplier with a clear explanation, and pay it.
**Done when:** a real lot worked out by hand with the owner (P0-T02, now one lot instead of one month)
gives exactly the same result in the app, and a real partnership lot is closed and settled.
**Depends on:** Phase 5 (lot costs) and P0-T02.
_Coarse plan: detail each task when the phase starts._

**Rules (client meeting 2026-10-11, `docs/spec/client-meeting-2026-10-11.md`, D-040, D-041):**
- Profit is computed **per lot**: what the lot sold for − its purchase cost − its own costs (typed
  costs, day labour, monthly employees at days × salary / 26, cold-room days, share of rent and
  accountant). Spoilage is a cost of its lot.
- A lot is closed when fully sold and settled; its result is then frozen.
- **Partnership lot:** the owner and a partner supplier each put money in. The partner gets their % of
  the net profit; in a loss they carry their % of it, **deducted from their capital** (Q3).
- Still provisional: D-031 (profit % and loss %, uncovered loss carried forward), the partner's
  settlement order (D-040), the cost rules of D-041.
- Q1 (own products only) fits: a partner shares only in the lots they are in.

---

### P6-T01 · Partnership lots · M
- [ ] Partnership on a lot: partner supplier, amount put in by each side, profit %, loss % (D-031). Set
      at receipt (P1-T07 form gets a "partnership" section) or on an open lot before its first sale.
- [ ] The partner's capital is a ledger per partner and lot: contribution, deduction for a loss, return.
      Separate from the trade payable and from the profit share.
- [ ] Provisional, to confirm: one partner per lot.

### P6-T02 · Lot result engine · L → split
- [ ] Pure functions: lot data snapshot (sales lines, purchase cost, cost lines) → result with every step
      shown.
- [ ] Handles profit, zero, loss, lot sold in pieces at different prices, spoilage, a loss larger than
      the partner's capital (D-031).
- [ ] Live view on an open lot ("so far"), frozen result on a closed lot.
- [ ] **Golden test:** reproduces the hand-made lot of P0-T02 to the millime.

### P6-T03 · Lot closing and settlement · M
- [ ] Close a lot: checks (stock 0 or written off, costs in, customer payments as agreed, see the
      meeting's "still to confirm"), then lock + snapshot. Reopen only with reason and audit.
- [ ] Settlement to the partner: capital back ± share; payments; three balances per partner (trade
      payable, capital, profit share).
- [ ] Electricity bill arriving after a lot closed: the difference goes to the partner's next
      settlement (D-041), never by reopening the lot.

### P6-T04 · Partner statement PDF · S
- [ ] Per lot: purchase, sales (customer, kg, price), each cost line, net profit, %, share, payments,
      balance. "Haka bayek": readable by the partner without explanation.

### P6-T05 · Month-end inventory valuation and COGS · M
- [ ] Stock value at month-end by batch; COGS of the month from sale-line snapshots.
- [ ] Profit is never "purchases − sales": unsold stock stays an asset.

### P6-T06 · Monthly closing (accountant) · M
- [ ] Monthly result for the accountant: sales, COGS, costs, net result; checks (unapproved expenses,
      unexplained cash differences, open driver days).
- [ ] Accountant review, then owner approval (Q9). Approve → lock + snapshot. It does not change
      partner shares, which are settled per lot.

### P6-T07 · Screens · M
- [ ] Lot page: sales, costs, result, partner share, with drill-down to every record behind a number.
- [ ] Prototype's "Partage des bénéfices" page reworked as a list of partnership lots (open, closed,
      settled); "Clôture mensuelle" for the accountant.

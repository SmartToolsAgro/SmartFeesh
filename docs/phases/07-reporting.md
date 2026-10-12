# Phase 7 · Reporting & dashboards

**Goal:** the owner sees how the business is doing without asking anyone.
**Depends on:** Phase 6. Load the `dataviz` skill before building any chart.
_Coarse plan: detail each task when the phase starts._

---

### P7-T01 · Dashboard · M
- [x] KPIs from the prototype: sales, cash collected, receivables, net operating result, stock value;
      alerts list. Clearly separate profit from cash.

### P7-T02 · Commercial reports · M
- [x] (D-113) Sales by customer, product, truck, driver, period.
- [ ] Sales by supplier and by payment method.

### P7-T03 · Stock reports · S
- [x] (D-113) Stock value by location; losses and weight differences; slow-moving stock.
- [ ] Batch history (exists per lot on the stock screens; not in the reports page).

### P7-T04 · Financial reports · M
- [x] (D-116) Monthly result, expenses by category, cash flow, customer and supplier balances, unpaid salaries.

### P7-T05 · Partnership reports · S
- [x] (D-117) Capital invested/recovered/outstanding, shares allocated/paid/due per partner over a period.
- [ ] Per-lot breakdown under each partner.

### P7-T06 · Exports · S
- [ ] Every report exports to Excel and PDF (Celery job for large ones).

### P7-T07 · Alerts and notifications · S
- [x] Low stock, overdue customers, cash differences, expiring batches. In-app first; SMS/WhatsApp in Phase 8.

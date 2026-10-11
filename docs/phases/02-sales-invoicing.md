# Phase 2 · Customers, quotes, sales & invoicing

**Goal:** sell from the cold room or a truck, invoice correctly for Tunisia, and always know who owes what.
**Done when:** a quote can become a sale and an invoice; stock and customer balance update in one
transaction; partial payments and returns work; quote/invoice/receipt PDFs look professional.
**Depends on:** Phase 1. **Questions:** Q5, Q7 and Q16 are answered; nothing is open for this phase.
TTN / El Fatoora e-invoicing is not built in this phase (D-016); P2-T05 only keeps a hook for it.

---

### P2-T01 · Customers · S
- [x] `Customer` (type: restaurant, hotel, fish shop, supermarket, wholesaler, caterer, individual; tax ID;
      contacts; credit limit; payment terms; active). "Walk-in customer" default record (D-047).
- [x] Admin list/detail with credit limit and payment terms. Balance and history come with sales and
      payments (P2-T04, P2-T06): the detail page has a placeholder card for them.

### P2-T02 · Prices · M
- [x] "Prix du jour" screen: the owner or manager sets the sale price for every product in one go,
      prefilled with the current one. Each row shows the cost of the batches in stock and the margin,
      since purchase costs also change daily (P1-T07).
- [x] A price can be changed again at any time of the day; the change applies from that moment, and
      the screen shows the day's earlier prices with who changed them and when.
- [x] A sale uses the price in force at the moment it is made (`price_in_force` at `sold_at`, D-049, D-051).
- [x] A sale line keeps the price actually charged; later price changes never touch past sales,
      invoices or profit. A quote keeps its own prices until its validity date. (Invoices: P2-T05.)
- [x] Price lists and customer-specific prices; minimum price per product; warning (not block) below it,
      logged in audit. (API and tests only; no price-list screen yet, D-049.)

### P2-T03 · Quotes (devis) · M
- [x] `Quote` + lines, validity date, statuses (draft, sent, accepted, refused, expired) (D-050): new
      `sales` app, `DV-0001` numbers, price in force kept on the line, discount in %, nightly
      `expire_quotes`, "Devis" screens, demo quotes.
- [x] Convert accepted quote → sale (`create_sale_from_quote`, `convertQuoteToSale`, D-051): accepted and
      still valid, same lines and prices, the quote links to its sale. No stock is reserved. (Button on
      the quote page: P2-T04b.)

### P2-T04 · Sales · L → split in two PRs: T04a backend (D-051), T04b screens (D-052)
- [x] `Sale` + lines from a location (cold room or truck). Lines allocated to batches FIFO at confirmation
      (`post_fifo_movements`), one `SaleLineBatch` per batch.
- [x] Each line stores price, discount, **batch, unit cost** (snapshot) → COGS per line and per lot. Tax:
      empty hook until P2-T05.
- [x] `sales.services.confirm_sale(...)` posts sale movements and sets `amount_due`, all in one transaction.
      The receivable proper (payments, balance, credit limit) is P2-T06: `record_receivable` and
      `check_credit` are the hooks.
- [x] Cancel = reversal (returns to the same batches), never deletion.
- [x] Counter sale at a cold room is a first-class flow (regular, Q8): same service, location = cold room,
      walk-in customer by default. (Quick screen: P2-T04b.)
- [x] T04b: "Ventes" list/detail, sale form, quick counter-sale screen, "Convertir en vente" on a quote,
      a lot's sales on the batch page, Playwright tests.

### P2-T05 · Invoices · M
- [ ] Gap-free numbering per organization per year.
- [ ] Finance settings per organization, with a valid-from date (Q5, D-018): one VAT rate for all
      products (19 %), fiscal stamp (1.000 DT per invoice), whether sale prices include VAT, withholding
      rate. Editable by the owner from a finance settings screen; never hard-coded.
- [ ] Optional VAT rate per product (including exempt) that overrides the company default: Tunisian
      fishing products appear as VAT-exempt in the VAT code, to check with the accountant
      (`docs/spec/sample/README.md`).
- [ ] Withholding tax (retenue à la source): optional per invoice, chosen before it is issued, at the
      rate from the finance settings. When the rate is 0 % nothing about it appears on the invoice.
      It reduces the amount to collect and is tracked in P2-T06.
- [ ] Issued invoice is immutable; corrections via `CreditNote`.
- [ ] Leave a clear hook for TTN e-invoicing (Phase 8 backlog, D-016). Nothing is sent to TTN for now.

### P2-T06 · Customer payments and balances · M
- [ ] `CustomerPayment` (cash, cheque, transfer, card) allocated to invoices; unallocated credit kept.
- [ ] Customer balance, ageing (0–30, 31–60, 60+ days).
- [ ] Credit limit per customer, enforced on the server at sale time for every seller, drivers included
      (Q16). Above the limit the behaviour is a company setting (D-018): block the sale, ask the owner or
      manager for approval, or warn and log.
- [ ] Withholding tax: the amount withheld is recorded against the invoice with its certificate (number,
      date, file); the receivable is reduced; totals per period are available to the accountant.

### P2-T07 · Customer returns · S
- [ ] Return → stock movement back (or to loss) + credit note.

### P2-T08 · PDFs · M
- [ ] WeasyPrint templates for quote, invoice, receipt, credit note, styled like the prototype's quote.
- [ ] Introduce Celery + Redis for generation; files stored in object storage.

### P2-T09 · Admin screens · M
- [ ] Quotes, sales, invoices, customers, payments screens. Customer page shows balance + history.
      (Quotes P2-T03, sales P2-T04b and customers P2-T01 done; invoices, payments and the balance remain.)
- [x] Quick counter-sale screen for the cold room (`/ventes/comptoir`, P2-T04b, D-052).

**Phase acceptance test:** quote 5 kg Crevette Royale at 42.000 → accept → sale from cold room → invoice
210.000 with VAT 19 % (on top or included, per the company setting) + fiscal stamp 1.000 → customer pays
100.000 → balance shows the rest; stock and batch updated; PDF correct.

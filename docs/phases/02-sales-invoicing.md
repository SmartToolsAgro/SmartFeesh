# Phase 2 · Customers, quotes, sales & invoicing

**Goal:** sell from the cold room or a truck, invoice correctly for Tunisia, and always know who owes what.
**Done when:** a quote can become a sale and an invoice; stock and customer balance update in one
transaction; partial payments and returns work; quote/invoice/receipt PDFs look professional.
**Depends on:** Phase 1. **Questions:** Q5 (blocks P2-T05), Q7, Q16.

---

### P2-T01 · Customers · S
- [ ] `Customer` (type: restaurant, hotel, fish shop, supermarket, wholesaler, individual; tax ID; contacts;
      credit limit; payment terms; active). "Walk-in customer" default record.
- [ ] Admin list/detail with balance and history.

### P2-T02 · Prices · S
- [ ] Price lists and customer-specific prices; minimum price per product; warning (not block) below it,
      logged in audit.

### P2-T03 · Quotes (devis) · M
- [ ] `Quote` + lines, validity date, statuses (draft, sent, accepted, refused, expired).
- [ ] Convert accepted quote → sale (optionally reserve stock).

### P2-T04 · Sales · L → split before starting
- [ ] `Sale` + lines from a location (cold room or truck). Lines allocated to batches with `allocate_fifo`.
- [ ] Each line stores price, discount, tax, **batch, unit cost** (snapshot) → COGS per line.
- [ ] `sales.services.confirm_sale(...)` posts sale movements, creates the receivable, all in one transaction.
- [ ] Cancel = reversal document, never deletion.

### P2-T05 · Invoices · M · blocked by Q5
- [ ] Gap-free numbering per organization per year.
- [ ] Tax configuration per product (VAT rate), fiscal stamp, withholding tax if Q5 says so.
- [ ] Issued invoice is immutable; corrections via `CreditNote`.
- [ ] Leave a clear hook for TTN e-invoicing (Phase 8, or earlier if mandatory).

### P2-T06 · Customer payments and balances · M
- [ ] `CustomerPayment` (cash, cheque, transfer, card) allocated to invoices; unallocated credit kept.
- [ ] Customer balance, ageing (0–30, 31–60, 60+ days), credit-limit warning at sale time.

### P2-T07 · Customer returns · S
- [ ] Return → stock movement back (or to loss) + credit note.

### P2-T08 · PDFs · M
- [ ] WeasyPrint templates for quote, invoice, receipt, credit note, styled like the prototype's quote.
- [ ] Introduce Celery + Redis for generation; files stored in object storage.

### P2-T09 · Admin screens · M
- [ ] Quotes, sales, invoices, customers, payments screens. Customer page shows balance + history.

**Phase acceptance test:** quote 5 kg Crevette Royale at 42.000 → accept → sale from cold room → invoice
210.000 + fiscal stamp → customer pays 100.000 → balance shows the rest; stock and batch updated; PDF correct.

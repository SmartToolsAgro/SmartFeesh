# Phase 1 · Catalogue, suppliers & stock

**Goal:** every kilogram is traceable from the supplier to the cold room to a truck, with its batch, cost
and supplier.
**Done when:** the owner can register products and suppliers, receive goods (with real weight), load and
unload trucks, record losses, count stock, and see stock per location and batch, with every quantity
explained by the movement history.
**Depends on:** Phase 0. **Questions:** Q4, Q8, Q10, Q12. If unanswered, use the defaults stated in each
task and mark them in DECISIONS as provisional.
**Out of scope:** customers and sales (Phase 2), the driver's phone screens (Phase 3).

---

### P1-T01 · Units and conversions · S
- [ ] `Unit` (kg, piece, box); per-product `base_unit` (default kg) and optional sale/purchase units with a
      conversion factor (e.g. 1 box = 5.000 kg).
- [ ] Conversion service with tests; quantities stored in base unit only.

Default if Q10 open: everything in kg.

### P1-T02 · Product catalogue · M
- [ ] `Category`, `Product` (name, reference, category, base unit, default sale price, minimum stock,
      storage temperature range, active flag, photo).
- [ ] API (list/filter/search/create/update/archive) + admin screens: list with photo cards like the
      prototype, form with photo upload.
- [ ] Price changes keep history (`ProductPrice` with valid-from date).

### P1-T03 · Suppliers · S
- [ ] `Supplier` (name, tax ID, phone, address, contacts, notes, active). Agreement link comes in Phase 6.
- [ ] API + admin list/detail/form.

### P1-T04 · Locations and trucks · S
- [ ] `StockLocation` (type: cold_room | truck | other, name). `Truck` (plate, name, assigned driver,
      location 1–1).
- [ ] Seed: one cold room, two trucks (adjust after Q8).

### P1-T05 · Batches (lots) · M
- [ ] `Batch` (product, supplier, receipt reference, receipt date, unit cost, expiry/use-by,
      nullable `agreement` placeholder, optional `parent_batches` for mixed products after Q11).
- [ ] Batch number generator (`L-0912` style, per organization).

Default if Q4 open: always create batches (it is harmless if each product has one supplier).

### P1-T06 · Stock ledger and on-hand · L → split before starting
Read: ARCHITECTURE §4 rule 3, DECISIONS D-006.
- [ ] `StockMovement` (append-only): type (receipt, transfer, sale, customer_return, supplier_return,
      loss, adjustment, count_correction), product, batch, from_location, to_location, quantity,
      unit_cost, source document (generic FK), user, timestamp, reason, `client_uuid`.
- [ ] `StockOnHand(location, batch)` cache; `inventory.services.post_movement(...)` updates it in the same
      transaction with `select_for_update`; negative stock refused.
- [ ] `allocate_fifo(product, location, qty)` → list of (batch, qty) oldest first.
- [ ] `rebuild_on_hand()` management command + nightly consistency check.
- [ ] Tests: concurrency (two transfers at once), negative stock refused, rebuild equals cache.

### P1-T07 · Goods receipt from suppliers · M
- [ ] `PurchaseOrder` (optional) → `GoodsReceipt` with lines: ordered qty, invoiced qty, **accepted net
      qty**, gross weight / glaze % (Q12), unit cost → creates batches + receipt movements.
- [ ] Differences (ordered vs accepted) visible on the receipt and in a report.

### P1-T08 · Supplier invoices and payments · M
- [ ] `SupplierInvoice` linked to receipts; due date; status (draft, posted, partly paid, paid).
- [ ] `SupplierPayment` with allocation to invoices. Supplier balance = invoices − payments.
- [ ] Nothing here touches investments or profit shares (separate balances, Phase 6).

### P1-T09 · Transfers cold room ↔ truck · S
- [ ] Transfer document (morning load, evening return) with lines → transfer movements, FIFO batches.
- [ ] Validation by owner/manager; driver confirms receipt in Phase 3.

### P1-T10 · Losses, adjustments and stock counts · M
- [ ] Loss / spoilage with reason and optional photo; above a threshold needs owner approval.
- [ ] `InventoryCount` per location: count sheet, differences, approval → count_correction movements.

### P1-T11 · Stock screens · M
- [ ] Admin stock page like the prototype: location cards, product cards with per-location kg, low-stock badge.
- [ ] Product → batch → movement history drill-down; movement list with filters.

**Phase acceptance test (end-to-end):** receive 60 kg dorade (62 invoiced) → load 15 kg to truck 1 →
record 1.5 kg loss on truck 1 → count cold room → all on-hand numbers match the ledger, and the supplier
balance shows the invoice.

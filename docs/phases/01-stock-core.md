# Phase 1 · Catalogue, suppliers & stock

**Goal:** every kilogram is traceable from the supplier to the cold room to a truck, with its batch, cost
and supplier.
**Done when:** the owner can register products and suppliers, receive goods (with real weight), load and
unload trucks, record losses, count stock, and see stock per location and batch, with every quantity
explained by the movement history.
**Depends on:** Phase 0. **Questions:** Q4, Q8, Q10, Q11 and Q12 are answered; nothing is open for this
phase.
**Out of scope:** customers and sales (Phase 2), the driver's phone screens (Phase 3).

---

### P1-T01 · Units and conversions · S
- [x] `Unit` table seeded with kg only; per-product `base_unit` (always kg for now). The `Product.base_unit`
      field itself is added with `Product` in P1-T02, defaulting to `catalog.selectors.base_unit()`.
- [x] Quantity helpers with tests; quantities stored in base unit only (`core.money.checked_quantity`
      for what a person types, `catalog.selectors.to_base_quantity` for every quantity entering the system).

Q10 answered: everything is sold by kg. Box and piece units and conversion factors are not built now;
the `Unit` table keeps the door open for other distributors (Q17).

### P1-T02 · Product catalogue · M
- [x] `Category`, `Product` (name, reference, category, base unit, default sale price, minimum stock,
      storage temperature range, active flag, photo). Also an Arabic name and a stand-in drawing (D-030).
- [x] API (list/filter/search/create/update/archive) + admin screens: list with photo cards like the
      prototype, form with photo upload.
- [x] Sale prices change from one day to the next, and sometimes several times in one day
      (2026-10-10): `ProductPrice` holds one price per product with a valid-from **date and time**; the
      price in force at a moment is the latest one at or before it. History is never overwritten.

### P1-T03 · Suppliers · S
- [x] `Supplier` (name, tax ID, phone, address, contacts, notes, active). Agreement link comes in Phase 6.
      Also a reference (`F-001`, generated when left empty), e-mail and city; contacts are
      `SupplierContact` rows (D-032).
- [x] API + admin list/detail/form.

### P1-T04 · Locations and trucks · S
- [x] `StockLocation` (type: cold_room | truck | other, name). `Truck` (plate, name, assigned driver,
      location 1–1). Locations in `inventory`, trucks in `fleet`; a truck's name is its location's (D-033).
- [x] Any number of cold rooms and trucks, managed from an admin screen (Q8: 2 cold rooms, 3+ trucks).
      The "Stock frigo & camions" screen shows them as cards; stock figures join it in P1-T11.
- [x] Object-level permission helper "own truck" for drivers (`fleet.selectors.may_use_location`,
      `may_use_truck`), and the driver's truck in `/api/v1/me` (left open by P0-T06).
- [x] A cold room is also a selling point: over-the-counter sales are regular (Q8), used by P2-T04
      (`counter_sales` flag; `sells` is true for every truck).
- [x] Seed (dev only): two cold rooms, three trucks. Real names come from the client's lists.

### P1-T05 · Batches (lots) · M
- [x] `Batch` (product, supplier, receipt reference, receipt date, unit cost, expiry/use-by) in
      `inventory`. The nullable `agreement` key is added by P6-T01 with the agreement table (D-034).
- [x] Batch number generator (`L-0912` style, per organization): `L-0001`, `L-0002`… under a row lock.
- [x] Read-only API (`listBatches`, paginated, filters product / supplier / search; `getBatch`), office
      only. Batches are created by `inventory.services.create_batch`, called by goods receipts (P1-T07).
- [x] Seed (dev only): 15 recent batches of the sample suppliers, dorade from two suppliers (Q4).

Q4 answered: the same product can come from several suppliers in one month; batches keep them apart.
Q11 answered: a mix such as Symphonie Marine comes from a single supplier, so it is an ordinary product
with ordinary batches. No `parent_batches`.

### P1-T06 · Stock ledger and on-hand · L, split into T06a–T06c (2026-10-10)
Read: ARCHITECTURE §4 rule 3, DECISIONS D-006.

#### P1-T06a · Movement ledger, on-hand cache, `post_movement` · M
- [x] `StockMovement` (append-only): type (receipt, transfer, sale, customer_return, supplier_return,
      loss, adjustment, count_correction), product, batch, from_location, to_location, quantity,
      unit_cost, source document (generic FK), user, timestamp, reason, `client_uuid`.
- [x] Which side each type moves: receipt and customer return come in, sale, supplier return and loss
      go out, transfer goes from one location to another, adjustment and count correction go one way.
- [x] `StockOnHand(location, batch)` cache; `inventory.services.post_movement(...)` updates it in the same
      transaction with `select_for_update`; negative stock refused. A repeated `client_uuid` returns the
      movement already posted.
- [x] A location still holding stock cannot be archived (left open by P1-T04).
- [x] Tests: concurrency (two transfers at once), negative stock refused. Demo batches get an opening
      stock and a morning truck load in the seed.

#### P1-T06b · FIFO allocation · S
- [ ] `allocate_fifo(product, location, qty)` → list of (batch, qty) oldest first, over
      `selectors.batches_oldest_first` (D-034), refusing more than the location holds.
- [ ] A helper that posts one movement per allocated batch (used by transfers, sales and losses).

#### P1-T06c · Rebuild and consistency check · S
- [ ] `rebuild_on_hand()` management command + nightly consistency check that reports differences.
- [ ] Tests: rebuild equals cache; a damaged cache is reported, then repaired.

### P1-T07 · Goods receipt from suppliers · M
- [ ] `PurchaseOrder` (optional) → `GoodsReceipt` with lines: ordered qty, invoiced qty (net weight,
      Q12), **accepted net qty**, unit cost → creates batches + receipt movements. No gross-weight or
      glaze fields.
- [ ] Differences (ordered vs accepted) visible on the receipt and in a report.
- [ ] Purchase prices change from one day to the next (2026-10-10): the unit cost is typed on every
      receipt line and belongs to that batch only. There is no fixed supplier price list. The form
      suggests the last cost paid to that supplier for that product and shows the change against it.
- [ ] Purchase price history per product and supplier (date, cost), read from the batches.

### P1-T08 · Supplier invoices and payments · M
- [ ] `SupplierInvoice` linked to receipts; due date; status (draft, posted, partly paid, paid).
- [ ] `SupplierPayment` with allocation to invoices. Supplier balance = invoices − payments.
- [ ] Nothing here touches investments or profit shares (separate balances, Phase 6).

### P1-T09 · Transfers between locations · S
- [ ] Transfer document (morning load, evening return, cold room → cold room) with lines → transfer
      movements, FIFO batches.
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

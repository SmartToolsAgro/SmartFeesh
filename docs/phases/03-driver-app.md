# Phase 3 · Driver app (PWA)

**Goal:** a driver runs a whole working day from their phone, even with weak mobile signal.
**Done when:** one real driver uses it for a full week alongside their usual method, and the evening
totals match.
**Depends on:** Phases 1–2. **Questions:** Q13 (phones, printer), Q14 (language), Q16 (who may sell on credit).
Look and feel: the "Camion" view of `prototype/index.html`.

---

### P3-T01 · Start of day · S
- [ ] Driver confirms the loaded stock (from the P1-T09 transfer) and the starting cash float.
- [ ] Opens a `DriverDay` (truck, driver, date, status).

### P3-T02 · My stock · S
- [ ] Truck stock list with product pictures, kg, price; read-only.

### P3-T03 · Sale on the road · M
- [ ] Choose customer (search, recent first; create if allowed), products, weight, payment amount and
      method → calls the same `confirm_sale` service as the admin app.
- [ ] Partial payment → remainder on customer credit; credit-limit warning.
- [ ] Receipt: on screen + share (and Bluetooth print later if Q13 says so).

### P3-T04 · Expenses on the road · S
- [ ] Fuel, tolls, ice… with a photo of the receipt; status "waiting for approval"; paid from the cash box.

### P3-T05 · Losses and returns · S
- [ ] Report damaged/spoiled product with reason and photo; return unsold stock to the cold room.

### P3-T06 · End-of-day closing · M
- [ ] Summary: sales, cash, other payments, credit sales, expenses, remaining stock.
- [ ] Driver enters counted cash → difference shown neutrally; driver can add a note.
- [ ] Admin review screen: approve or ask for a justification. Approved day is locked.

### P3-T07 · Offline mode · L → split before starting
Read: ARCHITECTURE §4 rule 7.
- [ ] Service worker caches the app; truck stock, customers and prices cached in IndexedDB.
- [ ] Writes go to an IndexedDB queue with `client_uuid`; sync when online; idempotent server endpoints.
- [ ] Sync status always visible ("3 sales waiting to send"). Conflicts (e.g. stock changed by admin)
      are shown to the admin, never silently dropped.
- [ ] Offline sales can only use the truck's own stock, which only that driver changes.

### P3-T08 · Field test · human · M
- [ ] One driver, one week, in parallel with the current method. Collect issues into the next tasks.

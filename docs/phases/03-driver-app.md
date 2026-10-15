# Phase 3 · Driver app (PWA)

**Goal:** a driver runs a whole working day from their phone, even with weak mobile signal.
**Done when:** one real driver uses it for a full week alongside their usual method, and the evening
totals match.
**Depends on:** Phases 1–2. **Questions:** Q13, Q14 and Q16 are answered: Android and iPhone, some dead
zones on the routes, printed and digital receipts, French or Arabic chosen by each driver, credit sales up
to a limit. Receipts are in French. The printer model is chosen in the P3-T10 spike.
Look and feel: the "Camion" view of `prototype/index.html`.

---

### P3-T01 · Start of day · S
- [x] Driver picks the truck of the day if the office has not (D-042, P1-T12); any truck, not a fixed one.
- [x] (shown read-only, D-090) Driver confirms the loaded stock with its price per kg (from the P1-T09 transfer) and the
      starting cash float.
- [x] Opens a `DriverDay` (truck, driver, date, status).

### P3-T02 · My stock · S
- [x] (kg and price, no pictures yet) Truck stock list with product pictures, kg, today's price; read-only.
- [x] (D-148) Prices are refreshed every minute while the phone is online, on reconnect and on focus. A price
      changed during the day raises a notice on every screen until the driver acknowledges it; the sale screen takes
      the new price at once. Offline, the stock and sale screens show when the prices were last received.
- [x] (D-150) The phone sends the price each line showed; the server accepts it only when it was a real price of the
      product in the 24 hours before the sale (else "Ce prix n'est plus valable", refused). A customer's own price list
      wins over the shown price (D-049).
- [x] (D-153) The sale screen shows the price the selected customer pays: their own price list first, else the daily
      price. The stock is read for that customer (`my-stock?customer=`); the daily prices stay while it loads.

### P3-T03 · Sale on the road · M
- [x] (search, D-091; a new customer on the phone, online only, D-152) Choose customer (search, recent first; create if
      allowed), products, weight, payment amount and
      method → calls the same `confirm_sale` service as the admin app.
- [x] (online only) Partial payment → remainder on customer credit, up to the customer's credit limit (Q16). Offline,
      the limit is checked against the last synced balance and checked again by the server at sync.
      Above the limit the app follows the company setting from P2-T06 (block, approval, or warn).
- [x] Receipt: on screen + share. Printing is P3-T10.

### P3-T04 · Expenses on the road · S
- [x] Fuel, tolls, ice… with a photo of the receipt; status "waiting for approval"; paid from the cash box.

### P3-T05 · Losses and returns · S
- [x] Report damaged/spoiled product with reason and photo; return unsold stock to the cold room.

### P3-T06 · End-of-day closing · M
- [x] Summary: sales, cash, other payments, credit sales, expenses, remaining stock; per product,
      loaded vs sold vs returned (client meeting 2026-10-11).
- [x] Driver enters counted cash → difference shown neutrally; driver can add a note.
- [x] (approved day locks its closing, D-094) Admin review screen: approve or ask for a justification. Approved day is locked.
- [x] (D-134) Sending the closing closes the day: nothing more goes on it. One day per driver and date; a load
      validated that date opens the same day again (also an approved one), and the driver sends it again. Each
      send a load undid is kept, and its counted cash is "already handed over" at the next count.
- [x] (D-134) "Mes journées" on the phone: the driver's past days, and the answer to the office's question sent
      from there. The office page searches by driver or truck and filters by dates.
- [x] (D-132, D-134) The office sees where the day's records differ from what the driver sent (a sale made
      before the send and received after it) and cannot approve until the driver sends the day again.

### P3-T07 · Offline mode · L → split into T07a to T07d, in this order
Read: ARCHITECTURE §4 rule 7. Keep it invisible to the driver: the app just works with weak signal, and one
small line says how many things are waiting to be sent.

#### P3-T07a · Installable app and cached screens · S
- [x] (hand-written service worker, D-096) PWA: service worker caches the app shell; "add to home screen" works on
      Android and iPhone; the app opens with no signal once it has been opened once.
- [x] (Cache Storage, no timestamp yet) Data read by the screens (stock, customers, today's prices, day summary) is kept in IndexedDB and
      shown while offline, with the time it was last updated.
- [x] A small banner shows "Hors ligne" when there is no connection.

#### P3-T07b · Queue for sales · M
- [x] Sales are written to an IndexedDB queue with their `client_uuid` and sent when the connection
      returns, in order; the server already ignores a `client_uuid` it has seen (D-091).
- [x] The queue count is always visible ("3 ventes en attente"); a sale shows as "en attente" on the
      receipt until sent.
- [x] Offline, the sale screen uses the last downloaded stock and customers; stock of the truck is
      reduced locally per queued sale so the driver cannot sell more than the truck holds.
- [x] (D-133) A sale is dated when it was made, not when it is sent: the phone sends the time, the server checks
      it (not in the future, a day not approved, the driver's truck and its stock of that day).

#### P3-T07c · Queue for expenses, losses and closing · S
- [x] (returning the unsold stock still needs signal) Same queue for expenses (with the photo kept locally), losses and the day closing.
- [x] The closing is refused offline with a clear message until everything queued is sent.

#### P3-T07d · Conflicts · S
- [x] A queued write the server refuses (stock changed by the office, credit limit) is kept, shown to
      the driver in plain words and to the office on `/journees`; never silently dropped.
- [x] (the notice to the driver is not built yet, D-099) Offline sales can only use the stock of the driver's truck of the day, which only that driver
      changes that day (office transfers to that truck during the day show as a notice).

### P3-T08 · Field test · human · M
Runs last, after P3-T09 and P3-T10.
- [ ] One driver, one week, in parallel with the current method. Collect issues into the next tasks.

### P3-T09 · Arabic for the driver app · M
Moved here from the Phase 8 backlog (Q14: each driver chooses French or Arabic).
- [x] Language choice on the login screen and in the driver's profile; remembered per user (P0-T08).
- [x] (provisional, D-103) All truck-app strings translated to Arabic.
- [ ] Translation reviewed by a native speaker (human).
- [ ] Right-to-left layout checked on every screen; weights and amounts stay readable.
- [ ] Server messages (validation errors) come back in the driver's language.

The admin app stays in French for now.

### P3-T10 · Bluetooth receipt printing · L → split before starting
Moved here from the Phase 8 backlog (Q13: printed and digital receipts, Android and iPhone).
- [ ] **Spike first:** print from the PWA on a real Android phone and a real iPhone with the chosen
      printer. If the browser cannot print on iPhone, wrap the truck app as a native app (Capacitor,
      ARCHITECTURE §5). Record the result in DECISIONS; it revisits D-002 and D-003.
- [ ] No printer is chosen yet (Q13): propose two or three models, pick one with the client and buy it
      for testing (human).
- [ ] Receipt layout for the paper width; works offline; reprint from the sale screen.
- [ ] The receipt is in French (Q13), whatever language the driver uses in the app.
- [ ] If native: store accounts, builds, and getting the app onto the drivers' phones (human + agent).

### P3-T11 · Collecting customer payments on the phone · S
- [x] Driver picks a customer (with what they owe), types the cash received, saves; offline-safe (D-111).
- [x] The payment is allocated to the customer's oldest open sales (the P2-T06 service) and counted in the day's expected cash.

### P3-T12 · Buying at the port (achat terrain) · L → split into T12a to T12c, in this order (added 2026-10-15, D-157, Q28)
A driver buys from a fisherman or at the port, sends it from the phone; the owner or the manager checks it; only then
do the stock, the supplier debt and the payment count.

**P3-T12a · Office side: the purchase, its revisions and its validation · M**
- [x] `FieldPurchase` (`AT-2026-0001`): supplier or a proposed new name, day, the deal (comptant, N days, end of month
      + N days), supplier's paper number (optional), lines (product or a proposed new name, kg said, kg received, price),
      money given at the port (cash, cheque, transfer, traite; reference, cashing day), boxes, notes both ways.
- [x] Statuses: sent → validated or refused. Every save is a revision (full copy, who, when, what changed); a save on
      an older revision is refused ("changed meanwhile").
- [x] Validation (owner or manager): a BR (kg received, cost; the kg said kept as the line's "ordered" weight), a posted
      FF for the kg received with the due date of the deal, an RF per payment given allocated to it (any rest is an
      advance). Partner per line: owner only, as on a receipt.
- [x] Admin: "À valider" tab in Achats (list, review page: map a new name to a product or supplier, fix kg and prices,
      note to the driver, save, validate, refuse; revision history). Dashboard alert: purchases waiting, late after 24 h.

**P3-T12b · Phone: the purchase screen · M**
- [x] A "can buy" switch per driver (owner sets it on the account; the server refuses the others).
- [x] The phone screen: supplier (list or new name), products (list with photo, or new name), kg, price (last price
      paid as a hint), money given (cash or cheque), rest to pay; photo of the supplier's paper (optional). Works
      offline like a sale; edits after sending need network. The driver sees his purchases, their status and the
      office's note; not what the company owed the supplier before. _(The product list shows names, no photos; the photo of the supplier's paper moved to T12c.)_
- [x] The purchase float: the office gives the driver a sum for purchases in the morning; the closing counts it and
      the money given (expected cash = … + float − purchases paid in cash).

**P3-T12c · Paying suppliers · M**
- [ ] "Dettes fournisseurs": owed per supplier, overdue, due this week; cheques and traites to be cashed by day.
- [ ] The office receipt form gets the deal too, so a delivery to the cold room is owed at once (a posted FF), like a
      purchase at the port; the payment form gets the cashing day of a cheque or traite.
- [ ] Monthly settlement: the supplier statement of the month (D-156) as the paper to agree on and pay.
- [ ] The photo of the supplier's paper on a purchase at the port (from the phone, optional; seen by the office).


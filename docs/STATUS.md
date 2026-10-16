# Project status

_Last updated: 2026-10-16 (truck load split by client, P2-T13, D-160; before that buying at the port, D-157 and D-158)_

## Where we are

- **Phase:** Phase 1 is done except P1-T14 (returnable boxes, owner decisions 2 to 4 open). Phase 2 (sales) is mostly
  done, Phase 5 (costs) is done, Phase 6 has T01 to T03 done. **Phase 3 (driver app) has T01 to T07d, T11, T12a and T12b done, and
  the price and offline items of T02 and T03 done**; open: T12c (paying suppliers), T08 field test, T09 Arabic
  review, T10 printing.
- **New owner request (2026-10-15, Q28, D-157): buying at the port.** A driver buys from a fisherman, sends it from the
  phone; the owner or the manager checks it (kg received, prices, revisions with notes) and validates it, which makes
  the BR, the FF due by the deal and the RF of what was given. T12a (office, #156) is merged; T12b (phone, "can buy"
  switch, purchase money counted apart at closing, notice of the office's decision) is on branch `field-purchase-phone`.
- **On `main` since the last update:** the company logo as the driver's tab icon, also on the login screen (D-147,
  #138); prices refreshed every minute with a notice on every screen when a price changes (D-148, #140); a driver's
  sale carries the price the phone showed, checked by the server (D-150, #142); expenses, losses, payments and box
  pickups keep the moment the phone says, so they count in the day they were made (D-151, #143); a driver adds a
  customer on the phone and the stock shows product photos (D-152, #144); the sale screen shows the price the chosen
  customer pays (D-153, #145); "Aujourd'hui" at the top of the day (D-149, #141).
- **Staging** (D-036, D-155, `docs/runbook.md`): admin http://app.fruttidelmare.com, driver
  http://ch.fruttidelmare.com (phase 1 of the domain; HTTPS is phase 2, after the certificate). Demo logins `owner` / `driver` (password in `~/frutti-staging/.env`
  on the server). Every merge to `main` deploys staging; check `gh run list`.
- **The plan (2026-10-11, `docs/spec/client-meeting-2026-10-11.md`):** profit per lot, shared with partners (D-040);
  a driver's truck is chosen per day (D-042). Q21 confirmed; Q24 (truck-cost split) still provisional.
- **How we work:** one branch and one PR per task; CI green, then merge with `gh pr merge --merge`. Decision numbers
  are handed out in advance: check `main` before taking one (D-146 and D-147 were both taken in parallel this week).

## Next step (do this first)

- **P2-T13 / D-160 (branch `load-per-client`):** a load cold room → truck can name the clients; validating it leaves a
  draft BL per client (address changeable on that BL only, small/big boxes). Check on staging: Stock › Transferts › new
  load, "Ajouter un client", validate, open the client's BL, print it (PROVISOIRE), confirm it. **Next:** the driver phone
  (list the load by client, confirm each delivery); a driver sees only the sales they made. D-159 is on PR #159.
- **P3-T12c, paying suppliers** (`docs/phases/03-driver-app.md`): the "Dettes fournisseurs" screen (owed, overdue,
  due this week; cheques and traites by cashing day, `SupplierPayment.cash_on`), the deal on the office receipt form
  (a posted FF at once), the cashing day on the payment form, the monthly statement, the photo of the supplier's paper.
- **Check on staging with a real phone (D-158):** switch "Peut acheter au port" on for the demo driver (Paramètres ›
  Utilisateurs), start a day with purchase money, buy (one new product name, cash + cheque), then validate it at the
  office and see the notice on the phone; close the day and count the purchase money.
0. **Domain and HTTPS (D-155, `docs/runbook.md` "Domain and HTTPS"):** the owner adds the two DNS `A` records
   (`app` and `ch` → 217.182.205.137); merge phase 1 and check the names answer; on the server run the
   certbot webroot command; then phase 2 (443, HTTPS settings, https origins) in a new PR.
1. **Owner decisions still open:**
   - Backups (D-139, runbook "Backups"): create the off-site storage and put its credentials in `.env`; move the backup
     private key to a password manager and a USB key.
   - Boxes: the company's 50 small and 50 big boxes are in the ledger (D-135). Still open: boxes already at clients or
     owed to suppliers, and a screen to type an opening stock on a real database.
   - Driver day (D-134): does the driver always hand over exactly the cash counted at the first send? Should the load
     screen warn before it reopens an approved day?
   - Price rule (D-150): a sale on a stale price is refused after 24 hours. Owner to confirm the window.
   - Archived records (D-145): confirm they leave every dropdown except the one a saved record uses.
   - Approved electricity bills under the daily rule are not recalculated (D-142, owner to decide).
2. **Check on staging (D-156):** open a customer's and a supplier's "Relevé (PDF)" and check the layout by eye.
3. **Check on staging with a real phone:** the company logo in the driver header and on the login screen (after one login; D-154); a price change during a sale (notice, new price,
   sale refused on a stale price); a late expense and a payment (dated the day they were made); a customer added on the
   phone; product photos in the stock list; a sale to a customer with a price list (the price shown is the list price).
4. **Phase 3, in this order:** P3-T10 printing spike (needs a real Android and iPhone and a printer, human), P3-T09
   Arabic review and right-to-left check (human reviewer), P3-T08 one-week field test.
5. **Phase 3 gaps (not yet tasks):** a truck sale should use the load's price (D-051); a customer added on the phone is
   not marked in the office; the office closing table does not show the opening stock or the gap yet (D-130).
6. **Other waves:** P2-T07/T08/T09, P6-T04 to T07 (check `gh pr list` and `docs/phases/` for what landed).

## Blockers / waiting on client

- **P0-T02** (worked example): now **one real lot** worked out by hand with the owner. Phase 6 has no target without it.
- **P0-T01**: no prototype walk-through or client materials yet (stand-ins in `docs/spec/sample/`).
- **P0-T11 human items:** DNS for `app.` and `ch.fruttidelmare.com` and the certificate (D-155; the domain is
  chosen, the records are not yet there); the owner creates a Sentry project and puts
  its DSN in `.env` (runbook "Monitoring", D-140).
- **TTN / El Fatoora is on hold** (D-016) although Q5 says it is required now.
- **For the accountant** (`docs/spec/sample/README.md`): the VAT code lists Tunisian fishing products as exempt, which
  does not match "19 % for all"; e-invoicing is mandatory since 01/01/2026. Employee CNSS rate 9,18 % is provisional
  (D-119, Q26).
- **Provisional, to confirm with the client:** supplier due date +30 days and payment methods (D-043); loss approval
  threshold 2 kg (D-045); no supplier credit note yet; default credit policy `block`; ageing from invoice/sale date;
  a loss beyond the partner's capital stays on the profit-share balance (D-066); no owner override with reason to close
  a lot with unpaid sales (D-068); a customer added on the phone has no credit until the office sets one (D-152).

## Watch out

- **The staging VPS is shared with other clients' production sites.** Touch only `frutti-staging` (containers, folder,
  nginx site); run `sudo nginx -t` before any reload; never prune Docker there.
- Mahmoud's Windows machine: `gh` is at `C:\Program Files\GitHub CLI\gh.exe`. No `make`, `pnpm`, `docker` or `psql` on
  the PATH: `npx -y pnpm@10.28.0 <command>` works; `uv` is at `C:\Users\ITDT\.local\bin\uv.exe`. A PostgreSQL 18 server
  is at `C:\Program Files\PostgreSQL\18\bin`: start a test cluster in the scratchpad on a free port (5433 was taken) and
  set `DATABASE_URL`. **UTF8 is required** (`initdb -E UTF8 --locale=C`).
- Parallel branches collide on the same shared files: `frontend/packages/i18n/src/fr.ts` and `ar.ts` (keep each task's
  keys in its own block), the generated API client (regenerate with `pnpm gen-api` after `spectacular`, never hand-merge),
  `App.tsx` routes, `seed_dev.py`, `ENUM_NAME_OVERRIDES` in `config/settings/base.py`, and `DECISIONS.md` and
  `OPEN_QUESTIONS.md` (keep number order; on a merge, keep both entries and renumber your own).
- Migrations: two branches can write the same migration number for one app; renumber after the merge and point its
  dependency at the newest migration.
- Run `make lint` before every commit (or `make hooks` once); CI runs the same checks.
- API: 401 = not logged in, 403 = role not allowed (D-023). Every view sets a permission class, scopes its queryset with
  `.for_organization(org)` (D-022) and names its operation with `operation_id` (D-026).
- UI: no hard-coded text (`packages/i18n/src/fr.ts` + `t()`); `formatMoney` / `formatQuantity` / `formatDate`; logical CSS
  classes (D-025); token colours only (D-024); API calls through `@frutti/api`.
- Stock changes only through `inventory.services.post_movement` or `post_fifo_movements` (D-035, D-037); never write
  `StockOnHand`.
- `origin/wip-snapshot-2026-10-13` is a snapshot of old uncommitted work, kept for the record: do not merge it.
- CI runs on `ubuntu-24.04`, pinned (#115): `ubuntu-latest` moves to Ubuntu 26 from 2026-10-19. Move on purpose.

## Recently done

- 2026-10-16 · D-160 truck load by client (P2-T13): `TransferLine/BoxLine.customer`, `TransferDelivery`, `Sale.transfer`
  and `Sale.delivery_address`, draft BL per client on `load_validated`, provisional BL PDF with address and boxes.
- 2026-10-16 · D-158 buying at the port from the phone (P3-T12b): "can buy" switch, phone screen (offline), "Mes
  achats" with the office's note and a notice on its decision, purchase money as a second cash box at closing.
- 2026-10-15 · D-157 buying at the port, office side (P3-T12a): `FieldPurchase` with revisions, check page, validation
  into BR + FF + RF, refusal, dashboard alert, demo purchase `KRK-0917`. Check it on staging (Achats › Achats terrain).
- 2026-10-15 · D-156 statement PDF of a customer or a supplier ("Relevé (PDF)" on their page): up to a day or between
  two days; products, kg and prices of each BL/BR, payments, running balance, boxes, summary. Check the layout on staging.
- 2026-10-15 · D-154 the driver sees the company logo: the logo endpoint lets every member read it (the driver got 403),
  and the phone keeps a copy for the login screen and the tab icon (corrects D-147; on this branch, not yet merged).
- 2026-10-15 · quote form: each product in the list shows its kilos in stock and the places holding them, fullest
  first (`LinesGrid` `places`, `placesOf`; not yet on the sale screens).
- 2026-10-15 · D-153 the sale screen shows the price the selected customer pays (`my-stock?customer=`), closing D-150's
  display gap (#145).
- Earlier: the driver app wave D-145 to D-152, closing D-134, costs D-142, ops D-139 to D-141; boxes D-124 to D-127, closing D-128 to D-131, invoice PDF D-125, documents D-131 and D-138: see git log.

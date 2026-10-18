# Project status

_Last updated: 2026-10-18 (public site with orders and quote requests, site products with a web price, D-184)_

## Where we are

- **D-184 (branch public-site):** a public, animated site (`frontend/apps/site`, :5175; Artlist video and photos):
  catalogue with web prices, basket, order or quote request with a **required phone number**. The office gets a bell
  notification and handles requests in "Site web → Demandes du site"; "Site web → Produits du site" adds and removes
  products, hides them, orders them and sets a **web-only price** (the day's price never changes). Awaits CI.
- **D-183 (branch receipt-product-search):** in "Nouvelle réception" the product cell is an empty box: typing a code,
  name, Arabic name or category lists the matching products, as in a quote or a sale. Awaits CI, then check on staging.
- **D-181 (branch field-purchase-paid-limit):** a port purchase whose sums given exceed its amount is refused (server,
  phone and office form); a lot counted lighter at the office still turns the extra into an advance. Awaits CI.
- **D-180 (on main):** the "Parcours" map and the phone's GPS tracking are switched off (flags, code kept). Check on staging.
- **D-179 (branch money-confirm-popup):** every money action of the driver app (delivery, sale, payment, expense,
  purchase, opening cash and float, closing) opens an "Annuler / Confirmer" window with the amounts. Awaits CI.
  Admin money forms are not converted yet; new money screens must use `ConfirmButton`.
- **P2-T15 / D-178 (branch load-delivery-workflow):** the BL of a load is validated at the load (real BL number, no
  PROVISOIRE), then the driver delivers it in full, in part or not at all from the phone (also offline); only what is
  delivered is sold, the rest stays on the truck; versions, PDF "Commandé / Livré", notifications. Awaits CI.
- **P3-T15 / D-175 (on main):** a bell in both apps; a driver's action notifies the office,
  the office's action notifies the driver, with a tone and a toast (polling every 20 s). Check on staging.
- **D-173 (on main):** the new receipt's product lines are a bordered spreadsheet table. Check on staging.
- **Phase 1:** done except P1-T14 (returnable boxes; owner decisions 2–4 are open). **Phase 2:** mostly done.
- **Phase 3:** T01–T07d and T11–T12c are done; open: T08 field test, T09 Arabic review, T10 printing.
- **P2-T13 / D-160:** load parts, draft BL per client, provisional PDF and driver-phone "Mes livraisons" are implemented
  on `load-per-client` / PR #160. CI identified a formatting issue in the corrected test; it is fixed, and CI must pass
  before merge.
- **On main:** D-176/158 cover buying at the port from the office and phone; D-159 covers supplier debts, payments and
  the supplier-paper photo. Staging checks for these and D-156's statement PDF remain.
- **Staging** (D-036, D-155, `docs/runbook.md`): admin http://app.fruttidelmare.com, driver
  http://ch.fruttidelmare.com. Demo logins `owner` / `driver`; password is in `~/frutti-staging/.env` on the server.
  Every merge to `main` deploys staging; check `gh run list`.
- **Plan:** profit per lot shared with partners (D-040); driver's truck chosen per day (D-042). Q21 confirmed; Q24
  (truck-cost split) remains provisional.
- **Working rule (owner, 2026-10-16):** do not run tests locally; commit and let CI check, then fix reported failures.
  One branch and one PR per task; merge only after CI passes.

- **P2-T14 / D-174 (branch transfer-load-grid):** transfer form as a spreadsheet grid per client, "Chambres froides
  (toutes)" as the source, driver "Vente" lists only the load's clients. CI must pass, then check on staging.

## Next step

0. D-184: merge after green CI (new app `storefront`, migration 0001). On staging put products on the site in
   "Site web → Produits du site" (`seed_dev` does it for dev data), open 127.0.0.1:18083 through an SSH tunnel, add
   2 products, send an order with a wrong then a right phone, see the bell and "Demandes du site", change a web
   price in "Produits du site" and reload the site. To publish it: owner DNS for `www.fruttidelmare.com` (or the root), add the name to the certificate, to
   `DJANGO_ALLOWED_HOSTS` and a host-nginx block to 127.0.0.1:18083. Ask the owner for the phone/e-mail to show and
   to read the page's texts (D-184, provisional).
0. D-183: merge after green CI; on staging open Achats → Nouvelle réception, type "dor" in the product cell, take
   "Dorade royale" with Enter: the cursor moves to the next weight and the last cost appears.
0. D-181: merge after green CI; on staging, on the phone type more cash than the total (the "Envoyer" button stays off
   with a red line), and on the office check page lower a price below what was given (error on the last payment).
   Open owner questions from the same review: what a refused purchase does with cash already paid at the port, and
   whether a big gap between the driver's kg and the kg received should warn or block.
0. D-179: merge after green CI; on staging with a phone, check each money button opens the window and "Annuler" sends
   nothing. Then ask the owner whether the admin app's money forms need the same window.
0. P2-T15: merge after green CI; on staging, load two clients, print both BLs (no PROVISOIRE), on the phone deliver one
   in part (one product at zero) and mark the other "Non livré"; check the truck stock, the client balance, the bell, and
   reprint the corrected BL ("Commandé / Livré", version 2).
0. P3-T15: merge after green CI; on staging, log in as `driver` on a phone and `owner` on a PC: start the day / sell →
   the office bell rings; validate a load → the phone rings. Tune the 20 s poll if it is too slow or too heavy.
1. Push the CI fixes for PR #160, wait for green CI, then merge. After deployment, check a load with two clients on
   staging: change one address, validate, print both provisional BLs, confirm one, and verify the driver's "Mes livraisons".
2. Check D-159 on staging (overdue invoice, cheque cashing day, receipt owed at once, monthly supplier statement and
   supplier-paper photo); check D-158 with a real phone (port purchase, office decision notice and closing money).
3. Check D-156's customer and supplier statement PDFs by eye.
4. Phase 3 order: P3-T10 printing spike (real Android/iPhone and printer), P3-T09 Arabic and RTL review, P3-T08
   one-week field test. P3-T14 (D-171) gets a phone check on staging before the field test.

## Open owner decisions

- Backups: configure off-site storage and move the private key to a password manager and USB key (D-139).
- Boxes: opening balances already at clients or owed to suppliers, and a screen for real opening stock (D-135).
- Driver day: exact cash handover on the first send; warning before a load reopens an approved day (D-134).
- Confirm the 24-hour stale-price window (D-150), archived-record dropdown behavior (D-145), and whether approved
  electricity bills under the daily rule are recalculated (D-142).

## Blockers / watch out

- P0-T02: only one real lot has been worked out with the owner; Phase 6 has no target without it. P0-T01: no prototype
  walk-through or client materials yet.
- DNS records and the certificate for `app.` and `ch.` remain owner actions (D-155); Sentry DSN is also pending (D-140).
- TTN / El Fatoora is on hold (D-016). Accountant confirmation is needed for VAT exemptions and e-invoicing; CNSS
  employee rate remains provisional (D-119, Q26).
- Staging VPS is shared: touch only `frutti-staging`; run `sudo nginx -t` before reload; never prune Docker.
- Keep generated API files in sync (`make gen-api` after serializer/endpoint changes); preserve each branch's i18n keys.
- CI stays pinned to `ubuntu-24.04` (#115); move off it deliberately before the hosted image changes on 2026-10-19.

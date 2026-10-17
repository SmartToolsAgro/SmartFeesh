# Project status

_Last updated: 2026-10-17 (notifications office ⇄ drivers with a tone, P3-T15 / D-175; receipt grid, D-173)_

## Where we are

- **P3-T15 / D-175 (branch driver-admin-notifications):** a bell in both apps; a driver's action notifies the office,
  the office's action notifies the driver, with a tone and a toast (polling every 20 s). Awaits CI, then check on staging.
- **D-173 (on main):** the new receipt's product lines are a bordered spreadsheet table. Check on staging.
- **Phase 1:** done except P1-T14 (returnable boxes; owner decisions 2–4 are open). **Phase 2:** mostly done.
- **Phase 3:** T01–T07d and T11–T12c are done; open: T08 field test, T09 Arabic review, T10 printing.
- **P2-T13 / D-160:** load parts, draft BL per client, provisional PDF and driver-phone "Mes livraisons" are implemented
  on `load-per-client` / PR #160. CI identified a formatting issue in the corrected test; it is fixed, and CI must pass
  before merge.
- **On main:** D-175/158 cover buying at the port from the office and phone; D-159 covers supplier debts, payments and
  the supplier-paper photo. Staging checks for these and D-156's statement PDF remain.
- **Staging** (D-036, D-155, `docs/runbook.md`): admin http://app.fruttidelmare.com, driver
  http://ch.fruttidelmare.com. Demo logins `owner` / `driver`; password is in `~/frutti-staging/.env` on the server.
  Every merge to `main` deploys staging; check `gh run list`.
- **Plan:** profit per lot shared with partners (D-040); driver's truck chosen per day (D-042). Q21 confirmed; Q24
  (truck-cost split) remains provisional.
- **Working rule (owner, 2026-10-16):** do not run tests locally; commit and let CI check, then fix reported failures.
  One branch and one PR per task; merge only after CI passes.

- **D-161 (PR load-print-fiche):** the validated load page has a banner and a "Fiche client" button per client.
- **P3-T14 / D-171 (PR #174, on main):** the driver app scrolls less (tiles, folding cards, sticky main action, back
  link in the header, recent customers). Check it on staging with a phone; the decision number was D-168 in the PR.

- **D-162 (PR #163):** Journées des chauffeurs has a live follow-up tab per driver, truck and day; awaits CI, then check on staging.
- **D-163 (PR #164, branch client-remarks-2026-10-17):** the client's 11 remarks of 2026-10-17 (shares in %, price floor, boxes,
  truck condition, partnership edits, XLS tables, frozen header). CI must pass before merge; then check on staging.

- **P2-T14 / D-174 (branch transfer-load-grid):** transfer form as a spreadsheet grid per client, "Chambres froides
  (toutes)" as the source, driver "Vente" lists only the load's clients. CI must pass, then check on staging.

## Next step

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

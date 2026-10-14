# Project status

_Last updated: 2026-10-14_

## Where we are

- **Phase:** 1 is done except P1-T14 (returnable boxes): steps 1 to 4 are merged, with owner decisions 2 to 4 open.
  Phase 2 (sales) is mostly done, Phase 5 (costs) is done, Phase 6 has T01 to T03 done, and **Phase 3 (driver app)
  has T01 to T06 done**. Phase 0 agent work is done; its human items are under Blockers.
- **On `main`:** the driver app (D-090 to D-094), the lot picker on counter sales (D-121), the month closing with
  partner shares (D-122), Paramètres with the company logo, users and own profile (D-123), employee CNSS withheld
  from gross (D-119, #93), the invoice PDF in the client's paper layout with the uploaded logo everywhere (D-125, #99),
  the returnable boxes ledger, admin screen and driver steps (D-124, #95, #97, #98, #100).
  Every merge to `main` deploys staging.
- **Staging** (D-036, `docs/runbook.md`): admin http://admin.217-182-205-137.sslip.io:8095, driver
  http://chauffeur.217-182-205-137.sslip.io:8096. Demo logins `owner` / `driver`, password in
  `~/frutti-staging/.env` on the server. Check that the last deploy of `main` succeeded (`gh run list`).
- **The plan changed (2026-10-11, `docs/spec/client-meeting-2026-10-11.md`):** profit is computed and shared
  **per lot**, not per month (D-040); lot costs as in D-041; a driver's truck is chosen per day (D-042).
  Q21 (rent split) is confirmed; Q24 (truck-cost split) is still provisional.
- **How we work:** agents open and merge PRs with `gh` only on green CI, after checking the PR is clean against
  `origin/main`. Several agents work in parallel, each in its own worktree and branch. Decision numbers are
  handed out in advance; check `main` before taking one. The client is not available: build with the stand-in
  data of `docs/spec/sample/`.

## Next step (do this first)

1. **Owner decisions still open:**
   - Backups (D-139, runbook "Backups"): **create the off-site storage and put its credentials in `.env`**
     (`BACKUP_S3_*` in `~/frutti-staging/.env`, lines already there), and move the backup private key
     (`C:\Users\ITDT\frutti-backup-key\frutti-backup-PRIVATE-key.asc` on Mahmoud's machine) into a password manager and
     onto a USB key, then delete it there.
   - Boxes, opening balance: **the company's own boxes are done (D-135):** 50 small and 50 big, posted by `seed_dev`
     as an opening stock ("Stock initial") into "Chambre froide 1 (frais)". The cold room is an assumption: ask the
     owner where they are. Still open, not built: boxes already at clients or owed to suppliers (the sign for
     suppliers), and a screen or command to type an opening stock on a real database.
   - Product codes on staging (D-126): **done 2026-10-13.** 2 codes written (crevette royale, Calamar) and 36
     products created from the owner's list, with no price, in the category "À classer". The owner sets their
     prices on the price board and sorts them into categories.
   - Driver day after the closing: **decided 2026-10-14, merged (#114, D-134; with #118, D-132).** Sending the
     closing closes the day; a load validated that date opens the same day again, also an approved one; the cash
     counted before is "already handed over". No second day on a date. A day whose records changed after it was
     sent (a late sale, an office decision on an expense or a loss) is sent again before the office can approve it;
     a past day is sent again from "Mes journées". **To do:** check on staging with a real phone (send, load
     again, sell, send again; the same on an approved day).
   - Still to ask the owner (D-134 assumes it): does the driver always give the office exactly the cash counted at
     the first send? And should the load screen warn before it reopens an approved day?
   - Staging check: no owner check yet of the closing fixes (D-129, D-130, D-133) on a real phone.
   - Uncommitted work in the shared checkout: resolved 2026-10-13. Its code was already on main, its one
     unfinished piece (Q21 confirmed) is merged (#111), and the checkout is back on `main`.
   - Done since the last update (answers recorded): truck expected boxes = real ledger balance (D-124 decision 2,
     built in #107); box actions offline (decision 3, #107); truck-to-cold-room return (decision 4, #107); supplier
     boxes must be returned, no schedule; boxes on a load stay a field on the load transfer (#106); "Frais" is a real
     field (D-126, #103).
2. **Browser check on staging** of the new screens: Paramètres, Utilisateurs, Mon profil (D-123); the driver box
   screens (D-124, #100); the invoice PDF (D-125).
3. Phase 3 remaining, in this order: **P3-T07a to T07d** (offline), **P3-T09** Arabic, **P3-T10** printing.
4. Phase 3 gaps (not yet tasks): an approved day should block more sales and expenses that day (D-094); a driver
   cannot collect a customer payment on the phone yet; recent customers first and creating a customer on the phone
   (D-091); a truck sale should use the load's price (D-051); the office's closing table does not show the opening
   stock or the gap yet (D-130); expenses, losses, payments and box pickups kept on the phone are still dated when
   they are sent, and a driver cannot close a day that is over (D-133 dates sales only).
5. Other waves: P2-T07/T08/T09, P6-T04 to T07 (check `gh pr list` and `docs/phases/` for what landed).

## Blockers / waiting on client

- **P0-T02** (worked example) is not started; it is now **one real lot** worked out by hand with the owner.
  Phase 6 has no target without it. D-031's uncovered loss and Q24 are provisional; Q21 is confirmed.
- **P0-T01**: no prototype walk-through or client materials yet (stand-ins in `docs/spec/sample/`).
- **P0-T11 human items:** a domain for HTTPS (staging is plain HTTP, D-027); **owner to do: create a Sentry project
  and put its DSN in `.env`** (`SENTRY_DSN` for the API, `SENTRY_DSN_FRONTEND` for the apps, then redeploy;
  runbook "Monitoring", D-140).
- **TTN / El Fatoora is on hold** (D-016) although Q5 says it is required now.
- **For the accountant** (`docs/spec/sample/README.md`): the VAT code lists Tunisian fishing products as exempt,
  which does not match "19 % for all"; e-invoicing is mandatory since 01/01/2026. Employee CNSS rate 9,18 % is
  provisional (D-119, Q26).
- **Provisional, to confirm with the client:** supplier due date +30 days and payment methods (D-043); loss approval
  threshold 2 kg (D-045); no supplier credit note yet (a posted invoice cannot be corrected).
- **Provisional (P2-T06, P6-T03):** default credit policy `block`; ageing runs from invoice/sale date; a loss beyond
  the partner's capital stays on the profit-share balance (D-066); no customer-credit refund yet; no owner override
  with reason to close a lot with unpaid sales (D-068).

## Watch out

- **The staging VPS is shared with other clients' production sites.** Touch only `frutti-staging` (containers,
  folder, nginx site); run `sudo nginx -t` before any reload; never prune Docker there.
- Mahmoud's Windows machine: `gh` is at `C:\Program Files\GitHub CLI\gh.exe` (logged in as `mahmoudnjeh95`). No
  `make`, `pnpm`, `docker`, `psql` or gettext on the PATH; `npx -y pnpm@10.28.0 <command>` works. For Playwright,
  put a `pnpm.cmd` shim (`@npx -y pnpm@10.28.0 %*`) on the PATH. For tests, `initdb -A trust -E UTF8 --locale=C` a
  PostgreSQL 18 cluster in the scratchpad on its own port and set `DATABASE_URL`. **The UTF8 encoding is required**
  (the default WIN1252 breaks the Arabic tests). Logins can take 5 s when several agents run.
- Parallel branches always collide on the same shared files: `frontend/packages/i18n/src/fr.ts` (keep each task's
  keys in its own block), the generated API client (regenerate, never hand-merge), `App.tsx` routes, `seed_dev.py`
  and its test, `ENUM_NAME_OVERRIDES` in `config/settings/base.py` (every enum named `kind`/`status`/`method` needs
  an entry), and `DECISIONS.md` and `OPEN_QUESTIONS.md` (keep number order, check `main` before taking a number).
- Run `make lint` before every commit (or `make hooks` once); CI runs the same checks.
- API: 401 = not logged in, 403 = role not allowed (D-023). Every view sets a permission class, scopes its queryset
  with `.for_organization(org)` (D-022) and names its operation with `operation_id` (D-026).
- UI: no hard-coded text (`packages/i18n/src/fr.ts` + `t()`); `formatMoney` / `formatQuantity` / `formatDate`;
  logical CSS classes (D-025); token colours only (D-024); API calls through `@frutti/api`.
- Stock changes only through `inventory.services.post_movement` or `post_fifo_movements` (D-035, D-037); never write
  `StockOnHand`. Nobody picks batches by hand except on the counter sale (D-121); take stock with `post_fifo_movements`.
- `origin/wip-snapshot-2026-10-13` is a snapshot of old uncommitted work, kept for the record. Nothing in it is
  missing from `main`: do not merge it.
- CI runs on `ubuntu-24.04`, pinned (#115): `ubuntu-latest` moves to Ubuntu 26 from 2026-10-19. Move on purpose.

## Last sessions (2026-10-13 and 2026-10-14)

Team-lead session. Merged to `main`: #92 (lot picker), #96 (sidebar), #97 and #98 (box steps 2 and 3), #99 (invoice
PDF, D-125), #100 (box step 4), #101 (box docs, D-124), #102 (Arabic box texts, provisional), #103 (Frais and product
codes, D-126), #105 (month-cost changes, D-128), #106 (boxes entered on a receipt and a load, D-127), #107 (box
follow-up, decisions 2 to 4), #108 (closing after a sale, D-129), #110 (opening stock and gap, D-130), #111 (Q21),
#112 (document header and footer, D-131), #113 (sale dated when made, D-133), #115 (CI image pinned), #116 (create
the missing articles), #118 (D-132). Every merge deployed to staging.

**2026-10-14, PR #114 reworked on the owner's new rule (D-134):** `main` merged in (with D-132), the numbered
second day removed (`DriverDay.number`, the driver's "Commencer une nouvelle journée"), a load of the date reopens
the sent day (`inventory.services.load_validated` → `dayclose.services.reopen_days_after_load`), the undone sends
kept in `DayReopening` with the cash handed over, the history kept. Merged 2026-10-14 (#114), after #118 (D-132)
and #119 (D-135); later the same night #120 to #126 (D-136 to D-138, expenses month filter, archived records hidden
in pickers, documents opened in a window, Prettier fix). `main` CI green. Two decisions had both been numbered
D-137: "Nouveau document" in a window is D-138, and D-135 to D-138 are back in number order.

## Recently done

- 2026-10-14 · P4-T04 monitoring (D-140): Sentry in the API and both apps (off without a DSN), the nightly stock
  check records its run (`/api/v1/health/stock-check`), and `.github/workflows/uptime.yml` checks staging every
  15 minutes; a failure e-mails through GitHub. Runbook "Monitoring".
- 2026-10-14 · P4-T03 / D-139 nightly backups on staging (02:30 UTC, `debian` crontab): database and media, gpg to a
  public key, 30 days in `~/frutti-staging/backups/`, off-site copy ready but waiting for a bucket; restore drill done
  (99 tables identical, stock check clean) with `deploy/restore.sh`.
- 2026-10-14 · D-138 "Nouveau document" on Documents opens the creation form in a window (no page change), with a
  guard: Escape or an outside click asks before a half-filled form is dropped. In PR #123 (`document-new-window`);
  unit tests, lint, tsc and the Documents e2e spec (4 tests) pass.
- 2026-10-14 · D-137 pickers hide archived places, products, trucks, categories and suppliers (unless the current
  value); the counter-sale lot picker shows place (green), lot (yellow), supplier (grey, gold + "partenaire" for a
  partner). Frontend only, on branch `worktree-dropdown-archived-lot-colors`.
- 2026-10-14 · Admin sale form and counter sale warn at once when the typed price is under the product's minimum
  (D-049 follow-up; warning only).
- 2026-10-14 · D-136 "Dépenses" opens on this month, with ‹ › to the months before and a "Période" switch that
  keeps the two free dates (Mahmoud's request). Frontend only.
- 2026-10-14 · D-134 sending the closing closes the driver's day; a load of that date reopens it, also when
  approved; the next count is less the cash already handed over; the driver's history of days (#114).

- 2026-10-13 · D-135 the company's 50 small and 50 big boxes are in the ledger as an opening stock (new movement
  kind `opening`, into a location, no supplier owed); `seed_dev` posts them once into "Chambre froide 1 (frais)".
- 2026-10-13 · D-132 a driver day worked on after it was sent (a new load, more sales) can be sent again; the office
  cannot approve it until then (staging report).
- 2026-10-13 · D-126 follow-up: `set_product_codes --create-missing` creates the articles of the owner's list that
  match no product (code, name, kg, category "À classer", no price). Applied on staging: 2 codes written, 36 created.
- 2026-10-13 · D-131 every document (quote, delivery note, credit note, receipt, partner statement) uses the
  invoice's header and footer, in PDFs and on screen (#112). A PDF already generated keeps its old layout until
  its document or the logo changes.
- 2026-10-13 · D-133 a driver's sale is dated when it was made (the phone sends the time, the server checks it): that
  day's price and closing; refused in the future, on an approved day, or for kilos the truck did not hold that day.
- 2026-10-13 · Q21 confirmed by the owner: general costs (rent, accountant) are split each day over the lots in
  stock by kg held, the same way as the cold room. Docs only: the code already did this (P5-T05).
- 2026-10-13 · Driver Clôture showed "vendu" above "chargé" (staging): the truck's opening stock was missing from the
  day; now shown per product with the gap, and a "Retour à Ma journée" button on every driver screen (D-130).
- 2026-10-13 · D-129 driver closing after a sale: the closing says why sales wait (no connection, no answer, server
  busy, session ended), sends them on open and has a retry; a send gives up after 25 s; busy-server errors keep the
  sale pending; a sale already recorded is answered, not refused (#108). The Arabic texts are provisional.
- 2026-10-13 · D-128 editing a monthly cost template updates its generated months not yet approved; the
  month screen refreshes after expense changes (#105).
- 2026-10-13 · D-127 boxes entered on a receipt and on a load in the admin, and the empty Caisses page links to them (#106).
- 2026-10-13 · D-124 box follow-up: truck balance, offline box actions, truck-to-cold-room return (#107).
- 2026-10-13 · P1-T14 returnable boxes, steps 1 to 4 (D-124): ledger and service (#95), receipt and transfer
  hooks (#97), admin "Caisses" page (#98), driver sale with boxes, pickups and day view (#100).
- 2026-10-13 · D-125 invoice PDF in the client's paper layout; uploaded logo on PDFs, admin and driver headers and
  the tab icon (#99).
- 2026-10-13 · Admin sidebar: data import in its own Administration group (#96).
- 2026-10-13 · D-119 employee CNSS withheld from gross (#93); D-123 Paramètres: company logo, users, own profile (#94).
- 2026-10-13 · D-122 month closing: each partner's share of shared costs, clickable figures.
- 2026-10-12 · D-121 counter sale lot picker (#92); P2-T11 Documents page; P3-T01 to P3-T06 (driver app).

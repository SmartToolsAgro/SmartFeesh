# Project status

_Last updated: 2026-10-13_

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
   - Boxes, opening balance: boxes already at clients, in cold rooms or owed to suppliers. Needs a design first
     (a movement kind with one side outside the ledger; the sign for suppliers). Not built.
   - Product codes on staging (D-126): the owner answered (ART0047 for "Maklouba rosé congelé M0", ART0055 unassigned).
     The dry run and the apply are **not run yet**: the server access needed for them was not granted.
     Dry run first, then apply after the owner approves the list.
   - Staging check: no owner check yet of the closing fix (D-129) on a real phone.
   - Done since the last update (answers recorded): truck expected boxes = real ledger balance (D-124 decision 2,
     built in #107); box actions offline (decision 3, #107); truck-to-cold-room return (decision 4, #107); supplier
     boxes must be returned, no schedule; boxes on a load stay a field on the load transfer (#106); "Frais" is a real
     field (D-126, #103).
2. **Browser check on staging** of the new screens: Paramètres, Utilisateurs, Mon profil (D-123); the driver box
   screens (D-124, #100); the invoice PDF (D-125).
3. Phase 3 remaining, in this order: **P3-T07a to T07d** (offline), **P3-T09** Arabic, **P3-T10** printing.
4. Phase 3 gaps (not yet tasks): an approved day should block more sales and expenses that day (D-094); a driver
   cannot collect a customer payment on the phone yet; recent customers first and creating a customer on the phone
   (D-091); a truck sale should use the load's price (D-051).
5. Other waves: P2-T07/T08/T09, P6-T04 to T07 (check `gh pr list` and `docs/phases/` for what landed).

## Blockers / waiting on client

- **P0-T02** (worked example) is not started; it is now **one real lot** worked out by hand with the owner.
  Phase 6 has no target without it. D-031's uncovered loss, Q21 and Q24 are provisional.
- **P0-T01**: no prototype walk-through or client materials yet (stand-ins in `docs/spec/sample/`).
- **P0-T11 human items:** a domain for HTTPS (staging is plain HTTP, D-027); a Sentry project and its DSN.
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
- Uncommitted work once sat in the shared checkout with no owner. It is saved on `origin/wip-snapshot-2026-10-13`,
  not for merge: it no longer applies to `main`. Its owner should decide whether to rework or drop it.

## Last session (2026-10-13)

Team-lead session. Merged to `main`: #92 (lot picker), #96 (sidebar), #97 and #98 (box steps 2 and 3), #99 (invoice
PDF, D-125), #100 (box step 4), #101 (box docs, D-124), #102 (Arabic box texts, provisional), #103 (Frais and product
codes, D-126), #105 (month-cost changes, D-128), #106 (boxes entered on a receipt and a load, D-127), #107 (box
follow-up, decisions 2 to 4), #108 (closing after a sale, D-129). Open PRs: none. Staging runs of #100 passed.

## Recently done

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

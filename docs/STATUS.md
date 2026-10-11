# Project status

_Last updated: 2026-10-11_

## Where we are

- **Phase:** 1 · Catalogue, suppliers & stock, nearly done: only P1-T11 (stock screens) is left. Phase 2
  has started with P2-T01. Phase 0 agent work is done; its human items are under Blockers.
- **On `main`:** P1-T02 to P1-T10 and P1-T12, P2-T01, and the client-meeting plan (PRs #3 to #17).
  Every merge to `main` deploys staging.
- **Staging** (D-036, `docs/runbook.md`): admin http://admin.217-182-205-137.sslip.io:8095, driver
  http://chauffeur.217-182-205-137.sslip.io:8096. Demo logins `owner` / `driver`, password in
  `~/frutti-staging/.env` on the server. Check that the last deploy of `main` succeeded
  (`gh run list`).
- **The plan changed (2026-10-11, `docs/spec/client-meeting-2026-10-11.md`):** profit is computed and
  shared **per lot**, not per month (D-040); lot costs: day labour, employees at days × salary / 26,
  cold room per day, truck costs of the day split over the lots on board, rent and accountant "like a
  salary" (D-041); a driver's truck is chosen per day (D-042). Q21 (rent split) and Q24 (truck-cost
  split) are still provisional.
- **How we work (2026-10-11):** Mahmoud lets agents open and merge PRs (green CI only) with `gh`;
  `.claude/settings.json` allows `gh pr merge`. Several agents work in parallel, each in its own
  worktree and branch; agents never edit this file, the orchestrator does. Decision numbers are handed
  out in advance. The client is not available: build with the stand-in data of `docs/spec/sample/`.

## Next step (do this first)

1. Agent: **P1-T11** stock screens: location cards with per-location kg, product cards, low-stock badge,
   product → batch → movement drill-down, and the **average purchase price** per product (D-040).
2. In parallel: **P2-T02** prices and **P2-T03** quotes (read `docs/phases/02-sales-invoicing.md`);
   P2-T04 sales is split first. Sales must call `partners.services.ensure_walk_in_customer` for counter
   sales (D-047).
3. Later in Phase 3: a narrow customer endpoint for drivers (drivers get 403 on `/customers`, D-047),
   a driver-side screen to pick the truck of the day (API exists, D-046), driver confirmation of loads
   (fields exist on transfers, D-044).
4. Mahmoud: check the apps on staging; upload one product photo.

## Blockers / waiting on client

- **P0-T02** (worked example) is not started; it is now **one real lot** worked out by hand with the
  owner (purchase, sales, each cost, partner share). Phase 6 has no target without it. D-031's
  uncovered loss, Q21 and Q24 are provisional; P0-T02 should confirm them.
- **P0-T01**: no prototype walk-through or client materials yet (stand-ins in `docs/spec/sample/`).
- **P0-T11 human items:** a domain for HTTPS (staging is plain HTTP, D-027); a Sentry project and its DSN.
  The CI deploy key logs in as `debian` (full sudo): a separate server or a server-side pull is advised.
- **TTN / El Fatoora is on hold** (D-016) although Q5 says it is required now.
- **For the accountant** (`docs/spec/sample/README.md`): the VAT code lists Tunisian fishing products as
  exempt, which does not match "19 % for all"; e-invoicing is mandatory since 01/01/2026. Supplier
  invoices carry no VAT until then (D-043).
- **Provisional, to confirm with the client:** supplier due date +30 days and payment methods (D-043);
  loss approval threshold 2 kg (D-045); no supplier credit note yet (a posted invoice cannot be corrected).

## Watch out

- **The staging VPS is shared with other clients' production sites.** Touch only `frutti-staging`
  (containers, folder, nginx site); run `sudo nginx -t` before any reload; never prune Docker there.
- Mahmoud's Windows machine: `gh` is at `C:\Program Files\GitHub CLI\gh.exe` (logged in as
  `mahmoudnjeh95`). No `make`, `pnpm`, `docker`, `psql` or gettext on the PATH;
  `npx -y pnpm@10.28.0 <command>` works. For Playwright, put a `pnpm.cmd` shim
  (`@npx -y pnpm@10.28.0 %*`) on the PATH. For tests, `initdb -A trust -E UTF8 --locale=C` a PostgreSQL
  18 cluster in the scratchpad on its own port (5433, 5434…: parallel sessions each use their own) and
  set `DATABASE_URL`. **The UTF8 encoding is required** (the default WIN1252 breaks the Arabic tests).
  The machine is slow when several agents run: logins can take 5 s, so Playwright may need longer
  timeouts locally (do not commit them).
- Parallel branches always collide on the same shared files: `frontend/packages/i18n/src/fr.ts` (keep
  each task's keys in its own block), the generated API client (regenerate, never hand-merge),
  `App.tsx` routes, `seed_dev.py` and its test, `ENUM_NAME_OVERRIDES` in `config/settings/base.py`
  (every enum named `kind`/`status`/`method` needs an entry), and `DECISIONS.md` (keep number order).
- Run `make lint` before every commit (or `make hooks` once); CI runs the same checks.
- API: 401 = not logged in, 403 = role not allowed (D-023). Every view sets a permission class, scopes its
  queryset with `.for_organization(org)` (D-022) and names its operation with `operation_id` (D-026).
- UI: no hard-coded text (`packages/i18n/src/fr.ts` + `t()`); `formatMoney` / `formatQuantity` /
  `formatDate`; logical CSS classes (D-025); token colours only (D-024); API calls through `@frutti/api`.
- Stock changes only through `inventory.services.post_movement` or `post_fifo_movements` (D-035, D-037);
  never write `StockOnHand`. Nobody picks batches by hand: take stock with `post_fifo_movements`.

## Last session (2026-10-11)

First parallel wave, four agents (Opus for T08 and T09/T10, Sonnet for T12 and P2-T01):
- **P1-T08** (PR #15, D-043): supplier invoices `FF-0001` linked to receipts, payments `RF-0001` with
  allocation, supplier balance (owed, overdue, advances). Supplier payments live in `purchasing`.
- **P1-T09** (PR #14, D-044): transfers (load, return, between places) validated FIFO; a load carries
  the day's price per kg; "truck's day" view loaded / returned / sold-or-lost.
- **P1-T10** (PR #17, D-045): losses with reason, photo and owner approval above a threshold; stock
  counts with approval posting `count_correction` movements.
- **P1-T12** (PR #16, D-046): `TruckAssignment` per date; one driver per truck and one truck per driver
  per day; "Camions du jour" panel.
- **P2-T01** (PR #13, D-047): customers with credit limit and terms, walk-in customer, admin screens.
- An API rate limit interrupted three agents once; their worktrees were intact and they resumed.

## Recently done

- 2026-10-11 · P1-T08, P1-T09, P1-T10, P1-T12, P2-T01 (first parallel wave)
- 2026-10-11 · Plan updated after the client meeting (per-lot profit)
- 2026-10-11 · P1-T07 goods receipts
- 2026-10-11 · P1-T06c rebuild and nightly check

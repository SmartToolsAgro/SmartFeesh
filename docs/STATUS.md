# Project status

_Last updated: 2026-10-10_

## Where we are

- **Phase:** 1 · Catalogue, suppliers & stock. Phase 0 agent work is done; its human items are listed
  under Blockers.
- **Staging is live:** admin http://admin.217-182-205-137.sslip.io:8095, driver
  http://chauffeur.217-182-205-137.sslip.io:8096 (one host name per app, D-036, `docs/runbook.md`).
  Demo logins `owner` / `driver`, password in `~/frutti-staging/.env` on the server.
- **On `main`:** P1-T02 to P1-T06a (PRs #3 to #6), the staging seed fix and the host names.
- **Waiting for merge:** `p1-t06b-fifo` (P1-T06b) and the docs-only `docs-profit-loss-rates` (D-031).
  `gh` is not installed on Mahmoud's machine and agents may not merge to `main` without his approval.
- **Next task:** P1-T06c · Rebuild and consistency check (`docs/phases/01-stock-core.md`).
- The client is not available: keep building the plan with the stand-in data of `docs/spec/sample/`
  (Mahmoud, 2026-10-10) and adjust when real requirements arrive.

## Next step (do this first)

1. Check that the deploy of PR #6 ran: staging should show the ledger tables migrated, and the 15 demo
   batches received into the cold rooms with Camion 1 loaded once (`client_uuid`s fixed: later deploys
   move nothing). Open the apps by their new names and check that the owner (admin) and the driver
   (driver app) stay logged in side by side in one browser.
2. Merge `p1-t06b-fifo`, then `docs-profit-loss-rates`. Both append to `docs/DECISIONS.md`: on a conflict
   keep both entries. Upload one product photo on staging: the `frutti-staging_media` volume must be
   writable.
3. Agent: P1-T06c from `main` (or `p1-t06b-fifo`): `rebuild_on_hand` management command that sums the
   ledger per (location, batch), compares with `StockOnHand`, reports differences and repairs them only
   when asked; a nightly run (no Celery yet: a cron line on the server, or Celery beat when it arrives).

## Blockers / waiting on client

- **P0-T02** (worked example on one real month) is not started. Phase 6 has no target without it. The
  rule for a loss larger than a supplier's remaining capital is provisional (D-031); P0-T02 should
  confirm it.
- **P0-T01**: no prototype walk-through or client materials yet (stand-ins in `docs/spec/sample/`).
- **P0-T11 human items:** a domain for HTTPS (staging is plain HTTP, D-027); a Sentry project and its DSN.
  The CI deploy key logs in as `debian` (full sudo): a separate server or a server-side pull is advised.
- **TTN / El Fatoora is on hold** (D-016) although Q5 says it is required now.
- **For the accountant** (`docs/spec/sample/README.md`): the VAT code lists Tunisian fishing products as
  exempt, which does not match "19 % for all"; e-invoicing is mandatory since 01/01/2026.

## Watch out

- **The staging VPS is shared with other clients' production sites.** Touch only `frutti-staging`
  (containers, folder, nginx site); run `sudo nginx -t` before any reload; never prune Docker there.
- Mahmoud's Windows machine: no `make`, `pnpm`, `docker`, `psql` or gettext on the PATH;
  `npx -y pnpm@10.28.0 <command>` works. For Playwright, put a `pnpm.cmd` shim
  (`@npx -y pnpm@10.28.0 %*`) on the PATH. For tests, `initdb -A trust` a PostgreSQL 18 cluster in the
  scratchpad on its own port (5433, 5434…: parallel sessions each use their own) and set `DATABASE_URL`.
- Run `make lint` before every commit (or `make hooks` once); CI runs the same checks.
- API: 401 = not logged in, 403 = role not allowed (D-023). Every view sets a permission class, scopes its
  queryset with `.for_organization(org)` (D-022) and names its operation with `operation_id` (D-026).
- UI: no hard-coded text (`packages/i18n/src/fr.ts` + `t()`); `formatMoney` / `formatQuantity` /
  `formatDate`; logical CSS classes (D-025); token colours only (D-024); API calls through `@frutti/api`.
- Stock changes only through `inventory.services.post_movement` or `post_fifo_movements` (D-035, D-037);
  never write `StockOnHand`. Nobody picks batches by hand: take stock with `post_fifo_movements`.

## Last session (2026-10-10)

- **P1-T06b:** `selectors.allocate_fifo` (preview of the oldest-first split, refuses more than held) and
  `services.post_fifo_movements` (locks the product's rows at both locations, posts one movement per
  batch, refused as a whole, idempotent per request with `uuid5(client_uuid, n)`) (D-037).
- Fixed this file: the merges of PRs #4 to #6 had left two versions of several lines.
- Local results: 250 backend tests (two trucks loaded at once never take the same kilos; 8 crossed
  loads and returns without deadlock, run three times), ruff, mypy, import boundaries. No API or screen
  changed, so no client regeneration or Playwright run.

## Recently done

- 2026-10-10 · P1-T06b FIFO allocation
- 2026-10-10 · P1-T06a stock ledger and on-hand cache
- 2026-10-10 · Staging: one host name per app; CI deploy green end to end (PR #4)
- 2026-10-10 · P1-T05 batches

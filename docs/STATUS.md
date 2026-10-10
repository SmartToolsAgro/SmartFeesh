# Project status

_Last updated: 2026-10-10_

## Where we are

- **Phase:** 1 · Catalogue, suppliers & stock. Phase 0 agent work is done; its human items are listed
  under Blockers.
- **Staging is live:** admin http://217.182.205.137:8095, driver http://217.182.205.137:8096
  (`docs/runbook.md`). Demo logins `owner` / `driver`, password in `~/frutti-staging/.env` on the server.
- **Done, waiting for merge (stacked, merge in this order):** `p1-t02-products` → `p1-t03-suppliers` →
  `p1-t04-locations`. None is deployed yet. A docs-only branch `docs-profit-loss-rates` (D-031) also waits.
- **Next task:** P1-T05 · Batches. Another Claude session agreed to take it, stacked on `p1-t04-locations`.
- The client is not available: keep building the plan with the stand-in data of `docs/spec/sample/`
  (Mahmoud, 2026-10-10) and adjust when real requirements arrive.

## Next step (do this first)

1. Merge the three task branches into `main` in order once CI is green (each PR then shows one task).
   `docs-profit-loss-rates` and `p1-t03-suppliers` both append to `docs/DECISIONS.md`: keep every entry,
   in number order (D-031, D-032, D-033).
2. The merge deploys staging by itself (CI job `deploy-staging`): check it ran. It adds the Docker volume
   `frutti-staging_media` and the demo products, suppliers, cold rooms and trucks. Then upload one
   product photo on staging: the volume must be writable by the `app` user.
3. Agent: P1-T05 (`Batch` in `inventory`, supplier and product read through `partners` / `catalog`
   selectors), then P1-T06. Same patterns: per-field `ValidationError` (D-030), scoped base views,
   demo data in `apps/demo`.

## Blockers / waiting on client

- **P0-T02** (worked example on one real month) is not started. Phase 6 has no target without it. The
  rule for a loss larger than a supplier's remaining capital is now provisional (D-031, branch
  `docs-profit-loss-rates`); P0-T02 should confirm it.
- **P0-T01**: no prototype walk-through or client materials yet (stand-ins in `docs/spec/sample/`).
- **P0-T11 human items:** a domain for HTTPS (staging is plain HTTP, D-027); a Sentry project and its DSN.
  CI deploy secrets are set; the key logs in as `debian` (full sudo), so a separate server or a
  server-side pull from GitHub is still advised (runbook).
- **TTN / El Fatoora is on hold** (D-016) although Q5 says it is required now.
- **For the accountant** (`docs/spec/sample/README.md`): the VAT code lists Tunisian fishing products as
  exempt, which does not match "19 % for all"; e-invoicing is mandatory since 01/01/2026.

## Watch out

- **The staging VPS is shared with other clients' production sites.** Touch only `frutti-staging`
  (containers, folder, nginx site); run `sudo nginx -t` before any reload; never prune Docker there.
  Disk is 83% full (13 GB free).
- The Docker dev stack (`make dev`) has not been run yet; the production images have (staging).
- Mahmoud's Windows machine: no `make`, `pnpm`, `docker`, `psql` or gettext on the PATH;
  `npx -y pnpm@10.28.0 <command>` works. The PostgreSQL 18 service on 5432 has no `frutti` role
  and its password is unknown; for tests, `initdb -A trust` a cluster in the scratchpad on port 5433.
- Run `make lint` before every commit (or `make hooks` once); CI runs the same checks.
- API: 401 = not logged in, 403 = role not allowed (D-023). Every view sets a permission class, scopes its
  queryset with `.for_organization(org)` (D-022) and names its operation with `operation_id` (D-026).
- UI: no hard-coded text (`packages/i18n/src/fr.ts` + `t()`); `formatMoney` / `formatQuantity` /
  `formatDate`; logical CSS classes (D-025); token colours only (D-024); API calls through `@frutti/api`.
- VAT rate, stamp, prices with or without VAT, withholding rate and the over-credit-limit behaviour are
  organization settings (D-018). Purchase and sale prices change daily (D-020).

## Last session (2026-10-10)

- **P1-T04:** `inventory.StockLocation` (cold room, truck, other; counter sales) and `fleet.Truck`
  (plate, driver, one-to-one location); services with audit; APIs for locations (office only) and
  trucks (a driver sees only their own); "own truck" helpers; the driver's truck in `/me`, shown in the
  driver app. Admin "Stock frigo & camions" screen with location cards and dialogs. Seeds 2 cold rooms
  and 3 trucks, Camion 1 driven by the demo driver (D-033).
- Fixed the P1-T03 browser test: it reused a fixed tax ID and failed on a second local run.
- Local results: 194 backend tests, 43 vitest tests, 21 Playwright tests; ruff, mypy, import
  boundaries, eslint, prettier and the API client check all pass. Screens checked in light, dark and
  phone width.

## Recently done

- 2026-10-10 · P1-T04 locations and trucks
- 2026-10-10 · P1-T03 suppliers
- 2026-10-10 · P1-T02 product catalogue, prices and photos
- 2026-10-10 · P1-T01 units and quantity helpers (merged)

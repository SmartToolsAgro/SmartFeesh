# Project status

_Last updated: 2026-10-10_

## Where we are

- **Phase:** 1 · Catalogue, suppliers & stock. Phase 0 agent work is done; its human items are listed
  under Blockers.
- **Staging is live:** admin http://217.182.205.137:8095, driver http://217.182.205.137:8096
  (`docs/runbook.md`). Demo logins `owner` / `driver`, password in `~/frutti-staging/.env` on the server.
- **Done:** P1-T02 · Product catalogue (branch `p1-t02-products`, pushed, not merged, **not deployed**).
- **Current task:** P1-T03 · Suppliers (`docs/phases/01-stock-core.md`)

## Next step (do this first)

1. Merge `p1-t02-products` into `main` once CI is green.
2. The merge deploys staging by itself (CI job `deploy-staging`, secrets set 2026-10-10): check it ran.
   This first automatic deploy adds the Docker volume `frutti-staging_media` and the 12 demo products.
   Then upload one photo on staging: the volume must be writable by the `app` user.
3. Agent: start **P1-T03** from `main`. Follow the catalogue's patterns: services raise
   `ValidationError` per field (D-030), views subclass a scoped base view, demo data goes in `apps/demo`.

## Blockers / waiting on client

- **P0-T02** (worked example on one real month) is not started. Phase 6 has no target without it, and
  it must settle one rule: a loss larger than a supplier's remaining capital (Q3).
- **P0-T01**: no prototype walk-through or client materials yet. Stand-in data in `docs/spec/sample/`.
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

- **P1-T02:** `Category`, `Product` (with Arabic name and stand-in drawing), append-only `ProductPrice`;
  services with audit; API for list/search/filter, create, update, archive, prices and photo (D-030);
  admin screen "Produits" with prototype-style cards and a form (photo, price history). Demo catalogue
  in `seed_dev`, now in the new `demo` app.
- Local results: 131 backend tests, 43 vitest tests, 13 Playwright tests; ruff, mypy, import
  boundaries, eslint, prettier and the API client check all pass. Screens checked in light, dark and
  phone width.

## Recently done

- 2026-10-10 · P1-T02 product catalogue, prices and photos
- 2026-10-10 · P1-T01 units and quantity helpers (merged)
- 2026-10-10 · Phase 0 branches merged into `main` (fast-forward, CI green)
- 2026-10-10 · P0-T10 cloud hook, P0-T11 staging live

# Project status

_Last updated: 2026-10-10_

## Where we are

- **Phase:** 1 · Catalogue, suppliers & stock. Phase 0 agent work is done; its human items are listed
  under Blockers.
- **Staging is live:** admin http://217.182.205.137:8095, driver http://217.182.205.137:8096
  (`docs/runbook.md`). Demo logins `owner` / `driver`, password in `~/frutti-staging/.env` on the server.
- **Done:** P1-T01 · Units (branch `p1-t01-units`, not merged, not deployed: it has no visible screen).
- **Current task:** P1-T02 · Product catalogue (`docs/phases/01-stock-core.md`)

## Next step (do this first)

1. Merge `p1-t01-units` into `main` once CI is green, then branch P1-T02 from `main`.
2. Agent: start **P1-T02**. Read only its section of the phase file. `Product.base_unit` is a
   `ForeignKey(Unit, on_delete=PROTECT)` defaulting to `catalog.selectors.base_unit()`; read quantities
   with `core.money.checked_quantity` and convert with `catalog.selectors.to_base_quantity` (D-029).
   After adding endpoints run `make gen-api` and commit the result. Deploy with `make deploy-staging`
   once the product screens exist so the client can follow.

## Blockers / waiting on client

- **P0-T02** (worked example on one real month) is not started. Phase 6 has no target without it, and
  it must settle one rule: a loss larger than a supplier's remaining capital (Q3).
- **P0-T01**: no prototype walk-through or client materials yet. Stand-in data in `docs/spec/sample/`.
- **P0-T11 human items:** a domain for HTTPS (staging is plain HTTP, D-027); GitHub secrets
  `STAGING_SSH_KEY` and `STAGING_KNOWN_HOSTS` for automatic deploys, ideally with a restricted deploy user;
  a Sentry project and its DSN.
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

- **P1-T01:** new `catalog` app with a `Unit` table shared by every organization, seeded with `kg` by a
  data migration (D-029); `to_base_quantity` and `checked_quantity` helpers. 84 backend tests,
  ruff, mypy, import boundaries, and migrations forward and back all pass locally. No endpoint, so the
  API client did not change. Frontend checks not run (no frontend change).
- Local tests ran on a throwaway PostgreSQL 18 cluster (`initdb` on port 5433, trust login), because
  the password of the installed service is unknown.

## Recently done

- 2026-10-10 · P1-T01 units and quantity helpers
- 2026-10-10 · Phase 0 branches merged into `main` (fast-forward, CI green)
- 2026-10-10 · P0-T10 cloud hook, P0-T11 staging live
- 2026-10-10 · P0-T09 API contract and generated client

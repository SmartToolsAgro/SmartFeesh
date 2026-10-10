# Project status

_Last updated: 2026-10-10_

## Where we are

- **Phase:** 0 · Discovery & foundations: all agent work done (P0-T03 to P0-T11). Open: P0-T01 and P0-T02
  (human), and three human items of P0-T11 (domain + HTTPS, CI deploy secrets, Sentry project).
- **Staging is live:** admin http://217.182.205.137:8095, driver http://217.182.205.137:8096
  (`docs/runbook.md`). Demo logins `owner` / `driver`, password in `~/frutti-staging/.env` on the server.
- **Current task:** P1-T01 · Units (`docs/phases/01-stock-core.md`)

## Next step (do this first)

1. **Merge the stacked branches into `main`, oldest first** (CI was green on all of them, Mahmoud
   2026-10-10): `p0-t04-quality-ci` → `p0-t05-core-app` → `p0-t06-auth` → `p0-t07-design-system` →
   `p0-t08-i18n` → `p0-t09-api-client` → `p0-t10-t11-staging`.
2. Agent: start **P1-T01**. Read only its section of the phase file. New Django apps follow
   ARCHITECTURE §3; after adding an endpoint run `make gen-api` and commit the result. Deploy with
   `make deploy-staging` after each finished task so the client can follow.

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
  `npx -y pnpm@10.28.0 <command>` works. A PostgreSQL 18 service listens on 5432 but has no `frutti`
  role yet: create it from `.env.example` to run the backend and browser tests.
- Run `make lint` before every commit (or `make hooks` once); CI runs the same checks.
- API: 401 = not logged in, 403 = role not allowed (D-023). Every view sets a permission class, scopes its
  queryset with `.for_organization(org)` (D-022) and names its operation with `operation_id` (D-026).
- UI: no hard-coded text (`packages/i18n/src/fr.ts` + `t()`); `formatMoney` / `formatQuantity` /
  `formatDate`; logical CSS classes (D-025); token colours only (D-024); API calls through `@frutti/api`.
- VAT rate, stamp, prices with or without VAT, withholding rate and the over-credit-limit behaviour are
  organization settings (D-018). Purchase and sale prices change daily (D-020).

## Last session (2026-10-10)

- Q1–Q17 answered; plan updated (D-014 to D-020); stand-in data in `docs/spec/sample/`.
- P0-T04 to P0-T09 built (D-021 to D-026); CI confirmed green by Mahmoud.
- **P0-T10** cloud session hook (D-028). **P0-T11** production images, staging on the shared OVH VPS,
  deploy script, CI deploy job waiting for secrets, runbook (D-027).
- Local results: 63 backend tests, 27 vitest tests, 10 Playwright tests. Staging logins checked from
  the internet in a browser.

## Recently done

- 2026-10-10 · P0-T10 cloud hook, P0-T11 staging live
- 2026-10-10 · P0-T09 API contract and generated client
- 2026-10-10 · P0-T08 internationalisation

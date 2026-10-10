# Project status

_Last updated: 2026-10-10_

## Where we are

- **Phase:** 1 · Catalogue, suppliers & stock. Phase 0 agent work is done; its human items are listed
  under Blockers.
- **Staging is live:** admin http://admin.217-182-205-137.sslip.io:8095, driver
  http://chauffeur.217-182-205-137.sslip.io:8096 (one host name per app, D-036)
  (`docs/runbook.md`). Demo logins `owner` / `driver`, password in `~/frutti-staging/.env` on the server.
- **Merged and deployed:** P1-T02 to P1-T05 are on `main` (PR #3) and on staging since 2026-10-10 21:16
  UTC, with the demo products, suppliers, cold rooms, trucks and batches.
- **Waiting for merge, in this order:** `fix-staging-seed-password`, then `p1-t06-ledger` (P1-T06a,
  stacked on it). Separately: the docs-only `docs-profit-loss-rates` (D-031). `gh` is not installed on
  UTC, with the demo products, suppliers, cold rooms, trucks and batches. Still waiting: the docs-only
  branch `docs-profit-loss-rates` (D-031) and `staging-hostnames-session` (D-036). `gh` is not installed on
  Mahmoud's machine and agents may not merge to `main` without his approval, so he merges.
- **Next task:** P1-T06b · FIFO allocation. P1-T06 is split into T06a (done), T06b and T06c
  (`docs/phases/01-stock-core.md`).
- The client is not available: keep building the plan with the stand-in data of `docs/spec/sample/`
  (Mahmoud, 2026-10-10) and adjust when real requirements arrive.

## Next step (do this first)

1. Merge `fix-staging-seed-password`: without it every automatic deploy fails at the demo-data step
   (staging's demo password has 11 characters, `seed_dev` wanted 12 even for existing accounts).
2. Merge `p1-t06-ledger`. Its deploy migrates the ledger tables and the seed receives the 15 demo batches
   into the cold rooms and loads Camion 1 once (fixed `client_uuid`s: later deploys move nothing).
3. Merge `docs-profit-loss-rates`; it appends D-031 to `docs/DECISIONS.md`: keep every entry, in number
1. Merge `staging-hostnames-session` (D-036). After its deploy, open the apps by their new names and
   check that the owner (admin) and the driver (driver app) stay logged in side by side in one browser.
2. Merge `docs-profit-loss-rates`; it appends D-031 to `docs/DECISIONS.md`: keep every entry, in number
   order. Upload one product photo on staging: the `frutti-staging_media` volume must be writable.
4. Agent: P1-T06b from `p1-t06-ledger` (or `main` once merged): `allocate_fifo(product, location, qty)`
   over `selectors.batches_oldest_first` and the on-hand cache, then a helper posting one movement per
   allocated batch with `services.post_movement` (D-035).

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
- Stock changes only through `inventory.services.post_movement` (D-035); never write `StockOnHand`.

## Last session (2026-10-10)

- **P1-T06a:** split P1-T06 into T06a/b/c. `StockMovement` (append-only, 8 kinds, sides per kind,
  source document, `occurred_at`, `client_uuid`) and the `StockOnHand` cache; `post_movement` locks rows
  in a fixed order and refuses negative stock; selectors `on_hand_of`, `quantity_on_hand`,
  `movements_of`. A location holding stock cannot be archived, and the admin dialogs show why. Demo
  stock: 15 receipts and a morning load of Camion 1 (D-035). No API yet: the stock screens (P1-T11).
- Local results: 240 backend tests (two transfers racing for the same kilos; 8 crossed transfers without
  deadlock), type checks, ruff, mypy, import boundaries, eslint, prettier; 20 Playwright tests, including
  a new one: a cold room with stock cannot be archived.

## Recently done

- 2026-10-10 · P1-T06a stock ledger and on-hand cache
- 2026-10-10 · Staging deployed with P1-T02 to P1-T05 (demo data seeded by hand: short password)
- 2026-10-10 · Staging: one host name per app (shared cookie bug), apps re-read the session on 401/403
- 2026-10-10 · CI deploy green end to end (PR #4, short demo password no longer stops the seed)

- 2026-10-10 · Staging deployed with P1-T02 to P1-T05 (CI host key secret fixed; demo data seeded by hand
  after the seed step stopped on the short password)

- 2026-10-10 · P1-T05 batches
- 2026-10-10 · P1-T04 locations and trucks

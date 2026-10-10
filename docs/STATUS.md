# Project status

_Last updated: 2026-10-10_

## Where we are

- **Phase:** 1 · Catalogue, suppliers & stock. Phase 0 agent work is done; its human items are listed
  under Blockers.
- **Staging is live:** admin http://217.182.205.137:8095, driver http://217.182.205.137:8096
  (`docs/runbook.md`). Demo logins `owner` / `driver`, password in `~/frutti-staging/.env` on the server.
- **Merged and deployed:** P1-T02 to P1-T05 are on `main` (PR #3) and on staging since 2026-10-10 21:16
  UTC, with the demo products, suppliers, cold rooms, trucks and batches. Still waiting: the docs-only
  branch `docs-profit-loss-rates` (D-031) and `fix-staging-seed-password`. `gh` is not installed on
  Mahmoud's machine and agents may not merge to `main` without his approval, so he merges.
- **Next task:** P1-T06 · Stock ledger and on-hand (size L: split it into sub-tasks first).
- The client is not available: keep building the plan with the stand-in data of `docs/spec/sample/`
  (Mahmoud, 2026-10-10) and adjust when real requirements arrive.

## Next step (do this first)

1. Merge `fix-staging-seed-password`: without it every automatic deploy fails at the demo-data step
   (staging's generated demo password has 11 characters, `seed_dev` wanted 12 even for existing
   accounts). Its deploy is the check that the CI deploy now runs to the end.
2. Merge `docs-profit-loss-rates`; it appends D-031 to `docs/DECISIONS.md`: keep every entry, in number
   order. Upload one product photo on staging: the `frutti-staging_media` volume must be writable.
3. Agent: start P1-T06 from `p1-t05-batches` (or `main` once merged). First split it in the phase file
   (ledger + on-hand + `post_movement`; FIFO allocation; rebuild command and nightly check). FIFO walks
   `inventory.selectors.batches_oldest_first` (D-034). Give the 15 demo batches an opening stock in the
   seed. Same patterns: per-field `ValidationError` (D-030), scoped base views, demo data in `apps/demo`.

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
  and its password is unknown; for tests, `initdb -A trust` a cluster in the scratchpad on its own port
  (5433, 5434…: parallel sessions each use their own) and set `DATABASE_URL`.
- Run `make lint` before every commit (or `make hooks` once); CI runs the same checks.
- API: 401 = not logged in, 403 = role not allowed (D-023). Every view sets a permission class, scopes its
  queryset with `.for_organization(org)` (D-022) and names its operation with `operation_id` (D-026).
- UI: no hard-coded text (`packages/i18n/src/fr.ts` + `t()`); `formatMoney` / `formatQuantity` /
  `formatDate`; logical CSS classes (D-025); token colours only (D-024); API calls through `@frutti/api`.
- VAT rate, stamp, prices with or without VAT, withholding rate and the over-credit-limit behaviour are
  organization settings (D-018). Purchase and sale prices change daily (D-020).

## Last session (2026-10-10)

- **P1-T05:** `inventory.Batch` (product, supplier, supplier's receipt reference, receipt date, cost per
  kg, use-by) with numbers `L-0001`… per organization from a locked counter; `services.create_batch`
  (per-field checks, audit); selectors for lists, search and FIFO order; read-only office API
  `listBatches` (first paginated list, `core.api.pagination.PagedList`) and `getBatch`; read-only Django
  admin. `core.money.checked_amount` for typed amounts. Seeds 15 recent batches (D-034). No screen yet:
  batches show in the stock screens (P1-T11).
- Fixed the suppliers API description that cited D-031 instead of D-032.
- Local results: 222 backend tests (one runs four receipts at once), vitest and type checks; ruff, mypy,
  import boundaries, eslint, prettier pass. No Playwright run: no screen changed.

## Recently done

- 2026-10-10 · Staging deployed with P1-T02 to P1-T05 (CI host key secret fixed; demo data seeded by hand
  after the seed step stopped on the short password)

- 2026-10-10 · P1-T05 batches
- 2026-10-10 · P1-T04 locations and trucks
- 2026-10-10 · P1-T03 suppliers
- 2026-10-10 · P1-T02 product catalogue, prices and photos

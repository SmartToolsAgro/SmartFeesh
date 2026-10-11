# Project status

_Last updated: 2026-10-11_

## Where we are

- **Phase:** 1 · Catalogue, suppliers & stock. Phase 0 agent work is done; its human items are listed
  under Blockers.
- **Staging is live** and runs `main` at 06cde30 (P1-T06b): admin
  http://admin.217-182-205-137.sslip.io:8095, driver http://chauffeur.217-182-205-137.sslip.io:8096
  (D-036, `docs/runbook.md`); the old IP addresses redirect there. Demo logins `owner` / `driver`,
  password in `~/frutti-staging/.env` on the server. Seeded stock: Chambre froide 1 271 kg, Chambre
  froide 2 107 kg, Camion 1 40 kg.
- **On `main`:** P1-T02 to P1-T06b and D-031 (PRs #3 to #8). Every merge to `main` deploys staging.
- **Merging (2026-10-11):** Mahmoud lets agents open, merge (green CI only) and verify PRs with `gh`
  (`C:\Program Files\GitHub CLI\gh.exe` on his machine).
- **On `main` too:** P1-T06c (PR #9, nightly stock check on staging).
- **This branch:** `p1-t07-receipts` (P1-T07, goods receipts), PR to `main`.
- **Next task:** P1-T08 · Supplier invoices and payments (D-040+).
- The client is not available: keep building the plan with the stand-in data of `docs/spec/sample/`
  (Mahmoud, 2026-10-10) and adjust when real requirements arrive.

## Next step (do this first)

1. After P1-T06c is deployed: `sudo docker ps` shows `frutti-staging-nightly-1` running; the first
   check runs just after 03:00 UTC (`sudo docker logs frutti-staging-nightly-1`).
2. After P1-T07 is deployed: on staging, "Achats" shows `BR-0001` (Mareyeur Port de Sfax, dorade 60 kg
   accepted for 62 invoiced) and a new receipt can be recorded.
3. Agent: P1-T08 supplier invoices and payments: `SupplierInvoice` linked to receipts (invoiced kg ×
   cost is the line's `invoiced_amount`, D-039), due date, status; `SupplierPayment` with allocation;
   supplier balance. Nothing touches capital or profit shares (separate balances).
4. Mahmoud: check the two apps side by side in one browser on the new host names; upload one product
   photo on staging.

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
- Mahmoud's Windows machine: `gh` is installed (`C:\Program Files\GitHub CLI\gh.exe`, logged in as
  `mahmoudnjeh95`; open a new shell to have it on the PATH). No `make`, `pnpm`, `docker`, `psql` or
  gettext on the PATH;
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

## Last session (2026-10-11)

- **P1-T07:** new `purchasing` app: `GoodsReceipt` + lines (ordered, invoiced, accepted net kg, cost);
  saving creates the batches and receipt movements in one transaction; per-line errors on
  `lines.<i>.<field>`; differences report; last cost per product and supplier. Admin "Achats": list,
  receipt page with the weight-difference notice, "Nouvelle réception" form with the last cost filled
  in and the change in percent. Demo receipt `BR-0001` (D-039).
- Local results: 272 backend tests; vitest (now also in the admin app); 23 Playwright tests including 3
  new ones for receipts; ruff, mypy, import boundaries, eslint, prettier, API client. Screens checked
  at desktop (light) and phone width (dark).

## Recently done

- 2026-10-11 · P1-T07 goods receipts
- 2026-10-11 · P1-T06c rebuild and nightly check
- 2026-10-10 · P1-T06b FIFO allocation
- 2026-10-10 · P1-T06a stock ledger and on-hand cache

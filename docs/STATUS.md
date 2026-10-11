# Project status

_Last updated: 2026-10-11_

## Where we are

- **Phase:** 1 is done. Phase 2 (sales) is half done, Phase 5 (costs) is mostly done, Phase 6 (lot
  profit and partner share) is next. Phase 0 agent work is done; its human items are under Blockers.
- **On `main`:** P1-T02 to P1-T12; P2-T01 to P2-T04 (customers, prices, quotes, sales and counter sale);
  P5-T01, P5-T03, P5-T04 (expenses, day-labour calendar, employees and salaries); PRs #3 to #25.
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

1. Agents (parallel): **P2-T05** invoices (finance settings, VAT, stamp, withholding, gap-free numbers);
   **P5-T02 + P5-T05** cold-room cost per day and rent/accountant "like a salary" on lots;
   **P6-T01..T03** partnership lots and the lot result engine (reads sales per lot `batch_sales_totals`,
   `expenses.lot_cost_lines`, hr `LotWorkDay`; cold-room and general cost lines plug in when they land).
2. Then P2-T06 customer payments and credit limit (hooks `check_credit` / `record_receivable` in
   `sales.services`), P2-T07 returns, P2-T08 PDFs, Phase 3 driver app, P6-T04..T07 statements/closing.
3. Phase 3 leftovers: narrow customer endpoint for drivers (D-047), driver truck-of-day screen (D-046),
   driver confirmation of loads (D-044), a truck sale should use the load's price (D-051).
4. Mahmoud: check the apps on staging; get the real lot for P0-T02.

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

Second and third parallel waves (Opus for the money-critical tasks, Sonnet for the rest):
- **P1-T11** stock screens + average purchase price (D-048); **P2-T02** "Prix du jour", price lists,
  `price_in_force` (D-049); **P2-T03** quotes, new `sales` app (D-050).
- **P2-T04** sales (D-051, D-052): FIFO lot rows with cost snapshots, cancel by reversal, quote
  conversion, quick counter sale, `batch_sales_totals` per lot.
- **P5-T01/T03** expenses with lot/truck-day costs, day-labour calendar (D-053, D-054); **P5-T04** `hr`
  employees, salaries, days on a lot (D-055).
- Two Opus agents were cut off by the API rate limit; resumed or finished by hand. A time-of-day
  dependent inventory test was fixed (it failed CI after 11:00 UTC).

## Recently done

- 2026-10-11 · P1-T11, P2-T02, P2-T03, P2-T04, P5-T01, P5-T03, P5-T04
- 2026-10-11 · P1-T08, P1-T09, P1-T10, P1-T12, P2-T01 (first parallel wave)
- 2026-10-11 · Plan updated after the client meeting (per-lot profit)
- 2026-10-11 · P1-T07 goods receipts
- 2026-10-11 · P1-T06c rebuild and nightly check

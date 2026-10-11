# Decisions log

One entry per decision. Newest at the bottom. Status: **accepted**, **provisional** (waiting on a client
answer), or **superseded by D-xxx**. Change a decision by adding a new entry, never by rewriting an old one.

---

**D-001 · Modular monolith: Django + DRF + PostgreSQL** · accepted · 2026-10-09
Sales, stock, payments and profit sharing must stay consistent in one transaction. A single database and
one deployable make that simple. Domain apps with enforced boundaries keep the option to split later.

**D-002 · React + Vite single-page apps, not Next.js** · accepted · 2026-10-09
The general ERP frontend guidance recommends Next.js. We use Vite instead because the backend is Django,
every screen is behind a login (no SEO or server-rendering need), and the driver app needs a service worker
for offline use, which is simpler with Vite + vite-plugin-pwa. The rest of that guidance is kept: TypeScript,
TanStack Query, Zustand, Zod, React Hook Form, Tailwind + shadcn/ui, TanStack Table, monorepo.

**D-003 · Two front ends (admin, truck) in one pnpm + Turborepo monorepo** · accepted · 2026-10-09
The driver app stays small and fast on a phone and can later be wrapped as a native app; the admin app can
grow without affecting it. Both share `packages/ui` and the generated `packages/api`. No micro-frontends.

**D-004 · `organization` foreign key on every business table** · accepted · 2026-10-09
Costs almost nothing now and avoids a painful migration if the product is later sold to other distributors.

**D-005 · Money and weights as Decimal with 3 places** · accepted · 2026-10-09
The Tunisian dinar has 1,000 millimes. Floats cause rounding errors in invoices and profit shares.
Amounts are sent as strings in JSON.

**D-006 · Stock = append-only movement ledger + on-hand cache** · accepted · 2026-10-09
Every kilogram must be traceable from receipt to sale or loss. The cache is updated in the same transaction
and can always be rebuilt from the ledger.

**D-007 · All writes go through a services layer** · accepted · 2026-10-09
The same business operation is triggered from the admin app, the driver app, offline sync, imports and
background jobs. Keeping it in one function per operation avoids duplicated rules.

**D-008 · Session cookie authentication + CSRF, same domain** · accepted · 2026-10-09
Simpler and safer than storing tokens in the browser. Works for the PWA because it is served from the
same domain. Revisit if a native app or third-party API clients appear.

**D-009 · Batch-level costing with automatic oldest-first (FIFO) batch allocation** · provisional · 2026-10-09
Supplier profit attribution needs to know which supplier's batch each sale came from. Drivers will not
pick batches by hand, so the system allocates the oldest batch first. Waiting on Q4 and Q7.

**D-010 · Agent workflow: STATUS.md pointer, one task per session** · accepted · 2026-10-09
Each session reads `docs/STATUS.md` and only the current phase file instead of the whole repo, and updates
STATUS before ending. Tasks have IDs (`P1-T06`) so the pointer is exact.

**D-011 · Third-party agent skill `find-skills` vendored in `.claude/skills/`** · accepted · 2026-10-09
Installed at the user's request from vercel-labs/skills (commit 13e4063). It is committed to the repo
(not installed user-level) because cloud sessions start from a fresh clone. Review any skill before adding it.

**D-012 · Exact, two-week-old dependency versions; TypeScript 6.0 for now** · accepted · 2026-10-09
JS packages are pinned to exact versions released at least two weeks earlier, which lowers the risk of
a compromised fresh release. TypeScript stays on 6.0 because typescript-eslint supports `<6.1`; move to
7.x when it is supported. Python dependencies are locked with uv (`backend/uv.lock`).

**D-013 · uv for Python, pnpm for JavaScript** · accepted · 2026-10-09
Both are fast, produce lockfiles, and are already used in CI images. Dev Docker images run the same
tools (`ghcr.io/astral-sh/uv`, `node:22` + corepack).

**D-014 · Batch-level FIFO costing confirmed** · accepted · 2026-10-10
Confirms D-009, which is no longer provisional. Q4: the same product can come from several suppliers in
one month and their batches are tracked separately. Q7: a sold kilo is valued at its own batch cost,
oldest batch first.

**D-015 · Plan changed after the client answers** · accepted · 2026-10-10
TTN / El Fatoora e-invoicing moves from the Phase 8 backlog to P2-T10 (Q5: required now). Arabic for the
driver app moves to P3-T09 (Q14) and Bluetooth receipt printing to P3-T10 (Q13). Printing on iPhone may
force a native wrapper, so the PWA choice in D-002 and D-003 is re-examined by the P3-T10 spike. An
`accountant` role is added in P0-T05 (Q9). Tax rate and fiscal stamp are organization settings, not
constants, because selling to other distributors is a confirmed goal (Q17).

**D-016 · TTN / El Fatoora e-invoicing on hold** · accepted · 2026-10-10
Changes D-015: P2-T10 is removed and its task list is kept in the Phase 8 backlog. Q5 says e-invoicing is
required now, but Mahmoud decided not to implement it for now. P2-T05 keeps a hook; the app issues PDF
invoices only until this is picked up again.

**D-017 · Staging and production on a VPS** · accepted · 2026-10-10
One rented server running the Docker stack: cheapest and fully under our control. We maintain the
server and the backups ourselves (P4-T03). Provider and size are still to choose.

**D-018 · Rules that may vary are organization finance settings** · accepted · 2026-10-10
VAT rate, fiscal stamp, whether sale prices include VAT, the withholding rate (hidden on invoices when
0 %) and the behaviour above a customer's credit limit (block, approval, warn) are settings per
organization with a valid-from date, editable by the owner. Other distributors will need other values
(Q17), and several of these were not fixed by the client.

**D-019 · OVH as VPS provider; stand-in data until the client's materials arrive** · accepted · 2026-10-10
Completes D-017: staging and production run on OVH. Separately, `docs/spec/sample/` holds example
products, suppliers, customers, locations, employees, an invoice and a partner agreement, built from
public Tunisian sources with invented companies and people. It feeds seeds, tests and demos only; real
client data replaces it at go-live. It does not replace P0-T02, which needs one real month.

**D-020 · Prices are dated, never fixed** · accepted · 2026-10-10
Purchase and sale prices both change from one day to the next. Purchase cost belongs to the batch
created by each receipt, with no supplier price list. Sale price is a `ProductPrice` with a valid-from
date and time, because it can change several times in one day; it is set from a "Prix du jour" screen. Sale lines snapshot the price charged and the batch cost, so past sales and
closed months never move when a price changes.

**D-021 · Quality tooling choices (P0-T04)** · accepted · 2026-10-10
- Line length 120 for Python (ruff) and TypeScript (prettier): the scaffold already used long lines.
- ESLint runs the type-aware rules, so an un-awaited promise is an error.
- The app boundary rule is a custom import-linter contract (`backend/tooling/import_contracts.py`), so
  new apps are covered without editing the config. Interpretation of ARCHITECTURE §3: `core` is the
  shared kernel and may be imported whole by every app; other apps expose only `services` and
  `selectors`; tests and `TYPE_CHECKING` imports are exempt.
- Python is pinned to 3.13 (`backend/.python-version`), the version of the Docker image.
- GitHub Actions are pinned to the commit of a release at least two weeks old, like JS packages (D-012).
- `.gitattributes` forces LF line endings so formatters give the same result on Windows.
- Known gap: D-012 covers direct JS dependencies only. pnpm's `minimumReleaseAge` would also cover
  transitive ones, but it rejects the current lockfile (rolldown 1.2.13, two days old on 2026-10-10).
  Turn it on the next time the lockfile is refreshed.

**D-022 · Core app choices (P0-T05)** · accepted · 2026-10-10
- Users log in with a username, not an email: drivers may have no email address.
- A user gets a role through a `Membership` (user, organization, role), so the same model serves
  several companies later (Q17).
- Tenancy is explicit: business code reads with `Model.objects.for_organization(org)`. No hidden
  thread-local filter, so background jobs, the shell and tests behave like requests. The API layer
  (P0-T06) must scope every queryset this way.
- `AuditLog` is append-only in code: saving an existing entry, deleting one, and bulk update or delete
  all raise. Decimals inside `before` / `after` are stored as strings.
- Money and quantity are plain `Decimal` values rounded by `money()` / `quantity()` and stored in
  `MoneyField` / `QuantityField`, not a wrapper class: Django, DRF and JSON handle Decimal natively.
  The helpers refuse floats with a `TypeError`.
- `django-stubs-ext` is a runtime dependency: it lets typed code subscript Django classes.

**D-023 · Authentication and permission choices (P0-T06)** · accepted · 2026-10-10
- The API answers 401 when nobody is logged in and 403 when the role is not allowed. The apps rely on
  it: 401 shows the login screen. DRF's stock session authentication answers 403 for both.
- Login is protected against CSRF explicitly and limited to 8 attempts per minute per account and 30
  per address. The counters live in Django's default in-process cache, so with several server
  processes each one counts separately: move them to Redis when Redis arrives (P2-T08), and set DRF's
  `NUM_PROXIES` in production so the address is the client's, not the proxy's.
- A wrong password, an unknown user and a disabled account get the same answer.
- Roles are checked by DRF permission classes built on `HasRole`; the front-end guard only improves the
  experience. The admin app accepts owner, manager and accountant; the driver app accepts driver.
- React Router for routing and TanStack Query for the session, in a shared `@frutti/auth` package
  (API helper with CSRF, session hooks, login page, route guard). It is hand-written until the
  generated client exists (P0-T09).
- Playwright tests live in `frontend/e2e` and start the backend and both apps themselves.

**D-024 · Design system choices (P0-T07)** · accepted · 2026-10-10
- Tailwind CSS 4 is configured in CSS, so the "preset" is one stylesheet, `packages/ui/src/styles.css`,
  imported by each app. The prototype's tokens stay CSS variables and are exposed as utilities
  (`bg-surface`, `text-ink-2`, `rounded-card`...).
- Light and dark switch by changing the variables (device preference, or `data-theme` on `<html>` set by
  the theme switch and kept in localStorage). Components never use Tailwind's `dark:` variant.
- Fonts are self-hosted with fontsource packages instead of Google Fonts: the driver app must work
  offline. They have no Arabic glyphs: choose an Arabic font in P3-T09.
- Icons and illustrations are the prototype's own drawings, kept as one SVG sprite (`sprite.svg`) with
  typed `Icon` and `Illustration` components. No icon library.
- Components follow the shadcn/ui approach (source in the repo, Radix for Select and Dialog, sonner for
  toasts) but are written by hand against our tokens, not generated by the shadcn CLI.
- Coral is reserved for the main action of a screen; status colours carry meaning, never decoration.

**D-025 · Internationalisation choices (P0-T08)** · accepted · 2026-10-10
- Texts live in one typed file per language in `packages/i18n` (`fr.ts` is the reference, `ar.ts` may be
  incomplete and falls back to French). Keys are checked by the compiler. Texts are bundled, not
  loaded over the network, so the driver app can show them offline.
- The language is a property of the user account, applied by the route guard after login (texts,
  `lang` and `dir` on `<html>`). The server answers a logged-in user in that language too.
- Amounts, weights and dates are formatted from the strings the API sends, with `Intl` and the locales
  `fr-TN` and `ar-TN` (Western digits in both). No JavaScript number is created for an amount.
- Layout uses logical CSS (`ms-`, `me-`, `border-e`, `text-start`) so it mirrors in Arabic.
- Server messages are written in French in the code; translations go in `backend/locale/`.

**D-026 · API contract choices (P0-T09)** · accepted · 2026-10-10
- The OpenAPI schema is committed (`frontend/packages/api/openapi.yaml`) next to the client generated
  from it, so a pull request shows every change of the contract. CI regenerates both and fails on a
  difference.
- orval generates plain functions, TanStack Query hooks, types and Zod schemas. All of them go through
  one hand-written transport, `packages/api/src/http.ts` (session cookie, CSRF token, `ApiError`).
- Every endpoint gets an explicit `operation_id` (`login`, `getSession`, `listMembers`...): it becomes
  the function name in the client.
- A backend test fails on any schema warning, because a warning means a wrong type in the client.

**D-027 · Staging on the shared OVH VPS, plain HTTP for now** · accepted · 2026-10-10
- The VPS also hosts other clients' production sites. Frutti gets its own Docker project, folder and one
  nginx site; nothing else on the server is changed. Its containers listen on 127.0.0.1 only.
- No domain yet (Mahmoud's choice), so staging is served on http://217.182.205.137, ports 8095 (admin)
  and 8096 (driver), with secure cookies, HSTS and the HTTPS redirect switched off by environment
  variables. Production keeps them on by default. Consequences until a domain exists: logins travel
  unencrypted, and the driver app cannot be installed as a PWA (service workers need HTTPS).
- Images are built on the server from a `git archive` of the committed code, so the server needs no
  access to the private repository. Secrets live in `~/frutti-staging/.env` on the server only.
- Staging demo accounts get a random password (`seed_dev --password`), never the development one.

**D-028 · Cloud session hook written by hand** · accepted · 2026-10-10
The `session-start-hook` skill named in P0-T10 does not exist from a trusted source (only small
third-party skills, 34 to 151 installs). The hook is a plain Claude Code `SessionStart` setting, so it
was written directly. It runs only when `CLAUDE_CODE_REMOTE=true`: installs backend and frontend
dependencies and starts PostgreSQL with the `frutti` role.

**D-029 · Units are shared reference data; typed weights are checked, not rounded (P1-T01)** · accepted · 2026-10-10
- `catalog.Unit` has **no** `organization` key: a kilogram means the same for every company, like a
  currency code. This is the one exception to "every business table has an organization". Anything a
  company decides about a unit (a box weight for one product) will live on its own organization-scoped
  rows, not on `Unit`.
- A data migration seeds `kg` only (Q10). Units are never deleted from the admin.
- Every quantity entering the system goes through `catalog.selectors.to_base_quantity(value, unit)`. It
  refuses any unit but kg today, so box or piece units later change one function.
- `core.money.checked_quantity` checks a weight a person typed or a scale gave and **refuses** more than
  3 decimals, negatives (the movement type carries the direction), zero (unless allowed, for counts)
  and values too large for a `QuantityField`. Rounding silently would change stock without anyone noticing.

**D-030 · Product catalogue choices (P1-T02)** · accepted · 2026-10-10
- `Product` has no price column: the sale price is the latest `ProductPrice` at or before a moment
  (D-020). A new product gets its first price from now; later prices go through `setProductPrice`, may be
  planned for later, and are refused in the past. Prices are append-only, like the audit log.
- Extra fields not in the brief: an optional **Arabic name** (drivers can work in Arabic, Q14, and the
  sample list has one) and a **drawing** from the prototype shown until a product has a real photo.
- Storage temperature is a min/max pair in °C with one decimal; either end may be empty ("≤ -18 °C").
- Product lists are **not paginated**: a catalogue holds tens of products. Revisit if one exceeds ~500.
- Every member reads the catalogue (drivers will sell from it); owners and managers change it
  (`ReadMemberWriteOwnerOrManager`). The Django admin shows catalogue rows read-only, so every change
  goes through the services and the audit log.
- Services raise Django's `ValidationError` with a message per field; one API exception handler turns it
  into a 400 shaped like serializer errors. Every app uses this from now on.
- **Photos** are re-encoded on upload (upright, at most 1200 px, WebP, no metadata: no GPS position),
  get a new random file name each time, and are served by the API to members of the same organization
  only (`/products/{id}/photo?v=…`, cached for good because the address changes with the photo). Loss
  photos and receipts will follow the same pattern. Staging keeps them in the `media` Docker volume.
- `seed_dev` moved from `core` to a new `demo` app, which may call every app, and now also creates the
  12 stand-in products of `docs/spec/sample/products.csv`.

**D-031 · Two share rates per partner; uncovered loss carried forward (Q3)** · provisional · 2026-10-10
- Mahmoud, 2026-10-10: a partner agreement has a **profit %**, used when the month's net result on the
  partner's products is a profit, and a **loss %**, used when it is a loss. The two may differ. A month
  with a zero result gives a zero share.
- Provisional, until the client confirms: when the loss share is larger than the remaining capital (or
  the partner has no capital), the capital goes down to zero and the rest becomes an amount the partner
  owes, kept in the profit-share balance and recovered from their next profit shares. Capital is never
  negative. The three balances (trade payable, capital, profit share) stay separate.
- Stand-in data: Pêcherie Kerkennah 40 % / 25 %, Surgelés du Sahel 30 % / 20 % (`docs/spec/sample/`).

**D-032 · Suppliers (P1-T03)** · accepted · 2026-10-10
- New `partners` app (ARCHITECTURE §3), which will also hold customers in Phase 2.
- `Supplier` adds three fields to the brief's list: a **reference** (`F-001`, as in the sample list; left
  empty, the server gives the next `F-NNN`), an **e-mail** and a **city**. Contacts are `SupplierContact`
  rows (name, role, phone, e-mail); a change that sends `contacts` replaces the whole list, and the audit
  log keeps the before/after list.
- The **tax ID** (matricule fiscal) is optional, unique per organization when given, and stored as
  `1234567A/A/M/000` (or `1234567A` alone); spaces, dots, dashes and missing slashes are accepted when
  typed, and a 6-digit number gets its leading zero. Other shapes are refused. Provisional: loosen it if
  the client's real list has suppliers with another identifier (CIN of a lone fisherman).
- Suppliers are **office data**: owner, manager and accountant read them, owner and manager change them,
  drivers get 403 (`ReadOfficeWriteOwnerOrManager`, new in `core.permissions`). Purchases will use it too.
- No delete: archive / restore, like products. Lists are not paginated (a handful of suppliers).
- Agreement type, balances and purchase history are **not** on `Supplier`: they come from purchases,
  payments and Phase 6 agreements. The detail screen shows a placeholder card for them.
- E2E tests log the owner in once (`owner.setup.ts`, saved session in `frontend/e2e/.auth/`): logging in
  in every test hit the limit of 8 logins a minute per account.

**D-033 · Locations and trucks (P1-T04)** · accepted · 2026-10-10
- `StockLocation` lives in a new `inventory` app (stock movements will join it in P1-T06); `Truck` in a new
  `fleet` app (driver days join it in Phase 3). `Truck.location` is a one-to-one key written by name
  (`"inventory.StockLocation"`), so `fleet` imports only `inventory.services` / `selectors`.
- A truck's **name is its location's name**, so stock screens and truck screens never disagree. A truck
  is created, renamed and archived through `fleet`; the location API refuses to create or change a truck
  location. Location names are unique per organization; plates too, stored in capitals with single spaces.
- `counter_sales` marks a cold room (or other location) where customers buy at the counter (Q8);
  `sells` is true for trucks and for those. Seeded cold rooms both sell at the counter (provisional).
- One active truck per driver at most (database constraint). Only an active member with the `driver`
  role of the same company can be assigned. Archiving a truck archives its location and takes it back
  from its driver. From P1-T06, a location still holding stock must not be archived.
- **Own truck:** `fleet.selectors.may_use_location(membership, location_id)` and `may_use_truck`. The
  office (owner, manager, accountant) may use every location; a driver only their active truck's. The
  truck API applies it (a driver lists and reads only their own truck, changes nothing); locations are
  office-only (drivers get 403 and learn their truck from `/me`).
- **`/me` truck:** `core` may not import `fleet`, so `core.session` holds a lookup that `fleet` registers in
  `FleetConfig.ready()`. `/me` returns `truck: {id, name, plate, location_id}` or null.
- The admin "Stock frigo & camions" screen manages locations for now (cards like the prototype); P1-T11
  adds the stock figures to the same screen.

**D-034 · Batches, their numbers, and the first paginated list (P1-T05)** · accepted · 2026-10-10
- `Batch` lives in `inventory`, next to the stock it will carry. It points to `catalog.Product` and
  `partners.Supplier` by name, like `Truck` does to its location. Unit cost is DT per kg without VAT, on
  the batch only (D-020); zero is allowed (free goods), negative and sub-millime costs are refused
  (`core.money.checked_amount`, the amount twin of `checked_quantity`). A receipt date in the future and
  a use-by date before receipt are refused. A batch is never edited: corrections come as new documents.
- **Numbers:** `L-` and at least 4 digits, per organization, from a `BatchCounter` row locked with
  `select_for_update` (a test runs four receipts at once). A refused batch uses no number. Gaps are
  possible only if a later step of the same transaction fails, and nothing requires batch numbers to be
  gap-free (unlike invoices).
- **FIFO order** is receipt date, then id (`inventory.models.FIFO_ORDER`, `selectors.batches_oldest_first`);
  P1-T06 allocates over it. Lists show newest first.
- **No `agreement` column yet:** the agreement table comes with P6-T01, which adds the nullable key and
  fills it from the agreement in force at each receipt date. A placeholder integer now would only have to
  be converted later.
- **Batches are created only by services** (goods receipts from P1-T07; the demo seed now). The API is
  read-only and office-only, like suppliers.
- **Pagination:** lists that keep growing (batches, later movements, invoices) use `core.api.pagination.PagedList`
  (`limit` / `offset`, 50 by default, 200 at most, answer `{count, next, previous, results}`). Short lists
  (products, suppliers, locations) stay unpaginated.
- Demo batches have no stock yet: the ledger (P1-T06) or the receipts (P1-T07) should give them an
  opening stock in the seed.

**D-035 · Stock ledger and on-hand cache (P1-T06a)** · accepted · 2026-10-10
- `StockMovement` and `StockOnHand` live in `inventory`. A movement has a kind, one batch (its product is
  copied for fast totals), a `from` and/or `to` location, a positive quantity (the locations give the
  direction), the batch's cost per kg at posting, an optional source document (generic key), the user,
  `occurred_at` (when it happened; a driver offline may sync later) and `created_at` (when posted), a
  reason and an optional `client_uuid`.
- **Sides per kind:** receipt and customer return only come in; sale, supplier return and loss only go
  out; a transfer goes between two different locations; an adjustment or a count correction names one
  location, the side giving the direction. Losses and adjustments need a reason. Locations must be
  active and of the same company.
- **Append-only** like the audit log: saving an existing movement, `update()` and `delete()` raise.
  Movements write **no** `AuditLog` entry: the ledger already records who, what and when, and an audit row
  per kilo moved would double the largest table.
- **Locking:** `post_movement` locks the on-hand rows it touches with `select_for_update`, always in
  location-id order, so crossed transfers cannot deadlock (tested with 8 at once); a missing row is created
  at zero first (`bulk_create(ignore_conflicts=True)`). Stock never goes below zero (a check constraint
  backs the service). A `client_uuid` already posted returns the existing movement.
- A location holding stock cannot be archived (also blocks archiving a loaded truck); the admin dialogs
  now show the server's reason.
- **Demo stock:** the 15 demo batches are received into the cold rooms (frozen products into "Chambre
  froide 2") and Camion 1 is loaded once. Each seeded movement has a fixed `client_uuid` (uuid5), so the
  staging deploy can run the seed every time without moving stock again.
- Tests using several database connections (`transaction=True`) also set `serialized_rollback=True`:
  otherwise the flush between tests deletes the `kg` unit made by a data migration.

**D-036 · One host name per app on staging; the apps re-read the session when refused** · accepted · 2026-10-10
- Browsers keep cookies per host name, not per port. With both staging apps on 217.182.205.137, logging
  in as `driver` on the driver app replaced the owner's session in the admin app, whose requests then
  got 403. Staging now serves each app on its own name from sslip.io (a public DNS that answers the
  address written in the name): `admin.217-182-205-137.sslip.io:8095` and
  `chauffeur.217-182-205-137.sslip.io:8096`. The bare address redirects to the name. Production gets
  one name per app on the real domain for the same reason.
- `remote-deploy.sh` writes `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` on every deploy
  (they are not secrets), so servers set up earlier follow. sslip.io is an outside service: if it is
  down, staging is unreachable by name until the domain exists.
- Both apps build their query client with `@frutti/auth`'s `createQueryClient()`: any 401 or 403 makes
  them read `/me` again, so an ended session shows the login screen and a session replaced by another
  account shows the wrong-app notice, instead of a screen whose saves fail with a generic error.
- gunicorn runs with `--no-control-socket`: its control socket wanted to write in the `app` user's home
  folder, which does not exist in the image, and logged an error at every start. Nothing used it.

**D-037 · FIFO allocation and multi-batch movements (P1-T06b)** · accepted · 2026-10-10
- `inventory.selectors.allocate_fifo(organization, product_id=, location=, quantity=)` previews which
  batches a quantity would come from: the location's on-hand rows of that product, oldest receipt first
  (`FIFO_ORDER`), each batch emptied before the next. More than the location holds is refused on
  `quantity`, with the kg available. Nothing is locked or posted.
- `inventory.services.post_fifo_movements(...)` does it for real: it locks every on-hand row of the
  product at both locations in (location, batch) order, the same order `post_movement` uses, splits the
  quantity oldest first and posts one movement per batch, all in one transaction (refused as a whole).
  Kinds that take nothing (receipt, customer return) are refused. Used by transfers (P1-T09), sales
  (Phase 2) and losses (P1-T10).
- **Idempotency** for a request split over several batches: the n-th movement gets
  `uuid5(client_uuid, n)`; a retry finds part 0 and returns all the parts already posted.
- A destination row that does not exist yet is created during posting; in the rare case that two
  requests create it while crossing, PostgreSQL aborts one with a deadlock error (no hang) and the client
  retries. The test with 8 crossed loads and returns at once passes.

**D-038 · Stock on hand checked against the ledger, nightly and on demand (P1-T06c)** · accepted · 2026-10-11
- `inventory.selectors.on_hand_differences(organization)` sums the movements per (location, batch) and
  compares them with `StockOnHand` in **one SQL statement**, so both are read from the same snapshot
  and a movement posted meanwhile never shows as a false difference. Missing rows and rows with no
  movement are covered (full outer join).
- `inventory.services.rebuild_on_hand(organization, actor)` sets the cache back to the ledger and writes
  one `stock.on_hand_rebuilt` audit entry with the rows before and after. It first takes
  `LOCK TABLE … IN EXCLUSIVE MODE` on the cache: writes wait a few milliseconds, reads do not, and
  since `post_movement` touches the cache before writing its movement, no movement is caught halfway.
  A ledger that would give negative stock (only possible by editing the database) is refused, not
  "repaired".
- `manage.py rebuild_on_hand` repairs every organization; `--check` only reports and fails (exit 1) on a
  difference, logging each one as an error (Sentry once its DSN is set). Repairing stays a human
  decision: a difference means a bug or a hand edit, to be understood first.
- **Nightly, without Celery or the shared server's crontab:** a `nightly` service in
  `compose.staging.yml` runs the backend image and sleeps until just after 03:00 UTC (04:00 in Tunisia),
  then runs the check. It moves to Celery beat when Celery arrives (ARCHITECTURE: Phase 2).

**D-039 · Goods receipts (P1-T07)** · accepted · 2026-10-11
- New `purchasing` app (ARCHITECTURE §3): `GoodsReceipt` (number `BR-0001`… per organization from a locked
  counter, supplier, receiving location, date, supplier's delivery note or invoice number, notes, who
  typed it) and `GoodsReceiptLine` (product, its batch one-to-one, ordered kg or empty, invoiced kg,
  accepted kg, cost per kg). Weights are net (Q12).
- **Saved = posted.** `services.create_receipt` checks everything first, then in one transaction makes one
  batch per line (`inventory.services.create_batch`, cost on the batch, D-020), posts a `receipt`
  movement of the **accepted** weight with the line as source document, and audits. There is no draft
  and no edit: a mistake is corrected by a supplier return or an adjustment, like every posted record.
  A receipt typed later for an earlier day posts its movement at noon of that day.
- **No `PurchaseOrder` yet:** the client works from notebooks and phone calls; the optional ordered
  weight on the line gives the "ordered vs received" difference. A purchase order document can be
  added later without changing receipts.
- **Errors per line** come back on flat keys `lines.<index>.<field>` (and the header's on their own
  field), all at once. Weights and costs travel as strings and are checked by the service
  (`checked_quantity`, `checked_amount`), so a typed "20,5" is refused there, not rounded.
- **Amounts:** invoiced amount = invoiced kg × cost (what the supplier will charge, P1-T08); accepted
  amount = accepted kg × cost (value entering stock). Each line is rounded, then added. A line differs
  when accepted ≠ invoiced, or ≠ ordered when there was an order; `listReceiptDifferences` is the report.
- **Last cost:** `inventory.selectors.last_batches_from(supplier)` (latest batch per product). The form
  fills the cost with it until the person types one, and shows the change in percent.
- **Admin screens:** "Achats" lists receipts (paginated, search, "with differences" filter), a receipt
  page shows lines, batches and the weight-difference notice of the prototype, and "Nouvelle
  réception" records one. Browser-side previews of amounts use exact `bigint` thousandths
  (`apps/admin/src/lib/decimal.ts`, unit-tested: the admin app now runs vitest); the server stays the
  reference. `formatPercent` joins the i18n formatters.
- Demo: receipt `BR-0001` from Mareyeur Port de Sfax today, dorade 62 kg ordered and invoiced, 60 kg
  accepted (the prototype's difference and the start of the Phase 1 acceptance test).

**D-040 · Profit is computed and shared per lot, not per month (client meeting)** · accepted · 2026-10-11
Source: `docs/spec/client-meeting-2026-10-11.md`. Partly supersedes the month-end parts of Q2, Q3 and Q9
and the Phase 6 plan written from them.
- The unit of profit is the **lot** (`Batch`). A lot collects its sales (FIFO already links each sale
  line to its batches), its purchase cost, and its own costs: typed costs (fuel, transport, misc.), day
  labour, monthly employees at days × salary / 26, cold-room days, and a share of rent and accountant.
- A lot is **closed** when it is fully sold (or written off) and settled; its result is then frozen
  (immutable, corrections are new records on a later settlement). Spoilage is a cost of its own lot.
- **Partnership lot:** the owner and a partner supplier each put an amount into the lot. On closing,
  the partner gets their % of the net profit, or carries their % of the loss, deducted from the capital
  they put in (Q3). Confirmed: one partner per lot, two rates (D-031), settlement = capital put in ±
  their share; a supplier can be a partner in several lots at once. Capital, trade payable and profit
  share stay three balances.
- A partnership lot never mixes with other lots: it is its own `Batch`, and FIFO already keeps batches
  apart from the cold room to the truck to the sale.
- The **average purchase price** per product (weighted by kg on hand) is shown for pricing only; it never
  values a sale (Q7 stays FIFO per batch).
- The month-end closing stays for the accountant's monthly result (P6), but no longer decides partner
  shares.

**D-041 · Lot cost rules: cold room, salaries, truck, general costs** · accepted · 2026-10-11
- **Cold room:** monthly electricity bill → split over cold rooms by a weight per room (default equal,
  set by the owner) → per day → per lot by kg held that day (from the ledger, as Q2 said). Until the
  bill is typed, the previous month's daily rate is used; when it arrives, the difference on lots
  already closed is booked on the next settlement, never by reopening them. Confirmed.
- **Monthly employees:** days worked on the lot × monthly salary / 26 (client, 2026-10-11).
- **Truck costs of the day** (transport, labour, misc. tagged to a truck and a date): split over the
  lots on that truck's load that day, **by kg loaded** (provisional: the client said "split over the
  lots", not how).
- **Rent, accountant and other general costs:** "like a salary" (client): monthly amount / 26 per day;
  each day's amount split over the lots in stock that day by kg held (provisional: our reading).
- **Day labour:** one record (date, worker, amount paid, optional lot). Typed from the lot or from the
  calendar, it is the same record; without a lot it is a general cost.

**D-042 · A driver's truck is chosen per day, not fixed** · accepted · 2026-10-11
Supersedes the "one active truck per driver" and "own truck" parts of D-033 (client meeting).
- A driver may drive truck X today and truck Y tomorrow. The truck of the day is set by the office or by
  the driver from the phone; one driver per truck per day (confirmed). It lives on the driver's day (`DriverDay`, P3-T01), not on the truck.
- "Own truck" becomes "the truck of my open day": `may_use_location` / `may_use_truck` and `/me` read
  the open day. Until Phase 3 exists, the `Truck.driver` field stays as the default proposal.
- A truck load carries the price per kg of each product for that day; the evening return shows sold vs
  returned (P1-T09, P3-T01, P3-T06).

**D-043 · Supplier invoices, payments and the supplier balance (P1-T08)** · accepted · 2026-10-11
- In `purchasing` (not a separate `payments` app, which ARCHITECTURE §3 now keeps for customer
  receipts): `SupplierInvoice` (number `FF-0001`… per organization, supplier, the supplier's own invoice
  number, date, due date, status, total, notes, who typed and who posted it), `SupplierInvoiceReceipt`
  (receipt one-to-one: a receipt is on one invoice at most, draft or posted; with its amount),
  `SupplierPayment` (number `RF-0001`…, date, amount, method, cheque/transfer reference, notes) and
  `SupplierPaymentAllocation` (payment → invoice, amount). Numbers come from a locked `DocumentCounter`
  per organization and kind; a deleted draft leaves a gap (these are not fiscal numbers).
- **The amount is never typed:** an invoice's total is the sum of its receipts' invoiced amounts
  (invoiced kg × cost per line, rounded per line, D-039). A supplier whose paper invoice differs is
  corrected on the receipt side (later: supplier credit note), not on the invoice. No VAT on supplier
  invoices for now: costs are without VAT (D-020); provisional until the accountant answers Q5.
- **Status:** `draft` (receipts, dates, reference and notes can change; can be deleted) → `posted`
  (immutable, counts in the balance; `post` can be given on create/update to post at once; a zero total
  is refused) → `partly_paid` → `paid`, moved only by allocations. A posted invoice is never edited or
  deleted; a correction will be a supplier credit note (not built yet).
- **Payments** are immutable. Allocations go to posted, not fully paid invoices of the same supplier,
  never above what is left on an invoice, and together never above the payment. The part not allocated
  is an **advance**: already deducted from the balance, allocated later (`allocateSupplierPayment`).
  Errors come back on `allocations.<index>.<field>`, like receipt lines. Methods: cash, cheque,
  transfer, bill of exchange (traite), other (provisional list).
- **Supplier balance = posted invoices − payments** (negative = advance). The balance endpoint also
  gives what is still owed on invoices, what is overdue (due date passed), unallocated advances, drafts
  and receipts not invoiced yet; the supplier page shows it. It is the **trade payable only**: a
  partner's capital and profit share (D-040, Phase 6) are separate balances and never pass through
  these tables.
- **Due date:** typed; the form proposes invoice date + 30 days (provisional, no client answer on
  payment terms). An archived supplier can still be invoiced and paid (debts outlive the archive).
- Permissions as receipts: owner/manager write, accountant reads, drivers 403. Enum schema names are
  pinned (`SupplierInvoiceStatusEnum`, `PaymentMethodEnum`) so later sales documents do not collide.
- Admin "Achats" gets tabs Réceptions · Factures · Paiements: invoice list (status, overdue, supplier
  filters), invoice page (post, edit, delete draft, pay), invoice form (pick the supplier's receipts not
  invoiced yet), payment form (spread over the oldest due dates, or pay the invoice it came from),
  payments list with "Affecter" for advances. Demo: `FF-0001` for `BR-0001` (1 471,500 DT), posted,
  `RF-0001` 500 DT by cheque: Mareyeur Port de Sfax owes 971,500 DT.

**D-047 · Customers (P2-T01)** · accepted · 2026-10-11
- `Customer` and `CustomerContact` live in the `partners` app beside suppliers and copy D-032: reference
  `C-NNN` generated when left empty, optional tax ID in the same `1234567A/A/M/000` shape (unique per
  organization when given), contacts replaced as a whole list, no delete (archive / restore), audit before/after.
- Fields beyond the suppliers': `kind` (restaurant, hotel, fish shop, supermarket, wholesaler, caterer,
  individual), `credit_limit` (Decimal, 3 places, 0 = no credit, Q16) and `payment_terms_days` (0 to 365,
  0 = on delivery). What happens above the limit is a company setting of P2-T06, not stored here.
- **Walk-in customer** ("Client de passage"): `is_walk_in`, one per organization (partial unique
  constraint), created by `partners.services.ensure_walk_in_customer` (idempotent; the seed and counter
  sales call it), never archived, credit limit always 0. It is listed last.
- Customers are **office data** like suppliers: owner, manager and accountant read, owner and manager
  change, drivers get 403 (`ReadOfficeWriteOwnerOrManager`). Provisional: the driver app (Phase 3) will need
  a narrower endpoint (name, reference, credit left) for choosing a customer on credit; add it then.
- The balance, opening balances (`opening_balance_dt` of the sample CSV) and history are not on `Customer`:
  they come from sales, invoices and payments (P2-T04 to P2-T06). The seed loads limits and terms only.
- `ENUM_NAME_OVERRIDES` in the schema settings names the customer kind enum `CustomerKindEnum`: several
  models have a `kind` field and the generated names collided.

**D-046 · Truck of the day: assignment per date (P1-T12)** · accepted · 2026-10-11
Builds D-042 before Phase 3's `DriverDay` exists.
- `fleet.TruckAssignment` (organization, truck, driver, date): unique per truck and date and per driver and
  date (database constraints, plus clear service errors naming who has the truck or where the driver is).
  `Truck.driver` stays as the **usual driver**; the "one active truck per driver" constraint is gone, a
  driver may be the usual driver of several trucks.
- Truck of the driver today = today's assignment; without one, the truck they usually drive unless
  another driver was assigned to it that day (then none). Several usual trucks: first by name.
  `may_use_truck`, `may_use_location`, the truck list for drivers and `/me` all use it.
- Set by owner/manager for any driver and any day, or by a driver for themselves (today or later).
  The office must remove an assignment before giving the driver another truck; a driver's own new choice
  replaces their previous one. Accountant reads only. Archiving a truck drops its assignments from today.
- API: `GET/POST /api/v1/truck-assignments`, `DELETE /api/v1/truck-assignments/<id>`. Admin: "Camions du
  jour" section on the stock screen. A driver-side screen to pick the truck comes with Phase 3.


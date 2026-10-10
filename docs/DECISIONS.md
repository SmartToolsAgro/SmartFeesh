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

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

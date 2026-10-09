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

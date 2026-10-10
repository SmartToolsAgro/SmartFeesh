# Project status

_Last updated: 2026-10-10_

## Where we are

- **Phase:** 0 · Discovery & foundations (`docs/phases/00-foundations.md`)
- **Current task:** P0-T07 · Design system from the prototype (owner: agent)
- **In parallel (human):** P0-T01 client workshop, P0-T02 profit-sharing worked example

## Next step (do this first)

1. **Push the branches and check CI.** Three stacked branches, none pushed: `p0-t04-quality-ci` →
   `p0-t05-core-app` → `p0-t06-auth`. The workflow has never run on GitHub. All three jobs (backend,
   frontend, e2e) must be green; if an action input changed, fix `.github/workflows/ci.yml`. That closes
   P0-T04's acceptance.
2. Agent: start **P0-T07**. Read only its section of the phase file. Port the prototype's colour tokens
   (light and dark), fonts, radius and shadows into a Tailwind preset in `packages/ui`, theme the base
   shadcn/ui components, and build the two app shells. The login page in `packages/auth` and the two
   `Home` scaffold screens are unstyled on purpose: restyle them here.

## Blockers / waiting on client

- No open question blocks Phases 0–5. Q1–Q17 are answered in `docs/OPEN_QUESTIONS.md`.
- **P0-T02** (worked example on one real month) is not started. Phase 6 has no target without it, and
  it must settle one rule: a loss larger than a supplier's remaining capital (Q3).
- **P0-T01** is not finished: no prototype walk-through or client materials yet. Stand-in data is in
  `docs/spec/sample/` (D-019); real data is needed for P4-T01.
- VPS at OVH (D-019); size to choose before P0-T11. Printer model to choose in P3-T10.
- **TTN / El Fatoora is on hold** (D-016) although Q5 says it is required now.
- **For the accountant** (`docs/spec/sample/README.md`): the VAT code lists Tunisian fishing products as
  exempt, which does not match "19 % for all"; e-invoicing is mandatory since 01/01/2026.

## Watch out

- The Docker stack (`make dev`) has not been run yet. Whoever has Docker: run it once and note the result.
- Mahmoud's Windows machine: no `make`, `pnpm`, `docker` or `psql` on the PATH; corepack cannot download
  pnpm there, `npx -y pnpm@10.28.0 <command>` works. A PostgreSQL 18 service listens on 5432 but has no
  `frutti` role yet: create it from `.env.example` to run the backend and browser tests.
- Run `make lint` before every commit (or `make hooks` once); CI runs the same checks.
- API: 401 = not logged in, 403 = role not allowed (D-023). Every view sets a permission class from
  `apps/core/permissions.py` and scopes its queryset with `.for_organization(org)` (D-022).
- Login throttling counts per server process until Redis arrives (D-023).
- P3-T10 (Bluetooth printing on iPhone) may force a native wrapper for the truck app (D-015).
- VAT rate, stamp, prices with or without VAT, withholding rate and the over-credit-limit behaviour are
  organization settings (D-018). Purchase and sale prices change daily (D-020).

## Last session (2026-10-10)

- Q1–Q17 answered and written down; plan updated (D-014 to D-020); stand-in data in `docs/spec/sample/`.
- **P0-T04** (D-021): ruff, mypy, import-linter boundary contract, eslint, prettier, vitest, GitHub
  Actions, pre-commit, `make lint` / `format` / `hooks`. CI run pending first push.
- **P0-T05** (D-022): custom `User` in migration 0001, `Organization`, `Membership` with four roles,
  `OrganizationScopedModel`, money helpers, append-only `AuditLog`, `seed_dev`.
- **P0-T06** (D-023): login/logout/me API with CSRF and rate limiting, role permission classes, shared
  `@frutti/auth` package, login screens and route guards in both apps, Playwright tests. Left open: the
  "own truck" helper, moved to P1-T04.
- Local results: 57 backend tests, 8 vitest tests, 5 Playwright tests, all linters and type checks pass.

## Recently done

- 2026-10-10 · P0-T06 authentication and permissions
- 2026-10-10 · P0-T05 core app
- 2026-10-10 · P0-T04 quality tooling and CI (CI run pending)

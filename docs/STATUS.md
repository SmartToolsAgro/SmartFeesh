# Project status

_Last updated: 2026-10-10_

## Where we are

- **Phase:** 0 · Discovery & foundations (`docs/phases/00-foundations.md`)
- **Current task:** P0-T08 · Internationalisation (owner: agent)
- **In parallel (human):** P0-T01 client workshop, P0-T02 profit-sharing worked example

## Next step (do this first)

1. **Check CI on GitHub (Actions tab), then open the pull requests.** Four stacked branches were pushed
   on 2026-10-10: `p0-t04-quality-ci` → `p0-t05-core-app` → `p0-t06-auth` → `p0-t07-design-system`.
   Nobody has looked at the
   result yet (the repository is private and the session had no GitHub access). All jobs (backend,
   frontend, and e2e on the last branch) must be green; if an action input changed, fix
   `.github/workflows/ci.yml`. That closes P0-T04's acceptance. Merge in order, oldest first.
2. Agent: start **P0-T08**. Read only its section of the phase file. Django i18n + i18next, French
   default, every UI string through a translation function, RTL switch tested with a dummy Arabic
   string, the user's `language` followed by both apps, number and date formats (`1 250,000 DT`,
   `dd/mm/yyyy`). UI strings are hard-coded French today in `packages/ui`, `packages/auth` and both apps.

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
- **P0-T07** (D-024): Tailwind 4 theme from the prototype's tokens, self-hosted fonts, icon and
  illustration sprite, Button, Input, Select, Card, Pill, Table, Dialog, Toast, admin and truck shells,
  restyled login, theme switch. Every prototype module has a "Bientôt disponible" route.
- Local results: 57 backend tests, 13 vitest tests, 10 Playwright tests, all linters and type checks pass.

## Recently done

- 2026-10-10 · P0-T07 design system and app shells
- 2026-10-10 · P0-T06 authentication and permissions
- 2026-10-10 · P0-T05 core app

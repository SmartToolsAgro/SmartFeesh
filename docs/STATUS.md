# Project status

_Last updated: 2026-10-10_

## Where we are

- **Phase:** 0 · Discovery & foundations (`docs/phases/00-foundations.md`)
- **Current task:** P0-T06 · Authentication & permissions (owner: agent)
- **In parallel (human):** P0-T01 client workshop, P0-T02 profit-sharing worked example

## Next step (do this first)

1. **Push the branches and check CI.** `p0-t05-core-app` is stacked on `p0-t04-quality-ci`. The workflow
   has never run. Both jobs must be green; if an action input changed, fix `.github/workflows/ci.yml`.
   That closes P0-T04's acceptance.
2. Agent: start **P0-T06**. Read only its section of the phase file and ARCHITECTURE §4 rule 8. Session
   login/logout with CSRF, `/api/v1/me`, DRF permission classes per role, login screens and route guards
   in both apps. Use `apps.core.selectors.active_membership(user)` for the role, and scope every
   queryset with `.for_organization(org)` (D-022). `make seed` gives logins `owner` and `driver`.

## Blockers / waiting on client

- No open question blocks Phases 0–5. Q1–Q17 are answered in `docs/OPEN_QUESTIONS.md`.
- **P0-T02** (worked example on one real month) is not started. Phase 6 has no target without it, and
  it must settle one rule: a loss larger than a supplier's remaining capital (Q3).
- **P0-T01** is not finished: prototype walk-through, client materials (`docs/spec/client/`) and screen
  change requests are not available. Stand-in data is in `docs/spec/sample/` (D-019): use it for seeds,
  tests and demos; real data is needed for P4-T01.
- VPS at OVH (D-019); size to choose before P0-T11. Printer model to choose in P3-T10.
- **TTN / El Fatoora is on hold** (D-016) although Q5 says it is required now. Q18 stays on hold with it.
- **For the accountant** (`docs/spec/sample/README.md`): the VAT code lists Tunisian fishing products as
  exempt, which does not match "19 % for all"; e-invoicing is mandatory since 01/01/2026.

## Watch out

- The Docker stack (`make dev`) has not been run yet. Whoever has Docker: run it once and note the result.
- Mahmoud's Windows machine: no `make`, `pnpm`, `docker` or `psql` on the PATH; corepack cannot download
  pnpm there, `npx -y pnpm@10.28.0 <command>` works. A PostgreSQL 18 service listens on 5432 but has no
  `frutti` role yet: create it from `.env.example` to run the backend tests.
- Run `make lint` before every commit (or `make hooks` once); CI runs the same checks.
- P3-T10 (Bluetooth printing on iPhone) may force a native wrapper for the truck app. Its spike decides;
  until then the truck app stays a PWA (D-002, D-003, D-015).
- VAT rate, stamp, prices with or without VAT, withholding rate and the over-credit-limit behaviour are
  organization settings, never constants (D-018).
- Purchase and sale prices change daily, sale prices even within a day: cost per batch, timestamped
  sale prices, snapshots on sale lines (D-020).

## Last session (2026-10-10)

- Q1–Q17 answered by Mahmoud and written in `docs/OPEN_QUESTIONS.md`; plan updated (D-014 to D-020);
  stand-in sample data added in `docs/spec/sample/`.
- **P0-T04 built** (D-021): ruff, mypy + django-stubs, a custom import-linter boundary contract, factory_boy,
  eslint (type-aware), prettier, vitest with a first component test, GitHub Actions workflow, pre-commit
  hooks, `make lint` / `make format` / `make hooks`, `.gitattributes` for LF. All checks pass locally,
  including 12 backend tests on PostgreSQL 16. CI itself is unverified until the first push.
- **P0-T05 done** (D-022): custom `User` in migration 0001, `Organization`, `Membership` with four roles,
  `OrganizationScopedModel`, `money()` / `quantity()` and their fields, append-only `AuditLog` with
  `audit.record()`, `seed_dev`. 38 backend tests pass.

## Recently done

- 2026-10-10 · P0-T05 core app: custom user, organization, roles, money helpers, audit log, seed (D-022)
- 2026-10-10 · P0-T04 quality tooling and CI (CI run pending)
- 2026-10-10 · Client questions answered, plan updated
- 2026-10-09 · P0-T03 monorepo scaffold

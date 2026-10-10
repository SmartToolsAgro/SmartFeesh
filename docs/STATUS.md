# Project status

_Last updated: 2026-10-10_

## Where we are

- **Phase:** 0 · Discovery & foundations (`docs/phases/00-foundations.md`)
- **Current task:** P0-T09 · API contract & generated client (owner: agent)
- **In parallel (human):** P0-T01 client workshop, P0-T02 profit-sharing worked example

## Next step (do this first)

1. **Check CI on GitHub (Actions tab), then open the pull requests.** Five stacked branches were pushed
   on 2026-10-10: `p0-t04-quality-ci` → `p0-t05-core-app` → `p0-t06-auth` → `p0-t07-design-system` →
   `p0-t08-i18n`. Nobody has looked at the result yet: the repository is private and the session had no
   GitHub access. All jobs (backend, frontend, e2e) must be green; if an action input changed, fix
   `.github/workflows/ci.yml`. That closes P0-T04's acceptance. Merge in order, oldest first.
2. Agent: start **P0-T09**. Read only its section of the phase file. Generate the TypeScript client and
   Zod schemas into `packages/api` with orval from the schema (`manage.py spectacular`), add
   `make gen-api`, and make CI fail when the generated client is out of date. Then replace the
   hand-written `Session` type and calls in `packages/auth` with the generated ones (D-023).

## Blockers / waiting on client

- No open question blocks Phases 0–5. Q1–Q17 are answered in `docs/OPEN_QUESTIONS.md`.
- **P0-T02** (worked example on one real month) is not started. Phase 6 has no target without it, and
  it must settle one rule: a loss larger than a supplier's remaining capital (Q3).
- **P0-T01** is not finished: no prototype walk-through or client materials yet. Stand-in data is in
  `docs/spec/sample/` (D-019); real data is needed for P4-T01.
- **P0-T10** needs the `session-start-hook` skill, which was not available in the last session.
- **P0-T11** (staging) needs an OVH VPS: size to choose, then access for the agent (D-019).
- **TTN / El Fatoora is on hold** (D-016) although Q5 says it is required now.
- **For the accountant** (`docs/spec/sample/README.md`): the VAT code lists Tunisian fishing products as
  exempt, which does not match "19 % for all"; e-invoicing is mandatory since 01/01/2026.

## Watch out

- The Docker stack (`make dev`) has not been run yet. Whoever has Docker: run it once and note the result.
- Mahmoud's Windows machine: no `make`, `pnpm`, `docker`, `psql` or gettext on the PATH; corepack cannot
  download pnpm there, `npx -y pnpm@10.28.0 <command>` works. A PostgreSQL 18 service listens on 5432
  but has no `frutti` role yet: create it from `.env.example` to run the backend and browser tests.
- Run `make lint` before every commit (or `make hooks` once); CI runs the same checks.
- API: 401 = not logged in, 403 = role not allowed (D-023). Every view sets a permission class from
  `apps/core/permissions.py` and scopes its queryset with `.for_organization(org)` (D-022).
- UI: no hard-coded text. Add the key to `packages/i18n/src/fr.ts` and use `t()`; amounts, weights and
  dates go through `formatMoney`, `formatQuantity`, `formatDate`; use `ms-`/`me-`/`text-start`, never
  left/right classes (D-025). Colours come from the tokens, never `dark:` variants (D-024).
- Login throttling counts per server process until Redis arrives (D-023).
- VAT rate, stamp, prices with or without VAT, withholding rate and the over-credit-limit behaviour are
  organization settings (D-018). Purchase and sale prices change daily (D-020).

## Last session (2026-10-10)

- Q1–Q17 answered; plan updated (D-014 to D-020); stand-in data in `docs/spec/sample/`.
- **P0-T04** quality tooling and CI (D-021), **P0-T05** core app (D-022), **P0-T06** authentication and
  permissions (D-023), **P0-T07** design system and shells (D-024), **P0-T08** internationalisation (D-025).
- Local results: 62 backend tests, 21 vitest tests, 10 Playwright tests, all linters and type checks pass.
- Not verified: the GitHub Actions run, the Docker stack, and how the screens look in Arabic.

## Recently done

- 2026-10-10 · P0-T08 internationalisation
- 2026-10-10 · P0-T07 design system and app shells
- 2026-10-10 · P0-T06 authentication and permissions

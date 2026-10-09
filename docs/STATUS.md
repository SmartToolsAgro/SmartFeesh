# Project status

_Last updated: 2026-10-09_

## Where we are

- **Phase:** 0 · Discovery & foundations (`docs/phases/00-foundations.md`)
- **Current task:** P0-T04 · Quality tooling & CI (owner: agent)
- **In parallel (human):** P0-T01 client workshop, P0-T02 profit-sharing worked example

## Next step (do this first)

Agent: start **P0-T04**. Read only the P0-T04 section of the phase file. Add ruff, mypy + django-stubs,
import-linter (backend) and eslint + prettier + vitest (frontend), then a GitHub Actions workflow with a
Postgres service that runs `make test` plus the linters. Keep JS versions pinned per D-012.

After P0-T04, do **P0-T05** (custom User model). It must be the **first migration** in the project:
do not run `migrate` on a shared database before it exists.

## Blockers / waiting on client

- Q1–Q4 (profit basis, expense allocation, capital return, multi-supplier products) block Phase 6.
  They do not block Phases 0–3.
- Q5 (tax and invoice rules, TTN e-invoicing) blocks P2-T05.

## Watch out

- The Docker stack (`make dev`) has not been run yet: no Docker daemon in cloud sessions. Everything was
  verified with a local PostgreSQL instead. Whoever has Docker: run it once and note the result here.

## Last session (2026-10-09)

- **P0-T03 done:** Django 5.2 backend (split settings, DRF, OpenAPI, `/api/v1/health`, 2 tests),
  pnpm + Turborepo frontend (`apps/admin`, `apps/truck`, `packages/ui`, `packages/api`), Docker Compose,
  Makefile, `.env.example`. Both apps reach the API through the Vite proxy.
- Decisions D-012 (pinned two-week-old versions, TypeScript 6.0) and D-013 (uv + pnpm).

## Recently done

- 2026-10-09 · P0-T03 monorepo scaffold
- 2026-10-09 · Prototype + development plan + find-skills skill

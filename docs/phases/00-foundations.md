# Phase 0 · Discovery & foundations

**Goal:** answers to the questions that shape the data model, and a running skeleton that every later
phase builds on.
**Done when:** `docker compose up` runs backend + both front ends; an owner and a driver can log in and
each sees only their own area; CI is green; staging is reachable; P0-T01 and P0-T02 are recorded.
**Out of scope:** any business module (products, stock…).

---

### P0-T01 · Client workshop with the prototype · owner: human · S
- [ ] Walk the client through `prototype/index.html` (both views).
- [x] Ask every question in `docs/OPEN_QUESTIONS.md`; write answers in the table.
- [ ] Collect (until then, use the stand-in data in `docs/spec/sample/`, built from public Tunisian
      sources on 2026-10-10): product list with units and prices, suppliers, customers, trucks, employees, a sample
      supplier contract, a sample invoice they issue today, real product photos.
- [ ] Note any screen the client wants changed.

**Acceptance:** Q1–Q4 answered or explicitly marked "client unsure"; materials stored in `docs/spec/client/`.

### P0-T02 · Profit-sharing worked example on one real month · owner: human + agent · M
- [ ] Take one real past month: sales, purchases, stock left, every expense, salaries. No numbers are
      available yet (2026-10-10); invented numbers cannot replace them for this task.
- [ ] For one partner supplier, compute their share by hand (spreadsheet) the way the client does today.
- [ ] Compare with what was actually paid to them. Explain any difference.
- [ ] Write it up in `docs/spec/profit-sharing-worked-example.md` with every number and rule.

**Acceptance:** the client agrees the write-up matches how they calculate. This file becomes the golden
test for the profit engine (P6-T05).

### P0-T03 · Monorepo scaffold · owner: agent · M
Read: ARCHITECTURE §2–3.
- [x] `backend/`: Django 5.2 project with split settings (base/dev/test/prod), env vars via django-environ,
      DRF, drf-spectacular, `apps/` package, health endpoint `/api/v1/health`.
- [x] `frontend/`: pnpm workspace + Turborepo; `apps/admin`, `apps/truck` (Vite + React + TS),
      `packages/ui`, `packages/api` (empty for now).
- [x] `docker-compose.yml`: postgres, redis, backend, admin, truck. One `Makefile` (or `justfile`) with
      `dev`, `test`, `lint`, `migrate`, `gen-api`.
- [x] `.env.example`, `.gitignore`, `.editorconfig`, top-level README with how to run.
- [x] Fill the **Commands** section of `CLAUDE.md`.

**Acceptance:** fresh clone → `make dev` → health endpoint returns 200, both front ends render a page.

_Done 2026-10-09. Verified without Docker (local PostgreSQL + `make backend` / `make frontend`): health 200,
both apps load and show "Serveur connecté" through the dev proxy, 2 backend tests pass, both apps build.
`docker-compose.yml` passes `docker compose config` but was **not run** (no Docker daemon in the cloud
session). First person with Docker: run `make dev` once and report._

### P0-T04 · Quality tooling & CI · owner: agent · S
- [x] Backend: ruff (lint + format), mypy with django-stubs, pytest + pytest-django + factory_boy,
      import-linter contract (apps only use each other's `services`/`selectors`; `core` imports nothing).
- [x] Frontend: eslint, prettier, `tsc --noEmit`, vitest.
- [x] GitHub Actions: backend job (with Postgres service) and frontend job, on every push and PR.
- [x] pre-commit hooks for formatting.

**Acceptance:** CI green on the branch; a deliberate lint error fails CI.

_Built 2026-10-10 (D-021). Verified locally on Windows: `ruff check`, `ruff format --check`, `mypy`,
`lint-imports`, 12 backend tests against PostgreSQL 16, `eslint`, `prettier --check`, `tsc`, 2 vitest
tests, pre-commit on all files; a deliberate error makes ruff, eslint and the boundary contract fail.
**Not verified:** the GitHub Actions workflow itself has never run, because the branch is not pushed.
First push: check that both jobs are green, and fix the workflow if an action input changed._

### P0-T05 · Core app: organization, users, roles, audit · owner: agent · M
Read: ARCHITECTURE §4 rules 1, 2, 6, 8, 9.
- [x] **Custom `User` model in the first migration** (cannot be changed cheaply later).
- [x] `Organization`; `OrganizationScopedModel` abstract base (FK + scoped manager); `TimeStampedModel`.
- [x] Roles: `owner`, `manager`, `driver`, `accountant` (membership: user ↔ organization ↔ role).
      The accountant reviews the month-end closing before the owner approves it (Q9).
- [x] `Money` and `Quantity` helpers (Decimal, 3 places, ROUND_HALF_UP) with unit tests.
- [x] `AuditLog` model + `audit.record(...)` service.
- [x] Seed command: one organization, one owner, one driver (dev only).

**Acceptance:** tests cover Money rounding, scoped querysets never leak across organizations, audit entries written.

_Done 2026-10-10 (D-022). 38 backend tests pass on PostgreSQL 16; `migrate` then `seed_dev` (twice) run on
an empty database. The user's `language` preference (fr | ar) from P0-T08 is already on the model._

### P0-T06 · Authentication & permissions · owner: agent · M
- [x] Session login/logout API with CSRF; `/api/v1/me` (user, role, organization, truck if driver).
      `truck` is always `null` until trucks exist (P1-T04).
- [x] DRF permission classes: `IsOwnerOrManager`, `IsDriver` (and `IsMember`, `HasRole`).
- [ ] Object-level helper for "own truck": moved to P1-T04, where the `Truck` model is created.
- [x] Login screen in both apps; route guard; the admin app refuses drivers and vice versa.
- [x] Rate limiting on login.

**Acceptance:** API tests prove a driver gets 403 on admin endpoints; Playwright test logs in to each app.

_Done 2026-10-10 (D-023), except the "own truck" helper. 57 backend tests, 8 vitest tests and 5
Playwright tests pass locally (owner and driver log in and out; each app turns the other role away).
The login screens are unstyled: the design system is P0-T07._

### P0-T07 · Design system from the prototype · owner: agent · M
- [ ] Port colour tokens (light + dark), fonts, radius, shadows from `prototype/index.html` into a Tailwind
      preset in `packages/ui`.
- [ ] Icons and seafood illustrations as React components.
- [ ] shadcn/ui base components themed: Button, Input, Select, Card, Badge/Pill, Table, Dialog, Toast.
- [ ] App shells: admin (sidebar + top bar), truck (phone layout + bottom nav), matching the prototype.

**Acceptance:** both apps show their empty shell looking like the prototype, in light and dark.

### P0-T08 · Internationalisation · owner: agent · S
- [ ] Django i18n + i18next; French default; all UI strings through translation functions.
- [ ] RTL support switch (`dir="rtl"`) tested with a dummy Arabic string. No translation yet
      (the driver app is translated in P3-T09).
- [ ] `language` preference on the user (fr | ar); both apps follow it. Drivers choose theirs (Q14).
      The field exists since P0-T05; what is left is the API and the apps following it.
- [ ] Number/date formatting helpers: `1 250,000 DT`, `dd/mm/yyyy`.

### P0-T09 · API contract & generated client · owner: agent · S
- [ ] drf-spectacular schema at `/api/v1/schema`; orval generates TS client + Zod schemas into `packages/api`.
- [ ] `make gen-api`; CI fails if the generated client is out of date.

### P0-T10 · Cloud session hook · owner: agent · S
- [ ] Use the `session-start-hook` skill to add a SessionStart hook that installs dependencies so tests
      and linters run in fresh cloud sessions.

### P0-T11 · Staging deployment · owner: agent + human · M
- [ ] Production Dockerfile (gunicorn, static files, both front ends built).
- [ ] Deploy to a staging VPS at OVH running the Docker stack (D-017, D-019). Size still to choose (human).
- [ ] Automatic deploy from `main`; HTTPS; Sentry connected.

**Acceptance:** the client can open staging on their phone and log in as a demo driver.

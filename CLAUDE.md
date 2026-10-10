# Frutti Del Mare ERP

Seafood distribution ERP for Frutti Del Mare (Sakiet Ezzit, Sfax, Tunisia): purchases, cold-room and
truck stock, quotes, sales and invoicing, a driver phone app, expenses and payroll, and the key feature,
**month-end supplier profit sharing**. The UI is in French (Arabic planned) and amounts are in Tunisian
dinars (DT) with 3 decimals.

## Read this first: how to work in this repo (saves context)

1. **Always read `docs/STATUS.md` first.** It says which phase and task we are on, what the last session
   did, and the exact next step. It is short on purpose.
2. **Then read only the current phase file** named in STATUS (`docs/phases/NN-*.md`), and only the
   section for the current task.
3. Read other docs **only when the task needs them**:
   - `docs/ARCHITECTURE.md`: stack, folder layout, hard technical rules. Read the section you are touching.
   - `docs/DECISIONS.md`: why things are the way they are. Read before changing a convention.
   - `docs/OPEN_QUESTIONS.md`: client questions. Never invent answers to an open question; if a task
     depends on one, stop and say so.
   - `docs/spec/project-brief.md`: full business brief. Search it (grep) instead of reading it whole.
   - `prototype/index.html`: the approved look and feel (clickable mockup).
4. Do **one task per session / per PR** (task IDs look like `P1-T06`).

## At the end of every session (required)

1. Tick the finished items in the phase file (`- [x]`).
2. Rewrite `docs/STATUS.md`: current task, what you did, the **exact next step**, blockers.
   Keep it under ~60 lines; move old "recently done" lines out.
3. Add a line to `docs/DECISIONS.md` if you made or changed a technical decision.
4. Commit the docs **together with the code**. A fresh session starts from a fresh clone, so anything
   not pushed is lost.

## Hard rules (details in docs/ARCHITECTURE.md)

- Money: `Decimal`, 3 decimal places (millimes). Never floats. Weights: `Decimal`, kg, 3 decimals.
- Stock is an **append-only movement ledger**. Never edit a quantity directly; post a movement.
- All writes go through `services.py` functions inside a DB transaction; views/serializers never write models.
- Every business table has an `organization` foreign key (multi-company ready).
- Permissions are enforced **on the server**. Hiding a button is not security.
- Issued invoices, approved closings and posted movements are immutable; corrections are new records.
- Supplier payables, invested capital, and profit shares are **three separate balances**.

## Commands

| What | Command |
|---|---|
| Whole stack in Docker | `make dev` (admin :5173, driver :5174, API :8000) |
| Install locally | `make install` (backend: `uv sync`; frontend: `pnpm install`) |
| Backend / frontend dev servers | `make backend`, `make frontend` (need PostgreSQL at `DATABASE_URL`) |
| Tests | `make test` (pytest + TypeScript type checks + vitest) |
| Browser tests | `make e2e` (Playwright; first time: `cd frontend && pnpm --filter @frutti/e2e exec playwright install chromium`) |
| Lint, format check, types, app boundaries | `make lint` (ruff, mypy, import-linter, eslint, prettier); CI runs the same |
| Auto-format | `make format` |
| Git hooks (once per clone) | `make hooks` |
| Migrations | `make makemigrations`, `make migrate` |
| API client | `make gen-api` after changing an endpoint or serializer; commit `frontend/packages/api` (CI checks it) |
| Dev data | `make seed` (organization + logins `owner` and `driver`, password `frutti-dev`; DEBUG only) |
| One backend test | `cd backend && uv run pytest apps/core/tests/test_health.py` |
| Add a Python package | `cd backend && uv add <pkg>` (dev: `uv add --dev <pkg>`) |
| Add a JS package | `cd frontend && pnpm --filter @frutti/admin add <pkg>` |

Cloud sessions without Docker: PostgreSQL 16 is installed; start it with `pg_ctlcluster 16 main start`,
then create the role/database from `.env.example` with `runuser -u postgres -- psql`.

Pin new JS packages to an exact version that is at least two weeks old (see D-012).

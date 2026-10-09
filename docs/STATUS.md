# Project status

_Last updated: 2026-10-10_

## Where we are

- **Phase:** 0 · Discovery & foundations (`docs/phases/00-foundations.md`)
- **Current task:** P0-T04 · Quality tooling & CI (owner: agent)
- **In parallel (human):** P0-T01 client workshop, P0-T02 profit-sharing worked example

## Next step (do this first)

Agent: start **P0-T04**. Read only the P0-T04 section of the phase file. Add ruff, mypy + django-stubs,
import-linter (backend) and eslint + prettier + vitest (frontend), then a GitHub Actions workflow with a
Postgres service that runs `make test` plus the linters. Keep JS versions pinned per D-012.

After P0-T04, do **P0-T05** (custom User model). It must be the **first migration** in the project:
do not run `migrate` on a shared database before it exists. Roles now include `accountant` (Q9).

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

- The Docker stack (`make dev`) has not been run yet: no Docker daemon in cloud sessions. Everything was
  verified with a local PostgreSQL instead. Whoever has Docker: run it once and note the result here.
- P3-T10 (Bluetooth printing on iPhone) may force a native wrapper for the truck app. Its spike decides;
  until then the truck app stays a PWA (D-002, D-003, D-015).
- VAT rate, stamp, prices with or without VAT, withholding rate and the over-credit-limit behaviour are
  organization settings, never constants (D-018).
- Purchase and sale prices change daily, sale prices even within a day: cost per batch, timestamped
  sale prices, snapshots on sale lines (D-020).

## Last session (2026-10-10)

- Q1–Q17 answered by Mahmoud, with their details, and written in `docs/OPEN_QUESTIONS.md`. No code changed.
- Plan updated for the answers: Arabic for drivers → P3-T09, Bluetooth receipt printing → P3-T10,
  multi-company task list in Phase 8, Phases 0–6 adjusted, roadmap updated (D-015).
- Decisions: D-014 FIFO costing confirmed, D-016 TTN on hold, D-017 VPS hosting, D-018 finance settings,
  D-019 OVH and stand-in sample data (`docs/spec/sample/`, 6 CSV files, invoice and agreement models).

## Recently done

- 2026-10-10 · Client questions answered, plan updated
- 2026-10-09 · P0-T03 monorepo scaffold
- 2026-10-09 · Prototype + development plan + find-skills skill

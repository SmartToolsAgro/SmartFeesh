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

Not scaffolded yet (task P0-T03). Fill this in when it exists: dev server, tests, lint, migrations.

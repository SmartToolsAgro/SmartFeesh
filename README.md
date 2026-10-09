# Frutti Del Mare ERP

Management software for a seafood distributor: purchases, cold-room and truck stock, quotes, sales and
invoicing, a phone app for drivers, expenses and payroll, and month-end profit sharing with partner suppliers.

- **See it:** open `prototype/index.html` in a browser (clickable mockup, sample data).
- **Plan:** [`docs/ROADMAP.md`](docs/ROADMAP.md) → phases in [`docs/phases/`](docs/phases/).
- **Where we are now:** [`docs/STATUS.md`](docs/STATUS.md).
- **How it is built:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/DECISIONS.md`](docs/DECISIONS.md).
- **Questions for the client:** [`docs/OPEN_QUESTIONS.md`](docs/OPEN_QUESTIONS.md).
- **Full business brief:** [`docs/spec/project-brief.md`](docs/spec/project-brief.md).

## Run it

```bash
make dev          # Docker: database, API, admin (http://localhost:5173), driver app (http://localhost:5174)
```

Without Docker: copy `.env.example` to `.env`, start PostgreSQL, then `make install`, `make migrate`,
and run `make backend` and `make frontend` in two terminals. Tests: `make test`.

Requirements: Python 3.12+ with [uv](https://docs.astral.sh/uv/), Node 22.12+ with pnpm (via corepack).

AI agents: start with [`CLAUDE.md`](CLAUDE.md).

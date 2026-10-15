#!/usr/bin/env bash
# SessionStart hook (P0-T10). Cloud sessions start from a fresh clone: install dependencies and start
# PostgreSQL so `make test` and `make lint` work at once (e2e runs in CI only, D-157). Local sessions are left alone.
set -uo pipefail

[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
cd "${CLAUDE_PROJECT_DIR:-$(pwd)}" || exit 0

step() { echo "[session-start] $*"; }

[ -f .env ] || { cp .env.example .env && step "created .env from .env.example"; }

step "backend dependencies"
(cd backend && uv sync --frozen) || step "WARNING: uv sync failed"

step "frontend dependencies"
export COREPACK_ENABLE_DOWNLOAD_PROMPT=0
corepack enable > /dev/null 2>&1 || true
(cd frontend && pnpm install --frozen-lockfile) || step "WARNING: pnpm install failed"

# PostgreSQL 16 is installed in cloud sessions (CLAUDE.md); role and database match .env.example.
if command -v pg_ctlcluster > /dev/null 2>&1; then
  step "PostgreSQL"
  pg_ctlcluster 16 main start 2> /dev/null || true
  as_postgres() { runuser -u postgres -- psql -v ON_ERROR_STOP=1 -qtAc "$1"; }
  [ "$(as_postgres "select 1 from pg_roles where rolname = 'frutti'")" = "1" ] \
    || as_postgres "create role frutti login createdb password 'frutti'" || step "WARNING: could not create the frutti role"
  [ "$(as_postgres "select 1 from pg_database where datname = 'frutti'")" = "1" ] \
    || as_postgres "create database frutti owner frutti" || step "WARNING: could not create the frutti database"
fi

step "ready: make test, make lint"
exit 0

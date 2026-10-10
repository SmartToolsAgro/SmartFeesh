# Common commands. Docker path: `make dev`. Without Docker: `make install`, then `make backend` and
# `make frontend` in two terminals (needs a local PostgreSQL matching DATABASE_URL in .env).
.PHONY: dev down install hooks backend frontend migrate makemigrations seed gen-api test e2e lint format build deploy-staging

dev:            ## Run the whole stack in Docker
	docker compose up

down:           ## Stop the Docker stack
	docker compose down

install:        ## Install backend and frontend dependencies locally
	cd backend && uv sync
	cd frontend && pnpm install

hooks:          ## Install the git pre-commit hooks (once per clone)
	uv run --project backend pre-commit install

backend:        ## Run the Django dev server on :8000
	cd backend && uv run python manage.py runserver

frontend:       ## Run both front ends (admin :5173, truck :5174)
	cd frontend && pnpm dev

migrate:        ## Apply database migrations
	cd backend && uv run python manage.py migrate

makemigrations: ## Create migrations after model changes
	cd backend && uv run python manage.py makemigrations

seed:           ## Dev data: one organization, logins owner and driver (password frutti-dev)
	cd backend && uv run python manage.py seed_dev

gen-api:        ## Regenerate the TypeScript API client after changing an endpoint or a serializer
	cd backend && uv run python manage.py spectacular --lang fr --validate --fail-on-warn --file ../frontend/packages/api/openapi.yaml
	cd frontend && pnpm gen-api

test:           ## Backend tests + frontend type checks and tests
	cd backend && uv run pytest
	cd frontend && pnpm typecheck && pnpm test

e2e:            ## Browser tests: starts the backend and both apps itself (needs PostgreSQL)
	cd frontend && pnpm e2e

lint:           ## Every check CI runs except tests: lint, format, types, app boundaries
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run lint-imports
	cd frontend && pnpm lint && pnpm format:check

format:         ## Format and auto-fix backend and frontend code
	cd backend && uv run ruff format . && uv run ruff check --fix .
	cd frontend && pnpm format

build:          ## Production build of both front ends
	cd frontend && pnpm build

deploy-staging: ## Deploy the committed HEAD to the staging VPS (needs SSH access)
	bash deploy/deploy.sh

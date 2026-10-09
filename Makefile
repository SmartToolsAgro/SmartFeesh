# Common commands. Docker path: `make dev`. Without Docker: `make install`, then `make backend` and
# `make frontend` in two terminals (needs a local PostgreSQL matching DATABASE_URL in .env).
.PHONY: dev down install backend frontend migrate makemigrations test build

dev:            ## Run the whole stack in Docker
	docker compose up

down:           ## Stop the Docker stack
	docker compose down

install:        ## Install backend and frontend dependencies locally
	cd backend && uv sync
	cd frontend && pnpm install

backend:        ## Run the Django dev server on :8000
	cd backend && uv run python manage.py runserver

frontend:       ## Run both front ends (admin :5173, truck :5174)
	cd frontend && pnpm dev

migrate:        ## Apply database migrations
	cd backend && uv run python manage.py migrate

makemigrations: ## Create migrations after model changes
	cd backend && uv run python manage.py makemigrations

test:           ## Backend tests + frontend type checks
	cd backend && uv run pytest
	cd frontend && pnpm typecheck

build:          ## Production build of both front ends
	cd frontend && pnpm build

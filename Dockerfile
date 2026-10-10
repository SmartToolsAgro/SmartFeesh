# Production images. Built from the repository root:
#   docker build --target backend -t frutti-backend .
#   docker build --target web -t frutti-web .
# deploy/compose.staging.yml builds both.

# ---- front ends: both apps built once ----
FROM node:22-bookworm-slim AS frontend
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
WORKDIR /app/frontend
RUN corepack enable
COPY frontend/ ./
RUN pnpm install --frozen-lockfile \
 && pnpm --filter @frutti/admin --filter @frutti/truck run build

# ---- backend: Django + gunicorn ----
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS backend
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/venv \
    PATH=/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
# Placeholder values: collectstatic needs settings to load, not the real secrets.
RUN DJANGO_SECRET_KEY=build-only DJANGO_ALLOWED_HOSTS=build python manage.py collectstatic --noinput
RUN useradd --system --no-create-home app  && mkdir -p /app/media && chown app /app/media
# Uploaded photos; a named volume mounted here starts with this owner (deploy/compose.staging.yml).
VOLUME /app/media
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]

# ---- web: nginx serving both apps and passing the API to the backend ----
FROM nginx:1.28-alpine AS web
COPY deploy/nginx-web.conf /etc/nginx/conf.d/default.conf
COPY deploy/frutti-app.inc /etc/nginx/conf.d/frutti-app.inc
COPY --from=frontend /app/frontend/apps/admin/dist /srv/admin
COPY --from=frontend /app/frontend/apps/truck/dist /srv/truck
EXPOSE 8081 8082

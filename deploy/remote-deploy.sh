#!/usr/bin/env bash
# Runs ON the staging server, from an unpacked release: deploy/remote-deploy.sh <release-id>
# Called by deploy/deploy.sh. Starts the stack, installs the nginx site, checks health, seeds demo logins.
set -euo pipefail

RELEASE="$1"
BASE="$HOME/frutti-staging"
RELEASE_DIR="$BASE/releases/$RELEASE"
ENV_FILE="$BASE/.env"
PUBLIC_HOST="${PUBLIC_HOST:-217.182.205.137}"
NGINX_SITE=/etc/nginx/sites-available/frutti-staging

# 1. Secrets: created once on the server, never in the repository.
if [ ! -f "$ENV_FILE" ]; then
  echo "Creating $ENV_FILE with new random secrets"
  umask 077
  cat > "$ENV_FILE" <<EOF
POSTGRES_PASSWORD=$(openssl rand -hex 24)
DJANGO_SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n')
DJANGO_ALLOWED_HOSTS=$PUBLIC_HOST
DJANGO_CSRF_TRUSTED_ORIGINS=http://$PUBLIC_HOST:8095,http://$PUBLIC_HOST:8096
DEMO_PASSWORD=$(openssl rand -base64 12 | tr -d '/+=\n')
SENTRY_DSN=
EOF
fi
chmod 600 "$ENV_FILE"
export RELEASE

# 2. Build and start. Only Frutti's own containers are touched.
cd "$RELEASE_DIR/deploy"
sudo -E docker compose --project-name frutti-staging --env-file "$ENV_FILE" -f compose.staging.yml build
sudo -E docker compose --project-name frutti-staging --env-file "$ENV_FILE" -f compose.staging.yml up -d --remove-orphans

# 3. Host nginx: install our site only if it changed, test, then reload. On a failed test, put back the old file.
if ! sudo cmp -s "$RELEASE_DIR/deploy/nginx-host-staging.conf" "$NGINX_SITE" 2>/dev/null; then
  sudo cp -a "$NGINX_SITE" "$NGINX_SITE.previous" 2>/dev/null || true
  sudo install -m 644 "$RELEASE_DIR/deploy/nginx-host-staging.conf" "$NGINX_SITE"
  sudo ln -sf "$NGINX_SITE" /etc/nginx/sites-enabled/frutti-staging
  if sudo nginx -t; then
    sudo systemctl reload nginx
  else
    echo "nginx test failed: restoring the previous Frutti site, other sites untouched" >&2
    if [ -f "$NGINX_SITE.previous" ]; then sudo mv "$NGINX_SITE.previous" "$NGINX_SITE"
    else sudo rm -f "$NGINX_SITE" /etc/nginx/sites-enabled/frutti-staging; fi
    exit 1
  fi
fi

# 4. Health, through the same path a browser uses.
for port in 8095 8096; do
  for _ in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:$port/api/v1/health" > /dev/null; then echo "port $port healthy"; break; fi
    sleep 2
  done
  curl -fsS "http://127.0.0.1:$port/api/v1/health" > /dev/null || { echo "port $port not healthy" >&2; exit 1; }
done

# 5. Demo logins (owner, driver) with the password from .env. Existing accounts are left as they are.
DEMO_PASSWORD="$(grep '^DEMO_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"
sudo -E docker compose --project-name frutti-staging --env-file "$ENV_FILE" -f compose.staging.yml \
  exec -T backend python manage.py seed_dev --password "$DEMO_PASSWORD"

# 6. Keep the last 3 releases and their images; remove only Frutti's older ones.
cd "$BASE/releases"
for old in $(ls -1t | tail -n +4); do
  rm -rf "$old"
  sudo docker image rm "frutti-backend:$old" "frutti-web:$old" > /dev/null 2>&1 || true
done

echo "Deployed $RELEASE: admin http://$PUBLIC_HOST:8095  driver http://$PUBLIC_HOST:8096"

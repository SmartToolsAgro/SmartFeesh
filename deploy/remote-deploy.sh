#!/usr/bin/env bash
# Runs ON the staging server, from an unpacked release: deploy/remote-deploy.sh <release-id>
# Called by deploy/deploy.sh. Starts the stack, installs the nginx site, checks health. Never seeds data.
set -euo pipefail

RELEASE="$1"
BASE="$HOME/frutti-staging"
RELEASE_DIR="$BASE/releases/$RELEASE"
ENV_FILE="$BASE/.env"
PUBLIC_HOST="${PUBLIC_HOST:-217.182.205.137}"
# One host name per app, so their login cookies stay apart (D-036). Must match nginx-host-staging.conf.
ADMIN_HOST="admin.${PUBLIC_HOST//./-}.sslip.io"
DRIVER_HOST="chauffeur.${PUBLIC_HOST//./-}.sslip.io"
NGINX_SITE=/etc/nginx/sites-available/frutti-staging

# 1. Secrets: created once on the server, never in the repository.
if [ ! -f "$ENV_FILE" ]; then
  echo "Creating $ENV_FILE with new random secrets"
  umask 077
  cat > "$ENV_FILE" <<EOF
POSTGRES_PASSWORD=$(openssl rand -hex 24)
DJANGO_SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n')
SENTRY_DSN=
SENTRY_DSN_FRONTEND=
EOF
fi
chmod 600 "$ENV_FILE"

# Host names are not secrets: written on every deploy, so a change here reaches servers set up earlier.
set_env() {
  if grep -q "^$1=" "$ENV_FILE"; then sed -i "s|^$1=.*|$1=$2|" "$ENV_FILE"; else echo "$1=$2" >> "$ENV_FILE"; fi
}
set_env DJANGO_ALLOWED_HOSTS "$ADMIN_HOST,$DRIVER_HOST"
set_env DJANGO_CSRF_TRUSTED_ORIGINS "http://$ADMIN_HOST:8095,http://$DRIVER_HOST:8096"
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
for site in "$ADMIN_HOST:8095" "$DRIVER_HOST:8096"; do
  port="${site##*:}"
  for _ in $(seq 1 30); do
    if curl -fsS -H "Host: $site" "http://127.0.0.1:$port/api/v1/health" > /dev/null 2>&1; then echo "$site healthy"; break; fi
    sleep 2
  done
  curl -fsS -H "Host: $site" "http://127.0.0.1:$port/api/v1/health" > /dev/null || { echo "$site not healthy" >&2; exit 1; }
done

# 5. Nightly backup (D-139): the script the debian user's crontab calls, and the public key it encrypts to.
#    The cron entry itself is installed once by hand (docs/runbook.md, "Backups").
install -d -m 700 "$BASE/bin"
install -m 755 "$RELEASE_DIR/deploy/backup.sh" "$BASE/bin/backup.sh"
install -m 644 "$RELEASE_DIR/deploy/backup-public-key.asc" "$BASE/backup-public-key.asc"

# 6. Keep the last 3 releases and their images; remove only Frutti's older ones.
cd "$BASE/releases"
for old in $(ls -1t | tail -n +4); do
  rm -rf "$old"
  sudo docker image rm "frutti-backend:$old" "frutti-web:$old" > /dev/null 2>&1 || true
done

echo "Deployed $RELEASE: admin http://$ADMIN_HOST:8095  driver http://$DRIVER_HOST:8096"

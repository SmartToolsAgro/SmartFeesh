#!/usr/bin/env bash
# Restores one backup made by deploy/backup.sh into a NEW, separate PostgreSQL 16 container (D-139). It never
# touches a running database: the new container, its network and its media volume are all named frutti-restore-*.
#
# Run it where the private key is (Git Bash on Windows works). The private key never goes to the server: the
# files are decrypted here and only the decrypted stream goes to Docker.
#   deploy/restore.sh <backup folder> <private key file>        restore, then print row counts
#   deploy/restore.sh --remove <frutti-restore-...>               remove a restore (container, network, volume)
# <backup folder> holds db.dump.gpg, media.tar.gz.gpg and manifest.txt (copied from ~/<project>/backups/<time>/).
#
# Settings (environment):
#   RESTORE_SSH=debian@217.182.205.137   run Docker on that host over SSH instead of on this machine
#   RESTORE_BACKEND_IMAGE=frutti-backend:<release>   also run the stock check (rebuild_on_hand --check) on the copy
set -euo pipefail

PG_IMAGE="postgres:16-alpine"

# Docker here, or on RESTORE_SSH. Arguments are quoted for the remote shell.
dock() {
  if [ -n "${RESTORE_SSH:-}" ]; then
    # shellcheck disable=SC2029 # expanding here is the point: the quoted command runs there
    ssh "$RESTORE_SSH" "docker $(printf '%q ' "$@")"
  else
    docker "$@"
  fi
}

if [ "${1:-}" = "--remove" ]; then
  NAME="${2:-}"
  [[ "$NAME" == frutti-restore-* ]] || { echo "usage: $0 --remove frutti-restore-<time>" >&2; exit 2; }
  dock rm -f "$NAME" > /dev/null || true
  dock volume rm "$NAME-media" > /dev/null || true
  dock network rm "$NAME" > /dev/null || true
  echo "Removed $NAME (container, network, volume $NAME-media)"
  exit 0
fi

[ $# -eq 2 ] || { echo "usage: $0 <backup folder> <private key file>" >&2; exit 2; }
SRC="$1"
KEY="$2"
for f in db.dump.gpg media.tar.gz.gpg; do [ -s "$SRC/$f" ] || { echo "missing $SRC/$f" >&2; exit 1; }; done
[ -s "$KEY" ] || { echo "missing private key $KEY" >&2; exit 1; }
if [ -f "$SRC/manifest.txt" ] && command -v sha256sum > /dev/null; then
  echo "Checking the files against manifest.txt"
  (cd "$SRC" && grep -E ' (db\.dump|media\.tar\.gz)\.gpg$' manifest.txt | sha256sum -c -)
fi

# The private key goes into a throwaway keyring, deleted at the end.
GNUPGHOME="$(mktemp -d)"
export GNUPGHOME
chmod 700 "$GNUPGHOME"
cleanup() {
  gpgconf --kill gpg-agent 2> /dev/null || true
  rm -rf "$GNUPGHOME"
}
trap cleanup EXIT
gpg --batch --quiet --import "$KEY"
decrypt() { gpg --quiet --decrypt "$1"; }

NAME="frutti-restore-$(date -u +%Y%m%dT%H%M%SZ)"
echo "Starting $NAME ($PG_IMAGE), on ${RESTORE_SSH:-this machine}"
dock network create "$NAME" > /dev/null
# No published port: reachable only from containers on its own network. Trust auth for the same reason.
dock run -d --name "$NAME" --network "$NAME" -e POSTGRES_USER=frutti -e POSTGRES_DB=frutti \
  -e POSTGRES_HOST_AUTH_METHOD=trust "$PG_IMAGE" > /dev/null
for _ in $(seq 1 60); do
  # The image's first start runs a temporary server; wait until the real one answers on the network.
  if dock exec "$NAME" pg_isready -h "$NAME" -U frutti -d frutti > /dev/null 2>&1; then break; fi
  sleep 1
done
dock exec "$NAME" pg_isready -h "$NAME" -U frutti -d frutti > /dev/null

echo "Restoring the database"
decrypt "$SRC/db.dump.gpg" \
  | dock exec -i "$NAME" pg_restore -U frutti -d frutti --no-owner --no-privileges --exit-on-error

echo "Restoring the media files into volume $NAME-media"
decrypt "$SRC/media.tar.gz.gpg" \
  | dock run --rm -i --network none -v "$NAME-media:/media" "$PG_IMAGE" tar -xzf - -C /media
echo "media files: $(dock run --rm --network none -v "$NAME-media:/media:ro" "$PG_IMAGE" find /media -type f | wc -l)"

# Exact row count of every table, sorted by name: compare with the same query on the live database.
echo "Row counts (table|rows):"
dock exec -i "$NAME" psql -U frutti -d frutti -At -v ON_ERROR_STOP=1 << 'SQL'
select table_name || '|' || (xpath('/row/c/text()',
  query_to_xml(format('select count(*) as c from %I.%I', table_schema, table_name), false, true, '')))[1]::text
from information_schema.tables where table_schema = 'public' and table_type = 'BASE TABLE' order by table_name;
SQL

if [ -n "${RESTORE_BACKEND_IMAGE:-}" ]; then
  echo "Stock check on the restored database ($RESTORE_BACKEND_IMAGE)"
  # Placeholder secret, host and cache: the check only reads the database.
  dock run --rm --network "$NAME" -e "DATABASE_URL=postgres://frutti@$NAME:5432/frutti" \
    -e DJANGO_SECRET_KEY=restore-check-only -e DJANGO_ALLOWED_HOSTS=localhost \
    -e DJANGO_CACHE_URL=redis://unused:6379/0 "$RESTORE_BACKEND_IMAGE" python manage.py rebuild_on_hand --check
fi

echo "Restored into $NAME (database frutti, user frutti) and volume $NAME-media."
echo "Look at it:  ${RESTORE_SSH:+ssh $RESTORE_SSH }docker exec -it $NAME psql -U frutti -d frutti"
echo "Remove it:   $0 --remove $NAME"

# Runbook

How to operate the running system. Keep it short and true; update it when a procedure changes.

## Staging (OVH VPS 217.182.205.137)

| What | Where |
|---|---|
| Admin app | http://admin.217-182-205-137.sslip.io:8095 |
| Driver app | http://chauffeur.217-182-205-137.sslip.io:8096 |
| Demo logins | `owner`, `driver`; password in `DEMO_PASSWORD` of `~/frutti-staging/.env` on the server |
| Server login | `ssh debian@217.182.205.137` (key `~/.ssh/id_ed25519_erp_prod` on Mahmoud's machine) |

**Shared server.** The VPS also runs other clients' production sites (Sonalim, TRT, dossipv, smartgreen)
behind one nginx. Frutti only owns: the Docker project `frutti-staging` (containers `frutti-staging-*`,
volumes `frutti-staging_pgdata` and `frutti-staging_media` (product photos)), the folder `~/frutti-staging`, and the nginx site
`/etc/nginx/sites-available/frutti-staging` (ports 8095 and 8096; the bare address redirects to the app's host name, D-036),
and the backup line of the `debian` user's crontab (see "Backups"). Never edit, prune or restart anything
else there. Always run `sudo nginx -t` before reloading nginx.

### Deploy

From a clone with SSH access: commit, then `make deploy-staging` (or `bash deploy/deploy.sh`). It sends
the committed code (never uncommitted changes) to `~/frutti-staging/releases/<time>-<commit>`, builds the
images on the server, starts the stack (migrations run at backend start), installs the nginx site if it
changed (test, reload, roll back on failure), checks health on both ports and seeds the demo logins.
The last 3 releases and their images are kept.

CI deploys automatically after every green push to `main`, once these GitHub secrets exist
(Settings → Secrets and variables → Actions):

- `STAGING_KNOWN_HOSTS`: output of `ssh-keyscan -t ed25519 217.182.205.137`.
- `STAGING_SSH_KEY`: a private key **made only for this** (`ssh-keygen -t ed25519 -f frutti_ci_deploy -N ""`),
  whose public key is added to `~debian/.ssh/authorized_keys` on the server.

**Done on 2026-10-10.** The CI key (`frutti-ci-deploy`) is in `~debian/.ssh/authorized_keys` with the
`restrict` option (no tunnels, no terminal); the previous file is kept as `authorized_keys.bak-before-frutti-ci`.
To revoke it, delete that line and the GitHub secret. Limit to keep in mind: the deploy runs uploaded code
with sudo, so whoever holds the secret is effectively root on a server shared with other clients. The real
fix is a separate server, or a server that pulls only code already on `main` from GitHub.

### Look at it

```bash
ssh debian@217.182.205.137
sudo docker ps --filter name=frutti-staging
sudo docker logs --tail 100 frutti-staging-backend-1
cd ~/frutti-staging/releases/$(ls -1t ~/frutti-staging/releases | head -1)/deploy
sudo docker compose --project-name frutti-staging --env-file ~/frutti-staging/.env -f compose.staging.yml exec backend python manage.py shell
```

### Stock check

Every night just after 03:00 UTC the `frutti-staging-nightly-1` container compares the stock on hand
with the movement ledger (D-038); see `sudo docker logs frutti-staging-nightly-1`. A difference is
logged as an error. After understanding it, repair from the ledger with
`... exec backend python manage.py rebuild_on_hand` (same folder as above); `--check` only reports.

### Roll back

Redeploy an older commit: `git checkout <commit> && make deploy-staging`, then come back to your branch.
Migrations are not reversed automatically.

### Secrets

`~/frutti-staging/.env` (mode 600) is created on the first deploy with random values: database password,
Django secret key, demo password, allowed host and CSRF origins, and an empty `SENTRY_DSN`. Edit it on the
server, then redeploy. It is never in the repository. Deleting it would change the database password and
break the existing database.

### Sentry

The backend reports errors to Sentry when `SENTRY_DSN` is set in `.env`. No Sentry project exists yet.

### Backups (D-139)

**What runs.** Every night at 02:30 UTC (03:30 in Tunisia), from the `debian` user's crontab (`crontab -l`):

```
30 2 * * * $HOME/frutti-staging/bin/backup.sh frutti-staging >> $HOME/frutti-staging/backup.log 2>&1
```

`deploy/backup.sh` (installed to `~/frutti-staging/bin/` on every deploy, with the public key
`deploy/backup-public-key.asc` → `~/frutti-staging/backup-public-key.asc`) writes
`~/frutti-staging/backups/<UTC time>/` with:

- `db.dump.gpg`: `pg_dump --format=custom` of the database, from the db container;
- `media.tar.gz.gpg`: the volume `frutti-staging_media` (product photos, logo, avatars, expense receipts, loss photos,
  payment files, generated PDFs);
- `manifest.txt` (not secret): time, key fingerprint, PostgreSQL version, SHA-256 of both files.

Both files are encrypted with gpg to the backup public key while they stream: nothing readable is written to disk
and the server cannot read its own backups. Folders older than 30 days are deleted. Each run adds one line to
`~/frutti-staging/backup.log`: `... BACKUP OK frutti-staging <time> db=541KB media=916KB duration=2s kept=.. removed=..
offsite=..` or `... BACKUP FAILED frutti-staging <time>: <reason>` (exit code 1). To run one by hand:
`~/frutti-staging/bin/backup.sh`. Not backed up: `.env` (recreated by a deploy; keep its off-site credentials in the
password manager), Redis (holds nothing), code, images and nginx site (in git).

**The key.** Public key fingerprint `8C69 CE47 FE72 6683 B373 2261 C5D2 D8A9 82D4 3BCF` (RSA 4096, encryption subkey
`D0FF5AC57C467C81159A72D06A497EF2DC5C2F40`). The **private key** is the file `frutti-backup-PRIVATE-key.asc`, made on
2026-10-14 on Mahmoud's machine, in `C:\Users\ITDT\frutti-backup-key\`, with no passphrase. To do: the owner moves it
into a password manager and onto a USB key, then it is deleted from that folder. It is never on the server or in git.
**Without it no backup can be read.**

**Off-site copy (still to set up by the owner).** When `BACKUP_S3_BUCKET` is set in `~/frutti-staging/.env`, each backup
is copied with rclone (container `rclone/rclone:1.68.2`) to `<bucket>/<prefix>/<time>/`. The variables (empty lines
are already in `.env`):

| Variable | Example (OVHcloud Object Storage) |
|---|---|
| `BACKUP_S3_ENDPOINT` | `https://s3.gra.io.cloud.ovh.net` |
| `BACKUP_S3_REGION` | `gra` |
| `BACKUP_S3_BUCKET` | `frutti-backups` (empty = local copy only, said in the log line) |
| `BACKUP_S3_PREFIX` | `frutti-staging` (the default) |
| `BACKUP_S3_ACCESS_KEY_ID`, `BACKUP_S3_SECRET_ACCESS_KEY` | keys of a user allowed to write that bucket |

Create the bucket yourself (the script does not), in another provider or region than this VPS, with a lifecycle rule
that deletes objects after 30 to 60 days: the script never deletes anything off-site, so give its keys write access
only. Then run `~/frutti-staging/bin/backup.sh` once and check the line says `offsite=<bucket>/...`. Tested on
2026-10-14 against a throwaway S3 server: upload OK; an unreachable endpoint fails in about 20 s with a clear line.

**Restore drill (2026-10-14, done for real).** From a clone, on the machine that holds the private key (Git Bash):

```bash
scp -r debian@217.182.205.137:frutti-staging/backups/20261014T122410Z ./drill/
RESTORE_SSH=debian@217.182.205.137 RESTORE_BACKEND_IMAGE=frutti-backend:20261014113217-a398d51 \
  bash deploy/restore.sh ./drill/20261014T122410Z ~/frutti-backup-key/frutti-backup-PRIVATE-key.asc
bash deploy/restore.sh --remove frutti-restore-20261014T122502Z   # with the same RESTORE_SSH
```

`deploy/restore.sh` checks the SHA-256 against the manifest, decrypts **on this machine** (the key never leaves it),
streams the dump into a new throwaway container `frutti-restore-<time>` (`postgres:16-alpine`, own network, no port),
the media into a new volume `frutti-restore-<time>-media`, prints the exact row count of every table and runs
`rebuild_on_hand --check` with the backend image. It never touches the running database. Without `RESTORE_SSH`
it uses the local Docker. Result, against the live database counted right after the backup:

| Check | Live | Restored |
|---|---|---|
| Tables, all compared row by row count | 99 (1 551 rows) | 99, identical |
| `sales_sale` / `inventory_stockmovement` / `inventory_stockonhand` | 18 / 76 / 29 | 18 / 76 / 29 |
| `catalog_product` / `core_user` / `sales_invoice` / `expenses_expense` | 50 / 3 / 8 / 17 | 50 / 3 / 8 / 17 |
| Media files | 24 | 24 |
| `rebuild_on_hand --check` | | "0 difference(s) found" |

Backup took 2 s (db 541 KB, media 916 KB encrypted); the whole restore 45 s. Afterwards the container, network and
volume were removed. Do this again every few months and after a large change to the data model.

**Emergency restore (the live data is lost or broken).** Not drilled yet in place; the drill above proves the files.

1. Take a backup of what is there now, if the server still runs (`~/frutti-staging/bin/backup.sh`), so the
   restore can be undone. Pick the backup to restore (`~/frutti-staging/backups/`, or the off-site bucket) and copy it
   to the machine with the private key. Check it first with `restore.sh` as in the drill.
2. On a new server, deploy first (`make deploy-staging`): it creates `.env`, an empty database and the volumes.
   Put the `BACKUP_S3_*` lines back into `.env`. Then stop the app, keep the database running:
   ```bash
   cd ~/frutti-staging/releases/$(ls -1t ~/frutti-staging/releases | head -1)/deploy
   export RELEASE=$(ls -1t ~/frutti-staging/releases | head -1)
   sudo -E docker compose --project-name frutti-staging --env-file ~/frutti-staging/.env -f compose.staging.yml stop backend worker nightly web
   docker exec frutti-staging-db-1 dropdb -U frutti --force frutti
   docker exec frutti-staging-db-1 createdb -U frutti frutti
   ```
3. From the machine with the key (Git Bash, in the backup folder):
   ```bash
   gpg --import frutti-backup-PRIVATE-key.asc   # once; or use a throwaway GNUPGHOME as restore.sh does
   gpg --decrypt db.dump.gpg | ssh debian@<server> docker exec -i frutti-staging-db-1 pg_restore -U frutti -d frutti --no-owner --exit-on-error
   gpg --decrypt media.tar.gz.gpg | ssh debian@<server> docker run --rm -i -v frutti-staging_media:/media postgres:16-alpine tar -xzf - -C /media
   ```
4. Start again (`... compose.staging.yml up -d`, same folder and `RELEASE`), check both health URLs, run
   `... exec backend python manage.py rebuild_on_hand --check`, and log in. A new `.env` means a new secret key: everyone
   logs in again.

## Production

Not set up yet (P4-T02). It needs a domain and HTTPS: staging runs on plain HTTP (D-027).

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
`/etc/nginx/sites-available/frutti-staging` (ports 8095 and 8096; the bare address redirects to the app's host name, D-036). Never edit, prune or restart anything
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
Every `--check` records its result, which the uptime watch reads (see "Monitoring").

### Roll back

Redeploy an older commit: `git checkout <commit> && make deploy-staging`, then come back to your branch.
Migrations are not reversed automatically.

### Secrets

`~/frutti-staging/.env` (mode 600) is created on the first deploy with random values: database password,
Django secret key, demo password, allowed host and CSRF origins, and an empty `SENTRY_DSN`. Edit it on the
server, then redeploy. It is never in the repository. Deleting it would change the database password and
break the existing database.

### Monitoring

What is watched (D-140):

| What | How | Alert |
|---|---|---|
| Admin app, driver app, API | `.github/workflows/uptime.yml`, every 15 minutes | the run fails, GitHub e-mails |
| Nightly stock check | `/api/v1/health/stock-check` read by the same workflow | same |
| Errors in the API and both apps | Sentry, once a DSN is set | Sentry e-mails |

**How the e-mail reaches the owner.** A failed scheduled run is e-mailed by GitHub to the account that owns the
schedule: the one that merged the workflow to `main`, or that last changed its `cron` line (if the workflow is
turned off and on again, the one that turned it on). That account must keep e-mail on for Actions (GitHub →
Settings → Notifications → Actions: e-mail, failed workflows only). While something stays down, every run (every
15 minutes) e-mails again: fix it, or pause the watch with `gh workflow disable uptime.yml` (and `enable` after).
GitHub **turns scheduled workflows off after 60 days without activity in the repository**; it e-mails a warning
first. To turn it back on: Actions → Uptime → "Enable workflow", or `gh workflow enable uptime.yml`. Run it by hand
any time: Actions → Uptime → "Run workflow", or `gh workflow run uptime.yml`.

**When the alert fires.** Open the failed run (Actions → Uptime): each failed check is an error line.

- *Admin app / Driver app / API is down:* `curl -sS http://admin.217-182-205-137.sslip.io:8095/api/v1/health` from
  any machine. If it does not answer, log in (see "Look at it"): `sudo docker ps --filter name=frutti-staging`
  (a container restarting?), `sudo docker logs --tail 100 frutti-staging-backend-1`, then
  `sudo systemctl status nginx` (read only: nginx is shared, never restart it for us; `sudo nginx -t` before any
  reload). A failed deploy shows in `gh run list --workflow ci.yml`; roll back as below. A single failed run that
  passes on the next one is usually a network blip: watch the next run.
- *Nightly stock check failed:* the check found a difference between the stock on hand and the ledger (or
  crashed). Read `sudo docker logs frutti-staging-nightly-1` for the lines, understand them (see "Stock check"),
  repair with `rebuild_on_hand`, then run `rebuild_on_hand --check` once: that run clears the state.
- *Nightly stock check late or never:* no check for 26 hours. The `frutti-staging-nightly-1` container is probably
  stopped or looping on an error: `sudo docker ps -a --filter name=frutti-staging-nightly` and its logs. A redeploy
  restarts it, and it checks once at start.

**Sentry (errors).** No Sentry project exists yet; until there is one, nothing is sent. To turn it on:

1. Create a free Sentry project (platform "React" for the two apps; one more, "Django", for the API, or use the
   same project for all three: every report carries the tag `app` = `api`, `admin` or `truck`).
2. On the server, in `~/frutti-staging/.env`: `SENTRY_DSN=<DSN of the API project>` and
   `SENTRY_DSN_FRONTEND=<DSN of the apps project>`.
3. Redeploy. The apps read their DSN **when the image is built**, so a change needs a redeploy, not only a restart.

Reports carry the release (`<time>-<commit>` of the deploy) and the environment (`staging`), and name a user by id
only. Variables: `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_RELEASE` (API, set by the compose file from the
deploy), `SENTRY_DSN_FRONTEND` (build argument, becomes `VITE_SENTRY_DSN`; `VITE_SENTRY_ENVIRONMENT` and
`VITE_RELEASE` likewise). A local `pnpm build` with `VITE_SENTRY_DSN` set builds the apps with Sentry on.

## Production

Not set up yet (P4-T02). It needs a domain and HTTPS: staging runs on plain HTTP (D-027).

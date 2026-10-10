# Runbook

How to operate the running system. Keep it short and true; update it when a procedure changes.

## Staging (OVH VPS 217.182.205.137)

| What | Where |
|---|---|
| Admin app | http://217.182.205.137:8095 |
| Driver app | http://217.182.205.137:8096 |
| Demo logins | `owner`, `driver`; password in `DEMO_PASSWORD` of `~/frutti-staging/.env` on the server |
| Server login | `ssh debian@217.182.205.137` (key `~/.ssh/id_ed25519_erp_prod` on Mahmoud's machine) |

**Shared server.** The VPS also runs other clients' production sites (Sonalim, TRT, dossipv, smartgreen)
behind one nginx. Frutti only owns: the Docker project `frutti-staging` (containers `frutti-staging-*`,
volumes `frutti-staging_pgdata` and `frutti-staging_media` (product photos)), the folder `~/frutti-staging`, and the nginx site
`/etc/nginx/sites-available/frutti-staging` (ports 8095 and 8096). Never edit, prune or restart anything
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

Recommended before adding that key: create a separate `frutti-deploy` user allowed to run only Docker and
the Frutti nginx steps, because `debian` has full sudo on a server shared with other clients.

### Look at it

```bash
ssh debian@217.182.205.137
sudo docker ps --filter name=frutti-staging
sudo docker logs --tail 100 frutti-staging-backend-1
cd ~/frutti-staging/releases/$(ls -1t ~/frutti-staging/releases | head -1)/deploy
sudo docker compose --project-name frutti-staging --env-file ~/frutti-staging/.env -f compose.staging.yml exec backend python manage.py shell
```

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

## Production

Not set up yet (P4-T02). It needs a domain and HTTPS: staging runs on plain HTTP (D-027).

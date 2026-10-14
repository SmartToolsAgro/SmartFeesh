# Phase 4 · Go-live for daily operations → Milestone A

**Goal:** the client stops using notebooks/Excel for stock, sales and customer debts.
**Done when:** production is live with real opening data, backups are tested, and every user is trained.
**Depends on:** Phases 1–3. **Questions:** Q15 (where existing data lives).

---

### P4-T01 · Data import · M
Today everything is in paper notebooks (Q15), so there is no file to convert.
- [x] (D-112, slice 1) Excel templates for products, suppliers, customers, employees. The client's team types the
      notebooks into them (human: plan the time), then import scripts load them.
- [x] Opening balances (D-112, slices 2 and 3): customer debts, supplier debts, opening stock per location and batch.
- [x] (D-112, slice 1) Dry-run mode with a report; the owner signs off the opening numbers.
- [ ] The stand-in data of `docs/spec/sample/` never reaches production.

### P4-T02 · Production environment · M
- [ ] Production VPS at OVH (D-017, D-019), Postgres, object storage, HTTPS, domain.
- [ ] Deploy from git tags; database migrations run safely.

### P4-T03 · Backups and restore · S
- [x] (D-139) Daily encrypted DB backup + file storage backup, kept 30 days: `deploy/backup.sh` from the `debian`
      crontab at 02:30 UTC on staging, gpg to a public key, `~/frutti-staging/backups/`.
- [ ] Stored off-site: built and tested (rclone to any S3 bucket, `BACKUP_S3_*` in `.env`), **waiting on the owner** to
      create the bucket and put its credentials in `~/frutti-staging/.env`. Also: move the private key off Mahmoud's
      machine (runbook, "Backups").
- [x] (D-139) Restore drill done once and written down in `docs/runbook.md` (2026-10-14: 99 tables identical, stock
      check clean). `deploy/restore.sh` restores into a throwaway container.
- [ ] Production (P4-T02): same cron line with the production project name once it exists; the in-place emergency
      restore (runbook) is written but not drilled.

### P4-T04 · Monitoring · S
- [x] Sentry (backend + both apps), uptime check, alert on failed nightly stock consistency check (D-140): Sentry
      wired in the API and both apps, off until a DSN is set; the nightly check records its run
      (`/api/v1/health/stock-check`); `.github/workflows/uptime.yml` checks staging every 15 minutes and fails,
      so GitHub e-mails. Runbook "Monitoring".
  - Still to do (human): create the Sentry project and put `SENTRY_DSN` / `SENTRY_DSN_FRONTEND` in the server's
    `.env`, then redeploy; check that the GitHub account owning the schedule gets Actions e-mails; watch the first
    scheduled runs on `main`. For production (P4-T02): set `UPTIME_ADMIN_URL` / `UPTIME_DRIVER_URL` and its own
    `SENTRY_ENVIRONMENT`.

### P4-T05 · Security review · S
- [x] Run the `security-review` skill; check permissions per role, CSRF, rate limits, file upload limits.
  - API review done (D-108): roles per route, tenancy, uploads, throttles, CSRF and cookies, with tests in
    `apps/core/tests/test_api_security.py`.
  - Second review 2026-10-14 (D-141): everything added since D-108, the front ends, sales and invoices, users and
    sessions, production settings and dependencies. 2 medium and 4 low holes closed with tests.
  - Still open: the owner's decision on how far back a driver's late sale may be dated (D-141); restrict
    `/django-admin/` by address in the production nginx; `DJANGO_NUM_PROXIES` and the health check under HTTPS in the
    production deploy; tie the driver app's offline queue to the driver who filled it (P3-T07).

### P4-T06 · Training and support · human · S
- [ ] Short guides with screenshots: French for the owner, French and Arabic for drivers (Q14).
      (Text guides in French written: `docs/guides/guide-proprietaire.md`, `docs/guides/guide-chauffeur.md`. Still to do: screenshots,
      the Arabic driver guide, and a walk-through with the owner and a driver.)
      Support contact and process.

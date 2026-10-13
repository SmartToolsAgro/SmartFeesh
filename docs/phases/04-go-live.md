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
- [ ] Daily encrypted DB backup + file storage backup, kept 30 days, stored off-site.
- [ ] Restore drill done once and written down in `docs/runbook.md`.

### P4-T04 · Monitoring · S
- [ ] Sentry (backend + both apps), uptime check, alert on failed nightly stock consistency check.

### P4-T05 · Security review · S
- [ ] Run the `security-review` skill; check permissions per role, CSRF, rate limits, file upload limits.
  - API review done (D-108): roles per route, tenancy, uploads, throttles, CSRF and cookies, with tests in
    `apps/core/tests/test_api_security.py`. Still to run: the `security-review` skill on the front ends and the sales
    and invoices views (after PR #55).

### P4-T06 · Training and support · human · S
- [ ] Short guides with screenshots: French for the owner, French and Arabic for drivers (Q14).
      (Text guides in French written: `docs/guides/guide-proprietaire.md`, `docs/guides/guide-chauffeur.md`. Still to do: screenshots,
      the Arabic driver guide, and a walk-through with the owner and a driver.)
      Support contact and process.

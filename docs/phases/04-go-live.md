# Phase 4 · Go-live for daily operations → Milestone A

**Goal:** the client stops using notebooks/Excel for stock, sales and customer debts.
**Done when:** production is live with real opening data, backups are tested, and every user is trained.
**Depends on:** Phases 1–3. **Questions:** Q15 (where existing data lives).

---

### P4-T01 · Data import · M
Today everything is in paper notebooks (Q15), so there is no file to convert.
- [ ] Excel templates for products, suppliers, customers, employees. The client's team types the
      notebooks into them (human: plan the time), then import scripts load them.
- [ ] Opening balances: customer debts, supplier debts, opening stock per location and batch.
- [ ] Dry-run mode with a report; the owner signs off the opening numbers.
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

### P4-T06 · Training and support · human · S
- [ ] Short guides with screenshots: French for the owner, French and Arabic for drivers (Q14).
      Support contact and process.

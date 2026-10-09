# Phase 8 · Scale & integrations (backlog)

Not committed. Pick items when there is a real need, then turn the item into a detailed task list.
The groundwork for each is already in the architecture (ARCHITECTURE §5).

| Item | Trigger | Groundwork already in place |
|---|---|---|
| Export to the accountant's software | Accountant asks for it | Immutable documents, audit log |
| Arabic for the admin app | Owner or staff ask | i18n + RTL from P0-T08, driver app done in P3-T09 |
| Route planning, customer visits, pre-orders | Client grows deliveries | Customers + driver days |
| Customer portal (order online, see invoices) | Large customers ask | API-first, roles |
| SMS / WhatsApp notifications | Overdue customers, order confirmations | Celery jobs |
| Read replica / analytics database | Reports get slow | Reporting isolated in `reporting` app |
| Extract a module into its own service | One module needs separate scaling or team | Service-layer boundaries + import-linter |

**Moved into committed phases (2026-10-10):** Arabic for drivers → P3-T09; Bluetooth receipt printer and
the possible native wrapper → P3-T10.

## TTN / El Fatoora e-invoicing (on hold, D-016)

Q5 says e-invoicing is required now, but the decision on 2026-10-10 is not to build it for now. Until it
is built the app issues PDF invoices only. Q18 (enrolment, certificate, documentation) must be answered
when this starts. Task list, kept ready:

- [ ] **Discovery (human + agent):** get TTN's current technical specification, a test account and the
      signing certificate; write the findings in `docs/spec/ttn.md`. Nothing below is built before that.
- [ ] Generate the electronic invoice file in the format TTN requires, from the immutable invoice.
- [ ] Sign it and send it to TTN from a Celery job; store the signed file and TTN's answer.
- [ ] Invoice status: not sent, sent, accepted, rejected (with reason); retries; admin follow-up screen.
- [ ] Whatever TTN returns for the printed copy appears on the invoice PDF (P2-T08).
- [ ] Credit notes go through the same path. Credentials are per organization, never in the repo.
- [ ] Decide what a driver hands over when the truck is offline and TTN has not yet accepted the invoice.

## Multi-company (confirmed goal, Q17)

The owner wants to sell the software to other distributors. Not scheduled yet: decide the timing with the
owner after Milestone B. Coarse list, to detail when it starts:

- Organization onboarding: create a company, its first owner and its settings (tax, numbering, logo,
  languages).
- Isolation audit: automated tests that no query, file, PDF or background job crosses organizations.
- Per-organization configuration instead of constants: units, expense categories, TTN credentials.
- Platform administration: list companies, suspend one, support access with audit.
- Subscription and billing, terms of use, data export when a customer leaves.
- Deployment model: one shared instance or one per customer (record in DECISIONS).

Until then every phase keeps one rule: no Frutti-specific value is hard-coded; it goes in organization
settings.

# Phase 8 · Scale & integrations (backlog)

Not committed. Pick items when there is a real need, then turn the item into a detailed task list.
The groundwork for each is already in the architecture (ARCHITECTURE §5).

| Item | Trigger | Groundwork already in place |
|---|---|---|
| TTN / El Fatoora e-invoicing | Q5 says it is mandatory (then move it earlier) | Invoice hook in P2-T05 |
| Export to the accountant's software | Accountant asks for it | Immutable documents, audit log |
| Arabic translation | Q14, or drivers ask | i18n + RTL from P0-T08 |
| Native driver app (Capacitor), Bluetooth receipt printer | Q13 | Separate truck app, PWA |
| Route planning, customer visits, pre-orders | Client grows deliveries | Customers + driver days |
| Customer portal (order online, see invoices) | Large customers ask | API-first, roles |
| SMS / WhatsApp notifications | Overdue customers, order confirmations | Celery jobs |
| Multi-company (sell the software to other distributors) | Q17 | `organization` FK everywhere |
| Read replica / analytics database | Reports get slow | Reporting isolated in `reporting` app |
| Extract a module into its own service | One module needs separate scaling or team | Service-layer boundaries + import-linter |

**Seafood Distribution ERP — Complete Conversation Extraction & Project Specification**

*Prepared from the discussion and the Facebook page screenshots provided in this chat*

# Document purpose and scope

This document consolidates the requirements, ideas, examples, workflows, calculations, open questions, and technical recommendations discussed in this conversation. It is intended as a working project brief, not as a verbatim word-for-word transcript of every assistant response. The user's requirements and the key content from the brainstorming are retained and organized so that nothing material from this project discussion is lost.

# 1. Business context captured from the screenshots

The screenshots show a Facebook business page with the following visible information:

- Business name: Frutti Del Mare.

- Description: “Fruits de mer ultra-frais”; “Qualité garantie”; “Fraîcheur de la mer, saveurs dans l’assiette.”

- Business category shown: Fish market.

- Phone number shown: 29 676 171.

- Address shown: RTE TUNIS KM 7, AV MONGI SLIM, Sakiet ez Zit, Tunisia, 3021.

- Visible product packaging includes seafood products such as Crevette Royale and Symphonie Marine. This is only what is visible in the supplied screenshots; the full product catalogue must be confirmed with the client.

These details were read from user-provided screenshots and have not been independently verified.

# 2. User's original project request

User message (verbatim):

> I would like to build an application for a client how sel seafood  
> He would like to have (devi, client, fornisseur, stock( stock in frigo and stock in camion)  
> Facturisation produit , charge  
> Some times fourniseur start investigating with him and he will get back percentage on win of the product that selled together(thus is the big point)  
> Also i would like yo have 2 user vue 1 for the admin and the other for the worker on camion  
> Brain storme the idea with me and reorgaise the idea in my head

# 3. Core product vision

Build a specialized seafood distribution and sales management ERP for Frutti Del Mare. It should not be only an invoicing application. It must connect purchasing, supplier/customer management, inventory across the refrigerator and trucks, mobile sales, expenses, worker salaries, monthly financial closing, and supplier profit-sharing.

- Trace every kilogram from supplier receipt to refrigerator, truck transfer, sale, return, loss, or spoilage.

- Every validated transaction should update the related stock and financial records automatically.

- Provide two different user experiences: an administrative management view and a simple mobile-first truck-worker view.

- The distinctive/high-value feature is monthly calculation of supplier profit shares after eligible business expenses have been accounted for.

- Use configurable rules because suppliers may have different agreements.

# 4. Actors and permissions

| Actor                               | Main responsibilities / access                                                                                                                                            |
|-------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Admin / owner                       | Manage products, suppliers, customers, purchases, sales, stock, expenses, salaries, partnerships, profit calculations, month closing, reports, settings, and permissions. |
| Truck worker / driver / salesperson | View assigned truck stock; record sales, customer payments, approved expenses, product losses, returns, and end-of-day cash/stock reconciliation.                         |
| Supplier                            | Supplies seafood and may be an ordinary vendor, consignor, commission partner, or investment/profit-sharing partner.                                                      |
| Customer                            | Purchases products; may pay immediately or on credit.                                                                                                                     |
| Business partner / investor         | May contribute capital or participate under a contract that defines the profit basis and share.                                                                           |

The worker must not automatically access company-wide profitability, other trucks, supplier investment terms, other workers' details, or administrative settings. Permissions must be enforced by the backend, not only by hiding interface elements.

# 5. Main application modules

## 5.1 Dashboard

- Today's and monthly sales, gross profit, operating profit, expenses, cash collected, and unpaid customer balances.

- Amounts owed to suppliers and unsettled supplier/partner profit.

- Stock value and quantity in refrigerator and each truck.

- Sales and profitability by product, truck, worker, customer, supplier, and period.

- Clearly distinguish revenue, gross profit, net operating profit, cash collected, accounts receivable, and amounts payable.

## 5.2 Products and inventory

- Product catalogue: name, reference, category, purchase unit, sale unit, cost, price, minimum stock, storage conditions, and traceability requirements.

- Potential example products from brainstorming: Crevette Royale, peeled shrimp, fish, squid, octopus, and mixed seafood. Confirm actual catalogue with client.

- Separate stock locations: refrigerator/cold room and each individual truck.

- Stock movements include receipts, transfers, sales, customer returns, supplier returns, spoilage, damaged goods, and inventory adjustments.

- Batch/lot tracking: supplier, purchase reference, receipt date, quantity, unit cost, expiry/use-by data where relevant, and associated partnership.

- Record actual accepted weight versus ordered/invoiced weight.

- Stock transfers are not sales. They decrease one location and increase another, with date, user, quantity, source, destination, and validation.

- Stock quantity should be derived from an auditable movement ledger, with controlled stock counts and adjustments rather than casual editing of quantity fields.

- Use inventory valuation and cost-of-goods-sold calculations so unsold stock at month-end is not automatically treated as an expense.

## 5.3 Suppliers and purchases

- Supplier profile, contact information, products, purchase history, outstanding balance, payment history, linked agreements, investments, and settlements.

- Suggested workflow: purchase order → receipt of goods → supplier invoice → payment.

- Record ordered quantity, actual accepted quantity, purchase cost, invoice, due date, and payments.

- A supplier invoice/liability and a payment must be separate records.

- Do not automatically treat supplier investment capital as an ordinary supplier invoice; distinguish capital contributions, trade payables, and profit settlements.

## 5.4 Customers, sales, and invoicing

- Customer types may include restaurants, hotels, fish shops, supermarkets, wholesalers, and individuals.

- Customer profile: contact details, sales history, invoices, payment history, balance, credit limit, and overdue debt.

- Support sales from the refrigerator and sales from a truck.

- Sales record: customer, product/batch, quantity, price, discount, taxes where applicable, total, payment method, invoice/receipt, and stock location.

- Example: 5 kg at 35 DT/kg = 175 DT sale. If the customer pays 100 DT, record 100 DT received and 75 DT outstanding.

- Preserve the actual price, cost, tax, and agreement rules used on historical transactions.

- Support customer-specific prices and configurable minimum-price warnings.

- Configure invoicing and tax treatment for applicable Tunisian legal requirements, including any electronic-invoicing obligations that apply to the client.

## 5.5 Truck worker mobile view

- Mobile-first responsive web application / PWA.

- Worker actions: start day, view assigned stock, record sale, select/create customer if authorized, record payment, record expense, report damaged/spoiled product, return products, and close day.

- At sale time, automatically update truck stock, sale totals, payment received, customer balance, and links to product batch/partnership.

- Daily closing captures sales, cash, electronic/bank payments, credit sales, remaining stock, returns, losses, expenses, and cash handed to owner.

- Compare expected cash with declared cash and flag differences for review without presuming misconduct.

- Consider offline support where mobile connectivity is unreliable. It requires robust sync, duplicate prevention, and handling of concurrent stock updates.

- Potential future additions: route planning, customer visits, delivery orders, and preorders if the business needs them.

## 5.6 Expenses

The user explicitly identified expenses as a required part of the application. Expense categories discussed:

| Category               | Examples                                                                                                                    |
|------------------------|-----------------------------------------------------------------------------------------------------------------------------|
| Personnel / payroll    | Worker salaries, driver salaries, bonuses, overtime, employer social contributions and other employment costs.              |
| Transportation         | Fuel, truck maintenance, insurance, road/toll/parking costs, and truck depreciation.                                        |
| Cold storage           | Electricity, refrigerator/cold-room rent, refrigeration maintenance, equipment depreciation, cleaning and storage supplies. |
| Seafood handling       | Ice, packaging, handling, spoilage, damaged product, and other product-related costs.                                       |
| General administration | Telephone, internet, accounting fees, office expenses, bank fees and miscellaneous operating costs.                         |
| Financial costs        | Loan interest and other relevant financing costs; distinguish interest from loan principal repayments.                      |

- Each expense should have date, category, amount, payment method, person recording it, supporting receipt/document, approval status, and optional truck, location, product batch, or business-wide allocation.

- Expenses may be entered by a truck worker but validated by the administrator.

- Prevent duplicate counting and maintain an audit trail.

- Expense allocation may be based on actual usage, truck activity, sales, gross profit, storage usage, or a configured rule.

## 5.7 Employee management and salaries — explicit user addition

User message (verbatim): “Also do not miss salary of workers”

Worker salaries must be included in monthly expenses before calculating the applicable net profit and supplier shares. Create a dedicated Human Resources & Payroll / Gestion du personnel et des salaires module.

- Employee profile: name/contact details, job position, salary, employment status, assigned truck if relevant, bonuses, overtime, applicable deductions and employer contributions.

- Track monthly salary amount, payment status, payment date/method, and unpaid salaries.

- For an initial version, support salary tracking and payment recording; add more advanced payroll calculations after confirming local payroll requirements.

- Possible allocation: driver salary to truck activity/delivery workload; warehouse salary to storage activity; salesperson salary to sales handled; general administration salaries as general expenses; sales bonuses to related sales if contractually appropriate.

- Do not double-count salary costs and payments. A salary expense and the cash payment settling that expense are different accounting events.

# 6. Supplier arrangements and profit sharing

The user identified supplier investment/profit sharing as the most important feature. The later clarification is that supplier profit is calculated at the end of the month, because the business must first calculate full expenses, including fuel, truck depreciation, drivers, electricity, refrigerator costs, and worker salaries.

## 6.1 Arrangement types to support

| Arrangement                  | Meaning                                                                                                                |
|------------------------------|------------------------------------------------------------------------------------------------------------------------|
| Ordinary purchase            | The business buys goods from a supplier at an agreed price; subsequent sales profit generally belongs to the business. |
| Consignment / vente en dépôt | Supplier provides products for sale under agreed ownership, settlement, and risk rules.                                |
| Sales commission             | The business earns a commission based on sales or another agreed basis.                                                |
| Profit sharing               | Supplier receives a contractual percentage of an agreed profit basis.                                                  |
| Joint investment             | Supplier and owner contribute capital; capital recovery and profit allocation are defined separately.                  |
| Flexible agreement           | Different suppliers or batches may use different rules.                                                                |

## 6.2 Agreement fields

- Supplier/partner, agreement type, start/end dates, products/batches covered, capital contributions, capital recovery rules, profit percentage, profit calculation basis, eligible expenses, allocation method, settlement schedule, and approval requirements.

- Profit percentage and investment percentage are separate fields and need not be identical.

- The agreement must specify whether the percentage applies to sales revenue, gross profit, net profit attributable to products/batches, or total company profit.

- Store a snapshot of the applicable agreement rules for each monthly closing. A later change must not silently rewrite a past closing.

- Track capital invested, capital recovered, remaining capital, profit allocated, profit paid, and profit payable separately.

- Handle positive profit, zero profit, losses, unrecovered investment, and expenses exceeding gross profit.

- Do not treat an ordinary supplier payable, investment capital, and profit entitlement as the same balance.

# 7. Monthly financial closing — core workflow

The user clarified that supplier profit must be calculated at month-end after the full business expenses are considered. Therefore, monthly closing is a core workflow, not just a report.

1.  Review all sales, returns, cancellations, credit notes, and unpaid invoices for the month.

2.  Review purchases, goods received, cost of goods sold, unsold inventory, stock transfers, returns, spoilage, and discrepancies.

3.  Validate all expenses, including worker salaries and employer contributions, fuel, truck costs, depreciation, refrigeration electricity and maintenance, packaging, ice, administration, and applicable financial costs.

4.  Calculate depreciation for trucks and refrigeration equipment using configured asset data and appropriate accounting rules.

5.  Allocate eligible expenses to the relevant supplier, batch, truck, product, or general business pool according to configured rules and contracts.

6.  Calculate revenue, cost of goods sold, gross profit, operating expenses, net operating profit, and each partnership's agreed profit base.

7.  Apply each supplier's contractual percentage and calculate the amount payable.

8.  Review and approve the closing; show details and discrepancies before approval.

9.  Lock the closing against silent changes. Corrections require a controlled adjustment or reopening process with an audit trail.

10. Generate a monthly statement for each supplier/partner and track subsequent settlement payments.

# 8. Financial calculations and examples discussed

All figures below are illustrative examples from the brainstorming, not confirmed client data.

## 8.1 Example of monthly company result

| Item                     | Illustrative amount |
|--------------------------|---------------------|
| Total seafood sales      | 60,000 DT           |
| Cost of seafood sold     | −38,000 DT          |
| Gross profit             | 22,000 DT           |
| Worker/driver salaries   | −3,000 DT           |
| Employer contributions   | −500 DT             |
| Fuel                     | −800 DT             |
| Truck depreciation       | −500 DT             |
| Refrigerator electricity | −650 DT             |
| Maintenance              | −450 DT             |
| Packaging and ice        | −350 DT             |
| Other expenses           | −300 DT             |
| Net operating profit     | 15,450 DT           |

This simplified example excludes any additional items that may need to be considered, such as financing costs, taxes, or other accounting adjustments. The application must use the client's agreed accounting definitions.

## 8.2 Inventory and cost of goods sold

Purchases made during the month are not automatically all an expense of that month. For example, if goods purchased cost 45,000 DT and 7,000 DT of goods remain unsold at month-end, unsold inventory generally remains an asset; cost of goods sold must be calculated using the inventory method adopted by the business.

## 8.3 Expense allocation examples

| Method                                 | Description                                                                                                                                                                                | Consideration                                                     |
|----------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------|
| Proportional to gross profit           | Allocate shared expenses in proportion to each supplier's gross profit.                                                                                                                    | Simple but may not reflect actual use of fuel, storage, or labor. |
| Proportional to sales revenue          | Allocate shared expenses in proportion to supplier-related revenue.                                                                                                                        | Simple, but ignores margin differences.                           |
| By expense nature (recommended target) | Fuel by truck activity/distance; driver salary by truck activity; electricity by storage use; packaging by actual consumption; spoilage to affected batch; administration by agreed basis. | More defensible but requires more detailed operational data.      |
| Admin-configured allocation            | Owner selects or adjusts allocations at month-end.                                                                                                                                         | Flexible; changes must be justified, approved, and logged.        |

The application should support configurable allocation rules. The actual approach must follow supplier contracts and the client's accounting advice. Avoid double allocation of the same expense.

## 8.4 Example of supplier share

If the agreed profit base attributable to a supplier is 5,000 DT and the contract grants 30%, the supplier share is 1,500 DT. This is only valid if the agreement defines that exact profit base. It must not be assumed that every supplier's percentage applies to total company profit.

## 8.5 Truck depreciation example

Illustration: depreciable value 30,000 DT over 60 months using straight-line depreciation = 500 DT per month. This is not a determination of the client's proper accounting treatment; asset value, residual value, useful life, method, and local rules must be confirmed. Loan principal repayments must be distinguished from interest.

## 8.6 Profit versus cash flow

If monthly sales are 60,000 DT but customers paid only 45,000 DT, revenue is 60,000 DT and outstanding receivables are 15,000 DT (subject to applicable recognition rules). Profitability and cash flow must be separate reports. Similarly, a payment to a supplier for prior-period stock does not automatically become a current-period expense.

# 9. Daily truck closing and cash reconciliation

- Capture sales totals, cash collected, electronic/bank payments, credit sales, remaining stock, returns to refrigerator, spoilage, expenses, and cash handed to owner.

- Compare expected cash with declared cash. Example from brainstorming: expected cash 1,250 DT, declared cash 1,200 DT, difference −50 DT. Flag the difference for investigation; do not assume misconduct.

- Require a documented reason and approval for adjustments.

- The truck worker's view should show operational data needed for their job without exposing confidential company-wide financial information.

# 10. Reports and dashboards

- Commercial: daily/monthly revenue, sales by customer/product/truck/worker/supplier, and payment method.

- Stock: quantity and value by refrigerator/truck, batch history, receipts, sales, transfers, returns, losses, and discrepancies.

- Financial: gross profit, net operating result, expense categories, cash flow, customer balances, supplier balances, unpaid salaries, and other liabilities.

- Partnership: capital invested/recovered/outstanding, profit base, allocated expense details, contractual percentage, profit allocated, amount paid, and amount still due.

- Supplier statements should show opening balances where relevant, capital balance, sales/costs included, expense allocation, profit calculation, percentage, payments, and remaining balance.

- Export reports to PDF and Excel.

# 11. Suggested navigation

## Admin interface

- Dashboard

- Sales

- Customers

- Suppliers

- Products

- Stock: refrigerator, trucks, transfers, inventory counts, losses/spoilage

- Purchases

- Invoices

- Payments

- Expenses

- Employees & Payroll

- Assets & Depreciation

- Partnerships & Investments

- Monthly Profit Sharing

- Truck Closings

- Monthly Closing

- Reports

- Settings and Permissions

## Truck worker interface

- My Truck

- Start My Day

- View My Stock

- Record a Sale

- Customers (according to permissions)

- Record a Payment

- Record an Expense

- Report Damaged/Spoiled Products

- Return Products

- Close My Day

# 12. Suggested database entities

| Entity / table                                    | Purpose                                                     |
|---------------------------------------------------|-------------------------------------------------------------|
| users, roles, permissions                         | Authentication and role-based access.                       |
| employees, salary_records, salary_payments        | Employee profiles, salary obligations, and payment history. |
| trucks                                            | Truck details and assignment.                               |
| products                                          | Product catalogue.                                          |
| suppliers, customers                              | Business counterparties.                                    |
| purchases, purchase_items                         | Purchase documents and line items.                          |
| batches                                           | Lot-level supplier/cost/expiry/partnership traceability.    |
| warehouses / stock_locations                      | Refrigerator, trucks, and other locations.                  |
| stock_movements, inventory_counts                 | Auditable inventory ledger and reconciliation.              |
| sales, sale_items, invoices, payments             | Sales documents, lines, invoices, and receipts/payments.    |
| expenses, expense_categories, expense_allocations | Operating costs and their allocation.                       |
| assets, depreciation_entries                      | Trucks, refrigerator, equipment, and depreciation.          |
| partnership_agreements                            | Terms and calculation rules.                                |
| investments                                       | Capital contributions and recovery.                         |
| monthly_closings                                  | Approved monthly closing and snapshot.                      |
| monthly_profit_results / profit_allocations       | Profit base and partner allocation detail.                  |
| partner_settlements, settlement_payments          | Amounts approved as payable and payments made.              |
| truck_day_closings                                | Daily truck stock/cash reconciliation.                      |
| financial_adjustments                             | Controlled corrections.                                     |
| audit_logs                                        | Who changed/approved what and when.                         |

Exact schema, relationships, indexes, constraints, and migration strategy should be finalized after the four open business questions in Section 15 are answered.

# 13. Technical architecture recommendations

| Component        | Initial recommendation                                                                                 |
|------------------|--------------------------------------------------------------------------------------------------------|
| Frontend         | React + TypeScript                                                                                     |
| UI styling       | Tailwind CSS or equivalent component system                                                            |
| Backend          | Django + Django REST Framework                                                                         |
| Database         | PostgreSQL                                                                                             |
| Authentication   | Secure session or token-based authentication; authorization enforced server-side                       |
| Truck interface  | Responsive web application / PWA                                                                       |
| Document storage | Object storage for receipts, invoices, and attachments                                                 |
| Reports          | SQL-backed reports and dashboard charts; PDF/Excel export                                              |
| Deployment       | Managed server or cloud platform, chosen for budget and operational needs                              |
| Reliability      | Automated backups, tested restore procedure, audit trail, and transaction-safe stock/financial updates |

Start as a modular monolith rather than microservices. Sales, stock, payments, expenses, and partnership allocations must remain consistent. For example, a sale should not be saved as complete if the stock deduction or related financial record fails.

# 14. Suggested development phases

| Phase                                | Scope                                                                                                                               | Outcome                                      |
|--------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------|
| 1\. Core operations                  | Users/permissions, products, suppliers, customers, refrigerator stock, truck stock, transfers, purchases, sales, customer payments. | Manage everyday purchases, stock, and sales. |
| 2\. Truck worker view                | Mobile-first UI, truck loading, daily sales, payments, expenses, returns, spoilage, daily closing, cash reconciliation.             | Worker can operate with owner oversight.     |
| 3\. Partnerships and monthly closing | Agreements, investments, expense allocation, cost of goods sold, profit engine, monthly closing, settlements, supplier statements.  | Calculate and explain supplier entitlements. |
| 4\. Reporting and automation         | Dashboards, alerts, PDF/Excel, messaging integration if needed, accounting integration if required.                                 | Decision-support and automation.             |

# 15. Questions still open — do not assume answers

These questions were asked during the conversation and have not yet been answered. They materially affect the data model and profit engine.

## Question 1 — Supplier's profit basis

- A. Each supplier receives a percentage of net profit generated by their own products after allocating appropriate expenses.

- B. All suppliers participate in total monthly company net profit, regardless of which products generated it.

- C. Different suppliers have different models.

## Question 2 — Expense allocation

- A. All expenses proportional to supplier-related sales revenue.

- B. All expenses proportional to supplier-related gross profit.

- C. Allocate by nature (fuel by truck activity, electricity by storage, salaries by operations, etc.).

- D. Owner decides/adjusts allocations at month-end.

## Question 3 — Return of original investment

For a supplier who invests, is the original capital repaid separately from profit share? The recommended design tracks investment capital and profit entitlement as separate balances.

## Question 4 — Same product from multiple suppliers

Can the same product (e.g. Crevette Royale) be purchased from multiple suppliers at different prices in the same month? If yes, batch-level traceability is necessary.

## Additional operational questions to confirm

- Does the business use all three models: normal purchases, consignment/commission, and joint investment/profit sharing?

- Do truck workers sell directly to customers, deliver preorders, or both?

- How many trucks and refrigerators/storage locations exist? Does the owner sell directly from the refrigerator?

- What are the exact local invoice/tax and payroll requirements to support?

- Should the monthly closing use accrual-based profit or a different agreed management calculation? Who approves it?

- Which expense allocation rules are contractually permitted for each supplier?

- How are returns, discounts, bad debts, spoiled products, negative profit, and capital losses treated by each agreement?

# 16. User messages captured in chronological order

The following reproduces the user's text messages relevant to this project:

> I would like to build an application for a client how sel seafood  
> He would like to have (devi, client, fornisseur, stock( stock in frigo and stock in camion)  
> Facturisation produit , charge  
> Some times fourniseur start investigating with him and he will get back percentage on win of the product that selled together(thus is the big point)  
> Also i would like yo have 2 user vue 1 for the admin and the other for the worker on camion  
> Brain storme the idea with me and reorgaise the idea in my head
>
> The profit of suppliers will be calculated by the end of the month cause i have to calculate how much i expenses from full , amortissement camion , diver, electricity, frigo , etc after that we can calculate how much they will earn
>
> Also do not miss salary of workers
>
> Extract all of our conversations in world file do not miss anything

# 17. Final consolidated requirements checklist

- Seafood product catalogue and unit/price management.

- Supplier and customer management.

- Purchasing, goods receipt, supplier invoices, and payments.

- Separate refrigerator stock and per-truck stock.

- Batch-level traceability and inventory valuation.

- Truck transfers, sales, returns, spoilage, and inventory adjustments.

- Customer invoicing, partial payments, credit balances, and receipts.

- Expense management with categories, supporting documents, approval, and allocation.

- Worker profiles, salary tracking, salary payments, and employer costs.

- Truck, refrigerator, and equipment asset/depreciation tracking.

- Supplier agreements for ordinary purchase, consignment, commission, joint investment, and profit sharing as applicable.

- Separate tracking of capital contributions, capital recovery, profit allocated, and profit paid.

- Monthly profit calculation after relevant expenses and salaries are included.

- Configurable expense allocation and supplier profit calculation rules.

- Monthly closing review, approval, lock, and controlled corrections.

- Supplier statements and settlement history.

- Separate profitability and cash-flow reporting.

- Two user experiences: admin and truck worker, with server-enforced permissions.

- Daily truck closing and cash/stock reconciliation.

- PDF/Excel reports, audit logs, backups, and optional offline PWA support.

**END OF CONSOLIDATED PROJECT DOCUMENT**

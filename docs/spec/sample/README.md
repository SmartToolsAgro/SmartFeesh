# Sample data (not client data)

Mahmoud asked on 2026-10-10 for example materials built from the internet, realistic for Tunisia, because
the real client materials and one real month of numbers are not available yet. Everything here is a
stand-in for `docs/spec/client/` and must be replaced by the client's real lists before go-live (P4-T01).

Use it for seed commands, tests, demos and screenshots. Never import it into production.

## Files

| File | Content |
|---|---|
| `products.csv` | 12 products sold by kg, with French and Arabic names, storage, sale price, minimum stock |
| `suppliers.csv` | 4 suppliers: 2 ordinary, 1 profit-sharing partner, 1 investor partner; partners have a profit % and a loss % |
| `supplier_products.csv` | Indicative purchase cost per supplier and product (real costs change daily and are set on each receipt); dorade comes from two suppliers (Q4) |
| `customers.csv` | 9 customers around Sfax with credit limits, terms and opening balances |
| `locations.csv` | 2 cold rooms and 3 trucks (Q8) |
| `employees.csv` | 8 employees on fixed monthly salaries with employer CNSS (Q6), plus the external accountant |
| `sample-invoice.md` | Invoice layout in French with VAT, fiscal stamp and the optional withholding line |
| `sample-partner-agreement.md` | The profit-sharing rules from Q1, Q2, Q3 and Q9 written as a contract model |

## What is real and what is invented

**Real, from public sources:**
- Species sold in Tunisia and their names.
- `market_price_dt`: retail prices observed on Tunisian markets in 2026, with the source code in the
  next column. A blank value means no price was found.
- Employer CNSS rate of 17.07 % (general non-agricultural scheme, in force since 01/01/2025). It excludes
  work-accident insurance, TFP and FOPROLOS (S8).
- Invoice mentions (S7).

**Invented:**
- Every company, person, tax ID, phone number and plate. Tax IDs start with `0000` on purpose.
- Sale prices: the eight products of the prototype keep the prototype's prices so screens and acceptance
  tests stay consistent; the four added products are set near the observed market price.
- Purchase costs, salaries, credit limits, balances, profit and loss percentages and invested capital.
- Arabic product names are to be reviewed by a native speaker.

Not included: product photos (the prototype's illustrations are enough for development) and a month of
sales and expenses for the profit-sharing worked example (P0-T02 still needs real numbers).

## Two findings to check with the accountant

1. **VAT on seafood.** Table A of the Tunisian VAT code lists "Les produits de la pêche tunisienne" among
   the exempt operations (item 38, S9). Q5 was answered "19 % for all products". Imported or processed
   products may be treated differently. P2-T05 therefore allows a VAT rate per product on top of the
   company default.
2. **E-invoicing.** Since 1 January 2026 electronic invoicing through TTN is mandatory for every business
   subject to VAT, and non-compliant paper or PDF invoices are no longer recognised for tax purposes
   (S10). TTN is on hold in this project (D-016).

## Sources

| Code | Source | Used for |
|---|---|---|
| S1 | [Tunisie Numérique, Sfax market, 15/09/2026](https://www.tunisienumerique.com/prix-alimentaires-a-sfax-le-point-sur-les-marches-ce-mardi-photosvideo/) | Dorade 22, loup 26, crevettes 12 DT/kg |
| S2 | [Tunisie Numérique, Sfax markets, 24/02/2026](https://www.tunisienumerique.com/sfax-les-prix-des-poissons-sur-les-marches-en-debut-de-ramadan-photosvideo/) | Rouget 12, sardines 5, bar 40, crevettes 28, daurade 23 DT/kg |
| S3 | [Tunisie Numérique, fish price reports 2026](https://www.tunisienumerique.com/tunisie-actualite/prix-des-poissons/) | Sfax reports of February and June 2026: dorade 20 to 23, crevettes 18 to 25, loup 23 to 30 DT/kg (search summaries, pages not read) |
| S4 | [Tuniscope, Tunis central market, 01/05/2026](https://www.tuniscope.com/ar/article/430829/actu-arabe/arabe/marche-central-tunisie-prix-175811) | Mulet 11.800, loup vivant 34.800 DT/kg |
| S5 | [Business News, 27/02/2026](https://businessnews.com.tn/2026/02/27/hausse-des-prix-du-poisson-les-intermediaires-pointes-du-doigt-par-lutap/1390097/) | Poulpe 41 to 54 DT/kg (search summary, page not read, attribution uncertain) |
| S6 | [La Presse, 27/02/2026](https://www.lapresse.tn/2026/02/27/sardine-quand-le-poisson-du-pauvre-devient-un-luxe-pendant-ramadan/) | Sardine about 7 DT/kg (search summary, page not read) |
| S7 | [La Presse, invoicing rules](https://www.lapresse.tn/?p=4305779) | Mandatory invoice mentions, article 18 of the VAT code (search summary, page not read) |
| S8 | [Ma calculatrice en ligne, CNSS Tunisie 2026](https://macalculatriceenligne.com/afrique/calcul-cnss-tunisie/) | CNSS rates (search summary, page not read) |
| S9 | [Jurisite Tunisie, VAT code, Table A](https://www.jurisitetunisie.com/tunisie/codes/tva/tva1000A1.htm) | VAT exemption of Tunisian fishing products |
| S10 | [La Presse, 07/01/2026](https://www.lapresse.tn/2026/01/07/tout-comprendre-a-la-facture-electronique-qui-simpose-en-tunisie-en-2026/) | E-invoicing obligation from 01/01/2026 |

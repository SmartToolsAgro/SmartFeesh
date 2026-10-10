"""Demo batches: recent deliveries of the stand-in suppliers, at the costs of docs/spec/sample/supplier_products.csv.

Costs move a little from one delivery to the next, as real purchase prices do (D-020). Dorade royale comes
from two suppliers at two prices (Q4), and two deliveries of Crevette Royale show the oldest-first order (Q7).
Dates are counted back from the day the seed runs. The stock of these batches comes with the ledger (P1-T06).
"""

import datetime as dt

from django.utils import timezone

from apps.catalog import selectors as catalog
from apps.core.models import Organization, User
from apps.inventory import selectors, services
from apps.partners import selectors as partners

# supplier, product, supplier's delivery note, received N days ago, cost (DT/kg), kept N days (use-by)
BATCHES = [
    ("F-004", "CD-002", "SDS-2026-311", 20, "30.000", 365),
    ("F-002", "CA-005", "MPS-5498", 12, "23.000", 180),
    ("F-004", "CD-002", "SDS-2026-342", 6, "30.750", 365),
    ("F-004", "SY-008", "SDS-2026-342", 6, "25.500", 365),
    ("F-001", "CR-001", "KRK-1187", 3, "33.500", 4),
    ("F-001", "PO-006", "KRK-1187", 3, "25.000", 4),
    ("F-002", "DO-003", "MPS-5521", 2, "20.000", 4),
    ("F-003", "DO-003", "AQM-0784", 2, "18.500", 5),
    ("F-003", "LO-004", "AQM-0784", 2, "21.500", 5),
    ("F-001", "CR-001", "KRK-1192", 1, "34.000", 4),
    ("F-001", "SE-012", "KRK-1192", 1, "20.500", 4),
    ("F-002", "RO-009", "MPS-5530", 1, "10.500", 3),
    ("F-002", "SA-010", "MPS-5530", 1, "5.200", 2),
    ("F-002", "MU-011", "MPS-5530", 1, "10.000", 3),
    ("F-003", "MO-007", "AQM-0791", 0, "6.800", 3),
]


def seed_batches(*, organization: Organization, actor: User | None) -> int:
    """Create the demo batches that do not exist yet, oldest first. Returns how many were created.

    A batch is known by its delivery note and product, so running the seed again adds nothing.
    """
    products = {product.reference: product for product in catalog.products_of(organization, status="all")}
    suppliers = {supplier.reference: supplier for supplier in partners.suppliers_of(organization, status="all")}
    existing = set(selectors.batches_of(organization).values_list("receipt_reference", "product__reference"))
    today = timezone.localdate()
    created = 0
    for supplier, product, delivery_note, days_ago, cost, kept_days in BATCHES:
        if (delivery_note, product) in existing:
            continue
        received_on = today - dt.timedelta(days=days_ago)
        services.create_batch(
            organization=organization,
            actor=actor,
            product=products[product],
            supplier=suppliers[supplier],
            receipt_reference=delivery_note,
            received_on=received_on,
            unit_cost=cost,
            use_by=received_on + dt.timedelta(days=kept_days),
        )
        created += 1
    return created

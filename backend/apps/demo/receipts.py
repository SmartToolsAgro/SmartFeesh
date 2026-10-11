"""Demo goods receipt: this morning's delivery from the port, with the weight difference of the prototype.

Dorade royale: 62 kg ordered and invoiced, 60 kg accepted (the prototype's "Écart de poids à la réception",
and the start of the Phase 1 acceptance test). Known by its delivery note, so the seed adds it only once.
"""

import datetime as dt

from django.utils import timezone

from apps.catalog import selectors as catalog
from apps.core.models import Organization, User
from apps.inventory import selectors as inventory
from apps.partners import selectors as partners
from apps.purchasing import selectors, services

DELIVERY_NOTE = "MPS-5544"
SUPPLIER = "F-002"
LOCATION = "Chambre froide 1 (frais)"
# product, ordered kg, invoiced kg, accepted kg, cost (DT/kg), kept N days
LINES = [
    ("DO-003", "62", "62", "60", "20.250", 4),
    ("RO-009", "20", "20", "20", "10.800", 3),
]


def seed_receipts(*, organization: Organization, actor: User | None) -> int:
    """Record the demo receipt when it is not there yet. Returns how many receipts were created."""
    if selectors.receipts_of(organization, search=DELIVERY_NOTE).exists():
        return 0
    products = {product.reference: product for product in catalog.products_of(organization, status="all")}
    supplier = partners.suppliers_of(organization, status="all").get(reference=SUPPLIER)
    location = inventory.locations_of(organization, status="all").get(name=LOCATION)
    today = timezone.localdate()
    services.create_receipt(
        organization=organization,
        actor=actor,
        supplier=supplier,
        location=location,
        received_on=today,
        supplier_reference=DELIVERY_NOTE,
        lines=[
            {
                "product": products[product],
                "ordered_quantity": ordered,
                "invoiced_quantity": invoiced,
                "accepted_quantity": accepted,
                "unit_cost": cost,
                "use_by": today + dt.timedelta(days=kept_days),
            }
            for product, ordered, invoiced, accepted, cost, kept_days in LINES
        ],
    )
    return 1

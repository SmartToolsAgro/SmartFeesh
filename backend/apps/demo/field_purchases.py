"""Demo purchase at the port (D-157): what the driver bought from a Kerkennah fisherman this morning, to check.

Poulpe 18 kg × 28.000 and a fish not in the catalogue yet ("Pageot", 6.500 kg × 16.000) = 608.000 DT; 300 DT given
in cash, the rest at 15 days. It waits in "Achats › À valider". Known by the supplier's paper number, so the seed
adds it only once.
"""

from django.utils import timezone

from apps.catalog import selectors as catalog
from apps.core.models import Organization, User
from apps.partners import selectors as partners
from apps.purchasing import selectors, services

PAPER = "KRK-0917"
SUPPLIER = "F-001"


def seed_field_purchases(*, organization: Organization, driver: User) -> int:
    """Record the demo purchase when it is not there yet. Returns how many purchases were made."""
    if selectors.field_purchases_of(organization, search=PAPER).exists():
        return 0
    octopus = catalog.products_of(organization, status="all").get(reference="PO-006")
    services.submit_field_purchase(
        organization=organization,
        buyer=driver,
        fields={
            "supplier": partners.suppliers_of(organization, status="all").get(reference=SUPPLIER),
            "bought_on": timezone.localdate(),
            "terms": "days",
            "due_days": 15,
            "supplier_reference": PAPER,
            "notes": "Le pageot n'est pas dans la liste.",
            "lines": [
                {"product": octopus, "declared_quantity": "18", "unit_cost": "28.000"},
                {"proposed_product": "Pageot", "declared_quantity": "6.500", "unit_cost": "16.000"},
            ],
            "payments": [{"method": "cash", "amount": "300"}],
        },
    )
    return 1

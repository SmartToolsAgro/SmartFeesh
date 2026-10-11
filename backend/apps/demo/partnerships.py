"""Demo partnership lot (P6-T01, D-060): Pêcherie Kerkennah (F-001, 40 % of a profit, 25 % of a loss, as in
docs/spec/sample/suppliers.csv) shares its seiche lot KRK-1192 (15 kg at 20.500 DT) with the owner.

The partnership is set before the demo sales, so the seiche sold on Sidi Mansour's converted quote is the
lot's first sale; a transport cost typed on the lot comes after the demo expenses. The lot stays open: its
"Résultat du lot" card shows the result so far. Running the seed again creates nothing.
"""

import uuid
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models import Organization, User
from apps.expenses import selectors as expense_selectors
from apps.expenses import services as expenses
from apps.inventory import selectors as inventory
from apps.partners import selectors as partners
from apps.partnerships import selectors, services

if TYPE_CHECKING:
    from apps.inventory.models import Batch

SEED_NAMESPACE = uuid.UUID("8d1f2b7c-4a6e-4f3b-9c2d-7e5a1b0c3d48")
PARTNER = "F-001"
DELIVERY_NOTE = "KRK-1192"
PRODUCT = "SE-012"


def _lot(organization: Organization) -> "Batch | None":
    return (
        inventory.batches_of(organization)
        .filter(receipt_reference=DELIVERY_NOTE, product__reference=PRODUCT)
        .order_by("id")
        .first()
    )


def seed_partnerships(*, organization: Organization, actor: User | None) -> int:
    """Put the seiche lot in partnership with Pêcherie Kerkennah, once. Returns how many were created."""
    batch = _lot(organization)
    if batch is None or selectors.partnerships_of(organization, batch_id=batch.pk).exists():
        return 0
    partner = partners.suppliers_of(organization, status="all").filter(reference=PARTNER).first()
    if partner is None:
        return 0
    try:
        services.create_partnership(
            organization=organization,
            actor=actor,
            batch=batch,
            partner=partner,
            owner_capital="200.000",
            partner_capital="107.500",
            profit_rate="40",
            loss_rate="25",
            notes="Lot acheté à deux : 15 kg de seiche à 20,500 DT/kg (exemple).",
        )
    except ValidationError:  # the lot was sold or changed by hand on staging
        return 0
    return 1


def seed_partnership_costs(*, organization: Organization, actor: User | None) -> int:
    """A transport cost typed on the partnership lot, approved. Returns how many were created."""
    batch = _lot(organization)
    if batch is None:
        return 0
    client_uuid = uuid.uuid5(SEED_NAMESPACE, "transport-seiche")
    if expense_selectors.expenses_of(organization).filter(client_uuid=client_uuid).exists():
        return 0
    expenses.create_expense(
        organization=organization,
        actor=actor,
        spent_on=max(batch.received_on, timezone.localdate()),
        category=expense_selectors.category_by_code(organization, "transport"),
        amount="18.000",
        description="Transport Kerkennah → dépôt",
        payee="Transports Ben Ammar",
        batch=batch,
        client_uuid=client_uuid,
        approve=True,
    )
    return 1

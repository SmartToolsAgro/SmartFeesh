"""Demo losses and stock count: the prototype's 1.5 kg of mussels spoiled on Camion 1 (under the threshold,
so already out of stock), a heavier loss in the fresh cold room waiting for the owner, and a count of the
frozen cold room ready to be filled in.

Losses have fixed `client_uuid`s and the count is made once per location, so running the seed again
creates nothing.
"""

import uuid

from django.utils import timezone

from apps.catalog import selectors as catalog
from apps.core.models import Organization, User
from apps.inventory import selectors, services
from apps.inventory.services import LossReason

SEED_NAMESPACE = uuid.UUID("9a4c2b7e-6f1d-4e8a-b3c5-0d2e7f6a1b94")
FROZEN_ROOM = "Chambre froide 2 (congelé)"
# key, location, product, kg, reason, note, the owner approves at once
LOSSES = [
    ("mussels-camion-1", "Camion 1", "MO-007", "1.5", LossReason.SPOILED, "Sac percé pendant la tournée", True),
    (
        "rouget-cold-room",
        "Chambre froide 1 (frais)",
        "RO-009",
        "4",
        LossReason.COLD_CHAIN,
        "Porte restée ouverte",
        False,
    ),
]


def seed_losses(*, organization: Organization, actor: User | None) -> int:
    """Record the demo losses and open the demo count when they do not exist yet. Returns how many were made."""
    locations = {location.name: location for location in selectors.locations_of(organization, status="all")}
    products = {product.reference: product for product in catalog.products_of(organization, status="all")}
    existing = set(selectors.losses_of(organization).exclude(client_uuid=None).values_list("client_uuid", flat=True))
    today = timezone.localdate()
    created = 0
    for key, location, product, kg, reason, note, at_once in LOSSES:
        client_uuid = uuid.uuid5(SEED_NAMESPACE, key)
        if client_uuid in existing:
            continue
        services.record_loss(
            organization=organization,
            actor=actor,
            location=locations[location],
            product=products[product],
            quantity=kg,
            reason=reason,
            lost_on=today,
            note=note,
            # The second one stands for a loss typed by a manager: above the threshold, it waits.
            may_approve=at_once,
            client_uuid=client_uuid,
        )
        created += 1
    frozen_room = locations[FROZEN_ROOM]
    # On staging the seed runs on every deploy against data people use: an emptied room has nothing to count, and
    # the demo count must not stop the deploy (start_count refuses an empty place).
    nothing_to_count = not selectors.on_hand_of(organization, location_id=frozen_room.pk).exists()
    if not nothing_to_count and not selectors.counts_of(organization, location_id=frozen_room.pk).exists():
        services.start_count(
            organization=organization,
            actor=actor,
            location=frozen_room,
            counted_on=today,
            notes="Inventaire de démonstration",
        )
        created += 1
    return created

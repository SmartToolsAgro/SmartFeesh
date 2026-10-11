"""Demo transfers: Camion 2's day (a morning load with the day's prices, then its evening return), and a
load of Camion 3 still waiting for validation.

Each transfer has a fixed `client_uuid`, so running the seed again creates nothing. The load and the return
are made on the day of the first seed; later runs leave them on that day.
"""

import uuid

from django.utils import timezone

from apps.catalog import selectors as catalog
from apps.core.models import Organization, User
from apps.inventory import selectors, services

SEED_NAMESPACE = uuid.UUID("5d0f6a0e-3b7f-4c1e-9a52-2f7e1d4c8b31")
FRESH_ROOM = "Chambre froide 1 (frais)"
# key, from, to, validated, lines: product, kg, price per kg of the day (None: the price in force)
TRANSFERS: list[tuple[str, str, str, bool, list[tuple[str, str, str | None]]]] = [
    ("morning-load", FRESH_ROOM, "Camion 2", True, [("DO-003", "10", "25.000"), ("CR-001", "8", None)]),
    ("evening-return", "Camion 2", FRESH_ROOM, True, [("DO-003", "2.5", None), ("CR-001", "1", None)]),
    ("draft-load", FRESH_ROOM, "Camion 3", False, [("LO-004", "5", None)]),
]


def seed_transfers(*, organization: Organization, actor: User | None) -> int:
    """Create the demo transfers that do not exist yet. Returns how many were created."""
    locations = {location.name: location for location in selectors.locations_of(organization, status="all")}
    products = {product.reference: product for product in catalog.products_of(organization, status="all")}
    existing = set(selectors.transfers_of(organization).exclude(client_uuid=None).values_list("client_uuid", flat=True))
    created = 0
    for key, source, target, validated, lines in TRANSFERS:
        client_uuid = uuid.uuid5(SEED_NAMESPACE, key)
        if client_uuid in existing:
            continue
        services.create_transfer(
            organization=organization,
            actor=actor,
            from_location=locations[source],
            to_location=locations[target],
            transferred_on=timezone.localdate(),
            lines=[
                {"product": products[reference], "quantity": kg, "unit_price": price} for reference, kg, price in lines
            ],
            client_uuid=client_uuid,
            validate=validated,
        )
        created += 1
    return created

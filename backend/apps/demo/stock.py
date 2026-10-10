"""Demo stock: the demo batches received into the cold rooms, then a morning load of Camion 1.

Fresh products go to "Chambre froide 1", frozen ones to "Chambre froide 2". Weights are net, as on the
suppliers' invoices (Q12). Every movement has a fixed `client_uuid`, so running the seed again posts nothing.
"""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from django.utils import timezone

from apps.core.models import Organization, User
from apps.inventory import selectors, services
from apps.inventory.services import MovementKind

FRESH_ROOM = "Chambre froide 1 (frais)"
FROZEN_ROOM = "Chambre froide 2 (congelé)"
MORNING_TRUCK = "Camion 1"
FROZEN_PRODUCTS = frozenset({"CD-002", "CA-005", "SY-008"})
SEED_NAMESPACE = uuid.UUID("0b6f3c52-5f0e-4a43-9d55-6f1d8c1e2a90")

# supplier's delivery note, product, net kg received
RECEIPTS = [
    ("SDS-2026-311", "CD-002", "40"),
    ("MPS-5498", "CA-005", "30"),
    ("SDS-2026-342", "CD-002", "25"),
    ("SDS-2026-342", "SY-008", "20"),
    ("KRK-1187", "CR-001", "35"),
    ("KRK-1187", "PO-006", "22"),
    ("MPS-5521", "DO-003", "40"),
    ("AQM-0784", "DO-003", "30"),
    ("AQM-0784", "LO-004", "18"),
    ("KRK-1192", "CR-001", "30"),
    ("KRK-1192", "SE-012", "15"),
    ("MPS-5530", "RO-009", "20"),
    ("MPS-5530", "SA-010", "35"),
    ("MPS-5530", "MU-011", "18"),
    ("AQM-0791", "MO-007", "40"),
]
# Camion 1's load on the morning of the first seed (once only): delivery note and product of the batch, kg
MORNING_LOAD = [
    ("KRK-1187", "CR-001", "12"),
    ("MPS-5521", "DO-003", "10"),
    ("MPS-5498", "CA-005", "8"),
    ("AQM-0791", "MO-007", "10"),
]


def _at(day: dt.date, hour: int, minute: int = 0) -> dt.datetime:
    return timezone.make_aware(dt.datetime.combine(day, dt.time(hour, minute)))


def seed_stock(*, organization: Organization, actor: User | None) -> int:
    """Post the demo receipts and the morning load that are not posted yet. Returns how many were posted."""
    locations = {location.name: location for location in selectors.locations_of(organization, status="all")}
    batches = {
        (batch.receipt_reference, batch.product.reference): batch for batch in selectors.batches_of(organization)
    }
    posted_keys = set(
        selectors.movements_of(organization).exclude(client_uuid=None).values_list("client_uuid", flat=True)
    )
    today = timezone.localdate()
    posted = 0

    def post(key: str, **fields: Any) -> None:
        nonlocal posted
        client_uuid = uuid.uuid5(SEED_NAMESPACE, key)
        if client_uuid in posted_keys:
            return
        services.post_movement(organization=organization, actor=actor, client_uuid=client_uuid, **fields)
        posted += 1

    for delivery_note, product, kg in RECEIPTS:
        batch = batches[(delivery_note, product)]
        room = FROZEN_ROOM if product in FROZEN_PRODUCTS else FRESH_ROOM
        post(
            f"receipt/{delivery_note}/{product}",
            kind=MovementKind.RECEIPT,
            batch=batch,
            quantity=Decimal(kg),
            to_location=locations[room],
            occurred_at=_at(batch.received_on, 6, 30),
        )
    for delivery_note, product, kg in MORNING_LOAD:
        room = FROZEN_ROOM if product in FROZEN_PRODUCTS else FRESH_ROOM
        post(
            f"load/{delivery_note}/{product}",
            kind=MovementKind.TRANSFER,
            batch=batches[(delivery_note, product)],
            quantity=Decimal(kg),
            from_location=locations[room],
            to_location=locations[MORNING_TRUCK],
            occurred_at=_at(today, 7, 15),
        )
    return posted

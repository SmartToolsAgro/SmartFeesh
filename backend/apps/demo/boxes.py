"""Demo returnable boxes: the 50 small and 50 big boxes the company owns, in the fresh cold room (D-135).

They enter the ledger as an opening stock, so no supplier is owed any of them. A box type that already has
an opening stock is left alone, so running the seed again creates nothing.
"""

from apps.boxes import selectors, services
from apps.boxes.services import BoxMovementKind, BoxType
from apps.core.models import Organization, User
from apps.inventory import selectors as inventory

COLD_ROOM = "Chambre froide 1 (frais)"
# Boxes the company owns, per box type.
OPENING_BOXES: dict[str, int] = {BoxType.SMALL: 50, BoxType.BIG: 50}


def seed_boxes(*, organization: Organization, actor: User | None) -> int:
    """Post the opening stock of the box types that have none yet. Returns how many movements were made."""
    seeded = set(
        selectors.movements_of(organization).filter(kind=BoxMovementKind.OPENING).values_list("box_type", flat=True)
    )
    counts = {box_type: count for box_type, count in OPENING_BOXES.items() if box_type not in seeded}
    cold_room = inventory.locations_of(organization, status="all").filter(name__iexact=COLD_ROOM).first()
    if not counts or cold_room is None:
        return 0
    movements = services.post_box_counts(
        organization=organization,
        actor=actor,
        kind=BoxMovementKind.OPENING,
        counts=counts,
        to_holder=services.holder_for(organization=organization, location=cold_room),
    )
    return len(movements)

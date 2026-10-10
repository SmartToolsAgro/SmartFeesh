"""What the session answer (`/me`) says about a member beyond core: today, a driver's truck.

`core` imports no other app (ARCHITECTURE §3), so the app that knows trucks registers a lookup here when
it starts (`fleet.apps.FleetConfig.ready`).
"""

from collections.abc import Callable
from typing import TypedDict

from .models import Membership


class TruckRef(TypedDict):
    id: int
    name: str
    plate: str
    location_id: int


type TruckLookup = Callable[[Membership], TruckRef | None]

_truck_lookup: TruckLookup | None = None


def register_truck_lookup(lookup: TruckLookup) -> None:
    global _truck_lookup
    _truck_lookup = lookup


def truck_of(membership: Membership) -> TruckRef | None:
    """The truck the member drives, or None (not a driver, no truck yet, or no app registered)."""
    return _truck_lookup(membership) if _truck_lookup is not None else None

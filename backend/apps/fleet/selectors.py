"""Reusable read queries of trucks, and the "own truck" rule for drivers (ARCHITECTURE §4.8)."""

from typing import Literal

from django.db.models import QuerySet

from apps.core.models import Membership, Organization, Role
from apps.core.session import TruckRef

from .models import Truck

type TruckStatus = Literal["active", "archived", "all"]

OFFICE_ROLES = frozenset({Role.OWNER, Role.MANAGER, Role.ACCOUNTANT})


def trucks_of(organization: Organization, *, status: TruckStatus = "active") -> QuerySet[Truck]:
    """Trucks of one organization sorted by name, with their location and driver."""
    trucks = (
        Truck.objects.for_organization(organization)
        .select_related("location", "driver")
        .order_by("location__name", "id")
    )
    if status == "active":
        trucks = trucks.filter(is_active=True)
    elif status == "archived":
        trucks = trucks.filter(is_active=False)
    return trucks


def truck_of(organization: Organization, truck_id: int) -> Truck:
    """One truck. Raises Truck.DoesNotExist outside the organization."""
    return trucks_of(organization, status="all").get(pk=truck_id)


def truck_of_driver(membership: Membership) -> Truck | None:
    """The active truck assigned to this member, if they are a driver and have one."""
    if membership.role != Role.DRIVER:
        return None
    return trucks_of(membership.organization).filter(driver_id=membership.user_id).first()


def may_use_location(membership: Membership, location_id: int) -> bool:
    """Whether this member may see or change the stock of a location.

    Owners, managers and the accountant: any location of their organization. A driver: only the location
    of their own active truck. Any other role: none. Views must still scope rows by organization (D-022).
    """
    if membership.role in OFFICE_ROLES:
        return True
    truck = truck_of_driver(membership)
    return truck is not None and truck.location_id == location_id


def may_use_truck(membership: Membership, truck: Truck) -> bool:
    """Whether this member may see or work with a truck: the office, or the truck's own driver."""
    if truck.organization_id != membership.organization_id:
        return False
    if membership.role in OFFICE_ROLES:
        return True
    return membership.role == Role.DRIVER and truck.is_active and truck.driver_id == membership.user_id


def truck_ref_of_driver(membership: Membership) -> TruckRef | None:
    """The driver's truck as the session answer (`/me`) shows it."""
    truck = truck_of_driver(membership)
    if truck is None:
        return None
    return {"id": truck.pk, "name": truck.location.name, "plate": truck.plate, "location_id": truck.location_id}

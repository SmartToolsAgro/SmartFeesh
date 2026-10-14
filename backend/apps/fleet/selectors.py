"""Reusable read queries of trucks, and the "own truck" rule for drivers (ARCHITECTURE §4.8)."""

from datetime import date as date_type
from datetime import datetime, time, timedelta
from typing import Literal

from django.db.models import QuerySet
from django.utils import timezone

from apps.core.models import Membership, Organization, Role
from apps.core.session import TruckRef

from .models import DriverDay, Truck, TruckAssignment

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


def assignments_of(organization: Organization) -> QuerySet[TruckAssignment]:
    """Every truck assignment of one organization, with truck, location and driver."""
    return TruckAssignment.objects.for_organization(organization).select_related("truck__location", "driver")


def assignments_on(organization: Organization, day: date_type) -> QuerySet[TruckAssignment]:
    """The truck assignments of one day, by truck name."""
    return assignments_of(organization).filter(date=day).order_by("truck__location__name", "id")


def assignment_of(organization: Organization, assignment_id: int) -> TruckAssignment:
    """One assignment. Raises TruckAssignment.DoesNotExist outside the organization."""
    return assignments_of(organization).get(pk=assignment_id)


def truck_of_driver(membership: Membership, on: date_type | None = None) -> Truck | None:
    """The active truck this member drives on a day (today by default), if they are a driver and have one.

    The day's assignment first (D-046). Without one, the truck they usually drive, unless another driver was
    assigned to it that day. A driver who usually drives several trucks gets the first by name.
    """
    if membership.role != Role.DRIVER:
        return None
    day = on or timezone.localdate()
    assigned = assignments_on(membership.organization, day).filter(driver_id=membership.user_id).first()
    if assigned is not None:
        return assigned.truck if assigned.truck.is_active else None
    return (
        trucks_of(membership.organization).filter(driver_id=membership.user_id).exclude(assignments__date=day).first()
    )


def may_use_location(membership: Membership, location_id: int, on: date_type | None = None) -> bool:
    """Whether this member may see or change the stock of a location.

    Owners, managers and the accountant: any location of their organization. A driver: only the location
    of their truck of the day (today, or `on` for something that happened on an earlier day, D-133). Any
    other role: none. Views must still scope rows by organization (D-022).
    """
    if membership.role in OFFICE_ROLES:
        return True
    truck = truck_of_driver(membership, on)
    return truck is not None and truck.location_id == location_id


def may_use_truck(membership: Membership, truck: Truck) -> bool:
    """Whether this member may see or work with a truck: the office, or its driver of the day."""
    if truck.organization_id != membership.organization_id:
        return False
    if membership.role in OFFICE_ROLES:
        return True
    if membership.role != Role.DRIVER or not truck.is_active:
        return False
    own = truck_of_driver(membership)
    return own is not None and own.pk == truck.pk


def truck_ref_of_driver(membership: Membership) -> TruckRef | None:
    """The driver's truck as the session answer (`/me`) shows it."""
    truck = truck_of_driver(membership)
    if truck is None:
        return None
    return {"id": truck.pk, "name": truck.location.name, "plate": truck.plate, "location_id": truck.location_id}


def driver_day_of(membership: Membership, on: date_type | None = None) -> DriverDay | None:
    """The day this driver opened on that date (today by default), if any: running, or closed once its
    closing is sent (D-134)."""
    return (
        DriverDay.objects.for_organization(membership.organization)
        .select_related("truck__location")
        .filter(driver_id=membership.user_id, date=on or timezone.localdate())
        .first()
    )


def driver_days_of(organization: Organization, *, driver_id: int) -> QuerySet[DriverDay]:
    """A driver's days, newest first, with the truck."""
    return (
        DriverDay.objects.for_organization(organization)
        .filter(driver_id=driver_id)
        .select_related("truck__location", "driver")
        .order_by("-date", "-id")
    )


def day_window(driver_day: DriverDay) -> tuple[datetime, datetime]:
    """The moments a driver's day covers, `start` included and `end` excluded (D-134): its date, up to the
    moment its closing was sent. A day that runs (not sent yet, or opened again by a new load), or one closed
    on a later date from the history, covers its whole date and no more."""
    midnight = timezone.make_aware(datetime.combine(driver_day.date, time.min))
    next_midnight = timezone.make_aware(datetime.combine(driver_day.date + timedelta(days=1), time.min))
    end = next_midnight if driver_day.ended_at is None else min(driver_day.ended_at, next_midnight)
    return midnight, max(midnight, end)


def closed_days_on_truck(organization: Organization, *, location_id: int, on: date_type) -> list[DriverDay]:
    """The days of one date whose closing was sent, on the truck of this location, by a driver who still has
    that truck that date: the days a new load opens again (D-134). A driver moved to another truck since, or
    who is no longer a driver, keeps their day closed."""
    days = list(
        DriverDay.objects.for_organization(organization)
        .filter(truck__location_id=location_id, date=on, ended_at__isnull=False)
        .select_related("truck__location", "driver")
        .order_by("id")
    )
    drivers = {
        membership.user_id: membership
        for membership in Membership.objects.filter(
            organization=organization, user_id__in=[day.driver_id for day in days], role=Role.DRIVER, is_active=True
        )
    }
    still_theirs = []
    for day in days:
        membership = drivers.get(day.driver_id)
        truck = truck_of_driver(membership, on) if membership is not None else None
        if truck is not None and truck.pk == day.truck_id:
            still_theirs.append(day)
    return still_theirs


def locked_driver_day(driver_day: DriverDay) -> DriverDay:
    """The same day read again with its row locked (inside a transaction), with truck and driver."""
    return DriverDay.objects.select_for_update().select_related("truck__location", "driver").get(pk=driver_day.pk)


def drivers_by_truck_day(
    organization: Organization, *, date_from: date_type, date_to: date_type
) -> dict[tuple[int, date_type], str]:
    """Who drove each truck on each day, from the days drivers opened on the phone: `{(truck location id,
    day): driver name}`. A day nobody opened is missing (reports show it as "no driver")."""
    rows = (
        DriverDay.objects.for_organization(organization)
        .filter(date__gte=date_from, date__lte=date_to)
        .select_related("driver", "truck")
        .order_by("id")
    )
    return {(row.truck.location_id, row.date): row.driver.get_full_name() or row.driver.username for row in rows}

"""Every write on trucks goes through these functions (ARCHITECTURE §3)."""

import re
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from apps.core import audit
from apps.core.models import Membership, Organization, Role, User
from apps.inventory import services as inventory
from apps.inventory.services import LocationKind

from .models import Truck


class _Unchanged:
    """Marks an argument that was not given, where None has a meaning (no driver)."""


UNCHANGED = _Unchanged()


def normalized_plate(value: str) -> str:
    """A plate in capitals with single spaces: "123 tu  4567" → "123 TU 4567"."""
    return re.sub(r"\s+", " ", value).strip().upper()


def _snapshot(truck: Truck) -> dict[str, Any]:
    return {
        "name": truck.location.name,
        "plate": truck.plate,
        "driver": truck.driver.username if truck.driver else None,
    }


def _clean_truck(truck: Truck) -> None:
    errors: dict[str, str] = {}
    truck.plate = normalized_plate(truck.plate)
    others = Truck.objects.for_organization(truck.organization).exclude(pk=truck.pk)
    if not truck.plate:
        errors["plate"] = _("L'immatriculation est obligatoire.")
    elif others.filter(plate=truck.plate).exists():
        errors["plate"] = _("Un autre camion a déjà cette immatriculation.")
    if truck.driver is not None:
        is_driver = Membership.objects.filter(
            organization=truck.organization, user=truck.driver, role=Role.DRIVER, is_active=True
        ).exists()
        if not is_driver:
            errors["driver"] = _("Ce compte n'est pas un chauffeur de la société.")
        elif others.filter(driver=truck.driver).exists():
            errors["driver"] = _("Ce chauffeur a déjà un autre camion.")
        elif not truck.is_active:
            errors["driver"] = _("Un camion archivé n'a pas de chauffeur.")
    if errors:
        raise ValidationError(errors)


@transaction.atomic
def create_truck(
    *, organization: Organization, actor: User | None, name: str, plate: str, driver: User | None = None
) -> Truck:
    """A new truck, with the stock location that holds its goods."""
    truck = Truck(organization=organization, plate=plate, driver=driver)
    _clean_truck(truck)
    truck.location = inventory.create_location(
        organization=organization, actor=actor, kind=LocationKind.TRUCK, name=name
    )
    truck.save()
    audit.record(organization=organization, actor=actor, action="truck.created", target=truck, after=_snapshot(truck))
    return truck


@transaction.atomic
def update_truck(
    *,
    truck: Truck,
    actor: User | None,
    name: str | None = None,
    plate: str | None = None,
    driver: User | _Unchanged | None = UNCHANGED,
) -> Truck:
    """Rename a truck, change its plate, or give it to another driver (`driver=None` takes it back)."""
    truck = Truck.objects.select_for_update().select_related("location").get(pk=truck.pk)
    before = _snapshot(truck)
    if plate is not None:
        truck.plate = plate
    if not isinstance(driver, _Unchanged):
        truck.driver = driver
    _clean_truck(truck)
    if name is not None:
        truck.location = inventory.update_location(location=truck.location, actor=actor, name=name)
    truck.save()
    after = _snapshot(truck)
    changed = [field for field in after if after[field] != before[field]]
    if changed:
        audit.record(
            organization=truck.organization,
            actor=actor,
            action="truck.updated",
            target=truck,
            before={field: before[field] for field in changed},
            after={field: after[field] for field in changed},
        )
    return truck


@transaction.atomic
def set_truck_active(*, truck: Truck, actor: User | None, is_active: bool) -> Truck:
    """Archive a truck (sold, broken down for good) with its location, or bring it back.

    Archiving takes the truck back from its driver, so the driver can be given another one.
    """
    truck = Truck.objects.select_for_update().select_related("location").get(pk=truck.pk)
    if truck.is_active == is_active:
        return truck
    before = _snapshot(truck)
    truck.is_active = is_active
    if not is_active:
        truck.driver = None
    truck.save(update_fields=["is_active", "driver", "updated_at"])
    inventory.set_location_active(location=truck.location, actor=actor, is_active=is_active)
    audit.record(
        organization=truck.organization,
        actor=actor,
        action="truck.restored" if is_active else "truck.archived",
        target=truck,
        before={"driver": before["driver"]} if before["driver"] else None,
    )
    return truck

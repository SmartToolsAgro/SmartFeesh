"""Every write on stock locations (and on stock, from P1-T06) goes through these functions (ARCHITECTURE §3)."""

from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from apps.core import audit
from apps.core.models import Organization, User

from .models import LocationKind as LocationKind  # re-exported for apps that create locations
from .models import StockLocation


def _snapshot(location: StockLocation) -> dict[str, Any]:
    return {"kind": location.kind, "name": location.name, "counter_sales": location.counter_sales}


def _clean_location(location: StockLocation) -> None:
    errors: dict[str, str] = {}
    location.name = location.name.strip()
    if location.kind not in LocationKind.values:
        errors["kind"] = _("Type d'emplacement inconnu.")
    if not location.name:
        errors["name"] = _("Le nom est obligatoire.")
    elif (
        StockLocation.objects.for_organization(location.organization)
        .filter(name__iexact=location.name)
        .exclude(pk=location.pk)
        .exists()
    ):
        errors["name"] = _("Un autre emplacement porte déjà ce nom.")
    if location.kind == LocationKind.TRUCK:
        # A truck always sells; the flag only means something for the other kinds.
        location.counter_sales = False
    if errors:
        raise ValidationError(errors)


@transaction.atomic
def create_location(
    *, organization: Organization, actor: User | None, kind: str, name: str, counter_sales: bool = False
) -> StockLocation:
    """A new cold room or other location. A truck's location is made by `fleet.services.create_truck`."""
    location = StockLocation(organization=organization, kind=kind, name=name, counter_sales=counter_sales)
    _clean_location(location)
    location.save()
    audit.record(
        organization=organization, actor=actor, action="location.created", target=location, after=_snapshot(location)
    )
    return location


@transaction.atomic
def update_location(
    *, location: StockLocation, actor: User | None, name: str | None = None, counter_sales: bool | None = None
) -> StockLocation:
    """Rename a location or change whether it sells at the counter. Its kind never changes."""
    location = StockLocation.objects.select_for_update().get(pk=location.pk)
    before = _snapshot(location)
    if name is not None:
        location.name = name
    if counter_sales is not None:
        location.counter_sales = counter_sales
    _clean_location(location)
    location.save()
    after = _snapshot(location)
    changed = [field for field in after if after[field] != before[field]]
    if changed:
        audit.record(
            organization=location.organization,
            actor=actor,
            action="location.updated",
            target=location,
            before={field: before[field] for field in changed},
            after={field: after[field] for field in changed},
        )
    return location


@transaction.atomic
def set_location_active(*, location: StockLocation, actor: User | None, is_active: bool) -> StockLocation:
    """Archive a location (it keeps its history but receives no more stock), or bring it back.

    From P1-T06 on, a location still holding stock cannot be archived.
    """
    location = StockLocation.objects.select_for_update().get(pk=location.pk)
    if location.is_active != is_active:
        location.is_active = is_active
        location.save(update_fields=["is_active", "updated_at"])
        action = "location.restored" if is_active else "location.archived"
        audit.record(organization=location.organization, actor=actor, action=action, target=location)
    return location

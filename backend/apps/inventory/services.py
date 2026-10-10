"""Every write on stock locations, batches (and stock, from P1-T06) goes through these functions (ARCHITECTURE §3)."""

import datetime as dt
from typing import TYPE_CHECKING, Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core import audit
from apps.core.models import Organization, User
from apps.core.money import Number, checked_amount

from .models import Batch, BatchCounter, StockLocation
from .models import LocationKind as LocationKind  # re-exported for apps that create locations

if TYPE_CHECKING:
    from apps.catalog.models import Product
    from apps.partners.models import Supplier

BATCH_NUMBER_PREFIX = "L-"


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


def _next_batch_number(organization: Organization) -> str:
    """L-0001, L-0002... per organization, taken under a row lock so two receipts never share a number.

    Four digits at least, like the prototype's "L-0912"; the 10 000th batch is simply L-10000.
    """
    # Creates the counter the first time without failing when another transaction creates it at once.
    BatchCounter.objects.bulk_create([BatchCounter(organization=organization)], ignore_conflicts=True)
    counter = BatchCounter.objects.select_for_update().get(organization=organization)
    counter.last_number += 1
    counter.save(update_fields=["last_number"])
    return f"{BATCH_NUMBER_PREFIX}{counter.last_number:04d}"


def _batch_snapshot(batch: Batch) -> dict[str, Any]:
    return {
        "number": batch.number,
        "product": batch.product.reference,
        "supplier": batch.supplier.reference,
        "receipt_reference": batch.receipt_reference,
        "received_on": batch.received_on.isoformat(),
        "unit_cost": str(batch.unit_cost),
        "use_by": batch.use_by.isoformat() if batch.use_by else None,
    }


@transaction.atomic
def create_batch(
    *,
    organization: Organization,
    actor: User | None,
    product: "Product",
    supplier: "Supplier",
    received_on: dt.date,
    unit_cost: Number,
    receipt_reference: str = "",
    use_by: dt.date | None = None,
) -> Batch:
    """A new batch with the next number. Called by the goods receipt (P1-T07) and the demo data.

    Refused (ValidationError per field): a product or supplier of another organization or archived, a
    receipt date in the future, a cost that is negative or finer than a millime, a use-by date before
    the receipt date.
    """
    errors: dict[str, str] = {}
    if product.organization_id != organization.pk:
        errors["product"] = _("Produit inconnu.")
    elif not product.is_active:
        errors["product"] = _("Ce produit est archivé.")
    if supplier.organization_id != organization.pk:
        errors["supplier"] = _("Fournisseur inconnu.")
    elif not supplier.is_active:
        errors["supplier"] = _("Ce fournisseur est archivé.")
    if received_on > timezone.localdate():
        errors["received_on"] = _("La date de réception ne peut pas être dans le futur.")
    if use_by is not None and use_by < received_on:
        errors["use_by"] = _("La date limite ne peut pas précéder la réception.")
    cost = None
    try:
        cost = checked_amount(unit_cost)
    except ValueError as error:
        errors["unit_cost"] = str(error)
    if errors or cost is None:
        raise ValidationError(errors)

    batch = Batch.objects.create(
        organization=organization,
        number=_next_batch_number(organization),
        product=product,
        supplier=supplier,
        receipt_reference=receipt_reference.strip(),
        received_on=received_on,
        unit_cost=cost,
        use_by=use_by,
    )
    audit.record(
        organization=organization, actor=actor, action="batch.created", target=batch, after=_batch_snapshot(batch)
    )
    return batch

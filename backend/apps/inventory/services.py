"""Every write on stock locations, batches and stock movements goes through these functions (ARCHITECTURE §3)."""

import datetime as dt
import itertools
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import connection, models, transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core import audit
from apps.core.models import Organization, User
from apps.core.money import Number, checked_amount, checked_quantity

from . import selectors
from .models import FIFO_ORDER, Batch, BatchCounter, StockLocation, StockMovement, StockOnHand
from .models import LocationKind as LocationKind  # re-exported for apps that create locations
from .models import MovementKind as MovementKind  # re-exported for apps that post movements

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

    A location still holding stock cannot be archived: its stock is moved out first.
    """
    location = StockLocation.objects.select_for_update().get(pk=location.pk)
    if not is_active and StockOnHand.objects.filter(location=location, quantity__gt=0).exists():
        raise ValidationError(
            _("« %(name)s » contient encore du stock : videz-le avant de l'archiver.") % {"name": location.name}
        )
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


# Which side each kind of movement needs: (from a location, to a location). None: exactly one of the two,
# the side giving the direction (an adjustment or a count correction adds or removes).
MOVEMENT_SIDES: dict[str, tuple[bool, bool] | None] = {
    MovementKind.RECEIPT: (False, True),
    MovementKind.CUSTOMER_RETURN: (False, True),
    MovementKind.SALE: (True, False),
    MovementKind.SUPPLIER_RETURN: (True, False),
    MovementKind.LOSS: (True, False),
    MovementKind.TRANSFER: (True, True),
    MovementKind.ADJUSTMENT: None,
    MovementKind.COUNT_CORRECTION: None,
}
# A person must say why stock disappeared or was changed by hand.
KINDS_NEEDING_A_REASON = frozenset({MovementKind.LOSS, MovementKind.ADJUSTMENT})


def _locked_on_hand(location: StockLocation, batch: Batch) -> StockOnHand:
    """The on-hand row of this location and batch, created at zero when missing, locked until commit."""
    StockOnHand.objects.bulk_create(
        [
            StockOnHand(
                organization_id=location.organization_id, location=location, batch=batch, product_id=batch.product_id
            )
        ],
        ignore_conflicts=True,
    )
    return StockOnHand.objects.select_for_update().get(location=location, batch=batch)


def _movement_errors(
    organization: Organization,
    kind: str,
    batch: Batch,
    from_location: StockLocation | None,
    to_location: StockLocation | None,
    reason: str,
) -> dict[str, str]:
    if kind not in MOVEMENT_SIDES:
        return {"kind": _("Type de mouvement inconnu.")}
    errors: dict[str, str] = {}
    if batch.organization_id != organization.pk:
        errors["batch"] = _("Lot inconnu.")
    sides = MOVEMENT_SIDES[kind]
    if sides is None:
        if (from_location is None) == (to_location is None):
            errors["to_location"] = _("Indiquez un seul emplacement : celui qui gagne ou celui qui perd du stock.")
    else:
        needs_from, needs_to = sides
        for field, location, needed in (
            ("from_location", from_location, needs_from),
            ("to_location", to_location, needs_to),
        ):
            if needed and location is None:
                errors[field] = _("L'emplacement est obligatoire pour ce mouvement.")
            elif not needed and location is not None:
                errors[field] = _("Ce mouvement ne passe pas par cet emplacement.")
    if from_location is not None and from_location == to_location:
        errors["to_location"] = _("Les emplacements de départ et d'arrivée doivent être différents.")
    for field, location in (("from_location", from_location), ("to_location", to_location)):
        if location is None or field in errors:
            continue
        if location.organization_id != organization.pk:
            errors[field] = _("Emplacement inconnu.")
        elif not location.is_active:
            errors[field] = _("« %(name)s » est archivé.") % {"name": location.name}
    if kind in KINDS_NEEDING_A_REASON and not reason:
        errors["reason"] = _("Indiquez la raison.")
    return errors


@transaction.atomic
def post_movement(
    *,
    organization: Organization,
    actor: User | None,
    kind: str,
    batch: Batch,
    quantity: Number,
    from_location: StockLocation | None = None,
    to_location: StockLocation | None = None,
    reason: str = "",
    source: models.Model | None = None,
    client_uuid: uuid.UUID | None = None,
    occurred_at: dt.datetime | None = None,
) -> StockMovement:
    """Post one movement of one batch and update the stock on hand in the same transaction (D-006).

    The on-hand rows involved are locked, always in the same order so two movements never wait for each
    other forever; a location never goes below zero. A `client_uuid` already posted returns that movement
    instead of posting it twice. Refused with a ValidationError per field.
    """
    if client_uuid is not None:
        posted = StockMovement.objects.for_organization(organization).filter(client_uuid=client_uuid).first()
        if posted is not None:
            return posted

    reason = reason.strip()
    errors = _movement_errors(organization, kind, batch, from_location, to_location, reason)
    amount = None
    try:
        amount = checked_quantity(quantity)
    except ValueError as error:
        errors["quantity"] = str(error)
    if errors or amount is None:
        raise ValidationError(errors)

    involved = sorted((loc for loc in (from_location, to_location) if loc is not None), key=lambda loc: loc.pk)
    rows = {location.pk: _locked_on_hand(location, batch) for location in involved}
    if from_location is not None:
        source_row = rows[from_location.pk]
        if source_row.quantity < amount:
            raise ValidationError(
                {
                    "quantity": _("Stock insuffisant : %(available)s kg du lot %(batch)s à « %(location)s ».")
                    % {"available": source_row.quantity, "batch": batch.number, "location": from_location.name}
                }
            )
        source_row.quantity -= amount
        source_row.save(update_fields=["quantity", "updated_at"])
    if to_location is not None:
        target_row = rows[to_location.pk]
        target_row.quantity += amount
        target_row.save(update_fields=["quantity", "updated_at"])

    return StockMovement.objects.create(
        organization=organization,
        kind=kind,
        product_id=batch.product_id,
        batch=batch,
        from_location=from_location,
        to_location=to_location,
        quantity=amount,
        unit_cost=batch.unit_cost,
        source_type=ContentType.objects.get_for_model(source) if source is not None else None,
        source_id=source.pk if source is not None else None,
        user=actor,
        occurred_at=occurred_at or timezone.now(),
        reason=reason,
        client_uuid=client_uuid,
    )


def _part_uuid(client_uuid: uuid.UUID, index: int) -> uuid.UUID:
    """The `client_uuid` of the n-th movement posted for one request taken from several batches."""
    return uuid.uuid5(client_uuid, str(index))


def _posted_parts(organization: Organization, client_uuid: uuid.UUID) -> list[StockMovement]:
    movements = StockMovement.objects.for_organization(organization)
    posted: list[StockMovement] = []
    for index in itertools.count():
        movement = movements.filter(client_uuid=_part_uuid(client_uuid, index)).first()
        if movement is None:
            return posted
        posted.append(movement)
    return posted  # pragma: no cover - itertools.count never ends


@transaction.atomic
def post_fifo_movements(
    *,
    organization: Organization,
    actor: User | None,
    kind: str,
    product_id: int,
    quantity: Number,
    from_location: StockLocation,
    to_location: StockLocation | None = None,
    reason: str = "",
    source: models.Model | None = None,
    client_uuid: uuid.UUID | None = None,
    occurred_at: dt.datetime | None = None,
) -> list[StockMovement]:
    """Take `quantity` kg of a product out of `from_location`, oldest batch first, one movement per batch.

    Used by transfers, sales and losses: nobody picks batches by hand (D-009). Every on-hand row of the
    product at both locations is locked first, in location then batch order, the same order as
    `post_movement`, so two requests never wait for each other forever. Refused as a whole (ValidationError
    per field) when the location holds less than asked. A `client_uuid` already used returns the
    movements it posted.
    """
    if client_uuid is not None:
        posted = _posted_parts(organization, client_uuid)
        if posted:
            return posted
    sides = MOVEMENT_SIDES.get(kind)
    if sides is not None and not sides[0]:
        raise ValidationError({"kind": _("Ce mouvement ne prend pas de stock à un emplacement.")})
    if from_location.organization_id != organization.pk:
        raise ValidationError({"from_location": _("Emplacement inconnu.")})
    try:
        amount = checked_quantity(quantity)
    except ValueError as error:
        raise ValidationError({"quantity": str(error)}) from None

    locations = [location for location in (from_location, to_location) if location is not None]
    locked = (
        StockOnHand.objects.select_for_update(of=("self",))
        .filter(product_id=product_id, location__in=locations)
        .select_related("batch")
        .order_by("location_id", "batch_id")
    )
    holdings = sorted(
        (row for row in locked if row.location_id == from_location.pk and row.quantity > 0),
        key=lambda row: tuple(getattr(row.batch, field) for field in FIFO_ORDER),
    )
    allocations = selectors.fifo_split(holdings, amount)
    if sum((taken for _batch, taken in allocations), Decimal(0)) < amount:
        raise selectors.not_enough_stock(sum((row.quantity for row in holdings), Decimal("0.000")), from_location)

    return [
        post_movement(
            organization=organization,
            actor=actor,
            kind=kind,
            batch=batch,
            quantity=taken,
            from_location=from_location,
            to_location=to_location,
            reason=reason,
            source=source,
            client_uuid=_part_uuid(client_uuid, index) if client_uuid is not None else None,
            occurred_at=occurred_at,
        )
        for index, (batch, taken) in enumerate(allocations)
    ]


@transaction.atomic
def rebuild_on_hand(*, organization: Organization, actor: User | None) -> list[selectors.OnHandDifference]:
    """Set the stock on hand of every location and batch back to the sum of its movements (D-038).

    The ledger is the truth; the cache only speeds up reading it. Returns what was wrong, empty when
    nothing was. Writes are blocked on the cache (of every organization) for the few milliseconds this
    takes: `post_movement` updates the cache before it writes its movement, so a movement either finished
    before the rebuild or starts after it, never in the middle. Reads are not blocked.
    """
    with connection.cursor() as cursor:
        cursor.execute(f"LOCK TABLE {StockOnHand._meta.db_table} IN EXCLUSIVE MODE")
    differences = selectors.on_hand_differences(organization)
    if not differences:
        return []
    negative = [difference for difference in differences if difference.ledger < 0]
    if negative:
        # Movements are checked before posting, so this cannot happen without editing the database by hand.
        raise ValidationError(
            _("Le journal donne un stock négatif pour %(count)s ligne(s) : réparation impossible, à examiner.")
            % {"count": len(negative)}
        )
    for difference in differences:
        row, _created = StockOnHand.objects.get_or_create(
            location_id=difference.location_id,
            batch_id=difference.batch_id,
            defaults={"organization": organization, "product_id": difference.product_id},
        )
        row.quantity = difference.ledger
        row.save(update_fields=["quantity", "updated_at"])
    audit.record(
        organization=organization,
        actor=actor,
        action="stock.on_hand_rebuilt",
        before={"rows": [_difference_entry(difference, difference.cached) for difference in differences]},
        after={"rows": [_difference_entry(difference, difference.ledger) for difference in differences]},
    )
    return differences


def _difference_entry(difference: selectors.OnHandDifference, quantity: Decimal) -> dict[str, Any]:
    return {"location": difference.location_id, "batch": difference.batch_id, "quantity": quantity}

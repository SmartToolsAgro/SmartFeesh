"""Reusable read queries of stock locations, batches, movements and stock on hand."""

from collections.abc import Iterable, Sequence
from decimal import Decimal
from typing import Literal

from django.core.exceptions import ValidationError
from django.db.models import Q, QuerySet, Sum
from django.utils.translation import gettext as _

from apps.core.models import Organization
from apps.core.money import Number, checked_quantity

from .models import FIFO_ORDER, Batch, LocationKind, StockLocation, StockMovement, StockOnHand

type LocationStatus = Literal["active", "archived", "all"]


def locations_of(
    organization: Organization,
    *,
    kinds: Iterable[str] | None = None,
    status: LocationStatus = "active",
) -> QuerySet[StockLocation]:
    """Locations of one organization: cold rooms first, then trucks, then the others, each sorted by name."""
    locations = StockLocation.objects.for_organization(organization).order_by("kind", "name", "id")
    if kinds is not None:
        locations = locations.filter(kind__in=list(kinds))
    if status == "active":
        locations = locations.filter(is_active=True)
    elif status == "archived":
        locations = locations.filter(is_active=False)
    return locations


def location_of(organization: Organization, location_id: int) -> StockLocation:
    """One location. Raises StockLocation.DoesNotExist outside the organization."""
    return StockLocation.objects.for_organization(organization).get(pk=location_id)


# Kinds managed on their own; a truck's location is managed through its truck (fleet).
STANDALONE_KINDS = (LocationKind.COLD_ROOM, LocationKind.OTHER)


def batches_of(
    organization: Organization,
    *,
    product_id: int | None = None,
    supplier_id: int | None = None,
    search: str = "",
) -> QuerySet[Batch]:
    """Batches of one organization, newest first, with their product and supplier.

    `search` matches the batch number, the supplier's receipt reference, and the product or supplier
    name or reference.
    """
    batches = (
        Batch.objects.for_organization(organization)
        .select_related("product", "supplier")
        .order_by("-received_on", "-id")
    )
    if product_id is not None:
        batches = batches.filter(product_id=product_id)
    if supplier_id is not None:
        batches = batches.filter(supplier_id=supplier_id)
    if search := search.strip():
        batches = batches.filter(
            Q(number__icontains=search)
            | Q(receipt_reference__icontains=search)
            | Q(product__name__icontains=search)
            | Q(product__reference__icontains=search)
            | Q(supplier__name__icontains=search)
            | Q(supplier__reference__icontains=search)
        )
    return batches


def batch_of(organization: Organization, batch_id: int) -> Batch:
    """One batch. Raises Batch.DoesNotExist outside the organization."""
    return batches_of(organization).get(pk=batch_id)


def batches_oldest_first(organization: Organization, *, product_id: int) -> QuerySet[Batch]:
    """A product's batches in the order stock leaves them: oldest receipt first (D-009, Q7).

    The FIFO allocation of P1-T06 walks this order over the batches that still have stock.
    """
    return Batch.objects.for_organization(organization).filter(product_id=product_id).order_by(*FIFO_ORDER)


def on_hand_of(
    organization: Organization,
    *,
    location_id: int | None = None,
    product_id: int | None = None,
    batch_id: int | None = None,
) -> QuerySet[StockOnHand]:
    """What each location holds now, per batch, from the cache. Empty rows are left out."""
    rows = (
        StockOnHand.objects.for_organization(organization)
        .filter(quantity__gt=0)
        .select_related("location", "batch", "batch__product", "batch__supplier")
        .order_by("location__kind", "location__name", "batch__received_on", "batch_id")
    )
    if location_id is not None:
        rows = rows.filter(location_id=location_id)
    if product_id is not None:
        rows = rows.filter(product_id=product_id)
    if batch_id is not None:
        rows = rows.filter(batch_id=batch_id)
    return rows


def quantity_on_hand(
    organization: Organization,
    *,
    location_id: int | None = None,
    product_id: int | None = None,
    batch_id: int | None = None,
) -> Decimal:
    """Total kg held, for one location, product or batch (or any mix of the three)."""
    total = on_hand_of(organization, location_id=location_id, product_id=product_id, batch_id=batch_id).aggregate(
        total=Sum("quantity")
    )["total"]
    return total if total is not None else Decimal("0.000")


def movements_of(
    organization: Organization,
    *,
    location_id: int | None = None,
    product_id: int | None = None,
    batch_id: int | None = None,
) -> QuerySet[StockMovement]:
    """The ledger, newest first. A location filter keeps movements coming in or going out of it."""
    movements = (
        StockMovement.objects.for_organization(organization)
        .select_related("batch", "product", "from_location", "to_location", "user")
        .order_by("-occurred_at", "-id")
    )
    if location_id is not None:
        movements = movements.filter(Q(from_location_id=location_id) | Q(to_location_id=location_id))
    if product_id is not None:
        movements = movements.filter(product_id=product_id)
    if batch_id is not None:
        movements = movements.filter(batch_id=batch_id)
    return movements


# One part of a quantity taken from one batch.
type Allocation = tuple[Batch, Decimal]


def holdings_oldest_first(organization: Organization, *, product_id: int, location_id: int) -> QuerySet[StockOnHand]:
    """What one location holds of one product, per batch, in the order it leaves: oldest receipt first."""
    return (
        StockOnHand.objects.for_organization(organization)
        .filter(product_id=product_id, location_id=location_id, quantity__gt=0)
        .select_related("batch")
        .order_by(*(f"batch__{field}" for field in FIFO_ORDER))
    )


def fifo_split(holdings: Sequence[StockOnHand], quantity: Decimal) -> list[Allocation]:
    """Take `quantity` from `holdings` (already oldest first), emptying each batch before the next.

    Returns less than asked when the holdings are not enough; the caller decides what that means.
    """
    allocations: list[Allocation] = []
    left = quantity
    for row in holdings:
        if left <= 0:
            break
        taken = min(row.quantity, left)
        if taken > 0:
            allocations.append((row.batch, taken))
            left -= taken
    return allocations


def not_enough_stock(available: Decimal, location: StockLocation) -> ValidationError:
    return ValidationError(
        {
            "quantity": _("Stock insuffisant : %(available)s kg à « %(location)s ».")
            % {"available": available, "location": location.name}
        }
    )


def allocate_fifo(
    organization: Organization, *, product_id: int, location: StockLocation, quantity: Number
) -> list[Allocation]:
    """Which batches `quantity` kg of a product would come from at `location`: oldest first (D-009, Q7).

    A preview: nothing is locked or posted (`services.post_fifo_movements` does both). Refused with a
    ValidationError on `quantity` when the location holds less, or when the quantity is not valid.
    """
    try:
        amount = checked_quantity(quantity)
    except ValueError as error:
        raise ValidationError({"quantity": str(error)}) from None
    holdings = list(holdings_oldest_first(organization, product_id=product_id, location_id=location.pk))
    allocations = fifo_split(holdings, amount)
    if sum((taken for _batch, taken in allocations), Decimal(0)) < amount:
        raise not_enough_stock(sum((row.quantity for row in holdings), Decimal("0.000")), location)
    return allocations

"""Reusable read queries of stock locations, batches, movements and stock on hand."""

from collections.abc import Iterable
from decimal import Decimal
from typing import Literal

from django.db.models import Q, QuerySet, Sum

from apps.core.models import Organization

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

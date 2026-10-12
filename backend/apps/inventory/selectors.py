"""Reusable read queries of stock locations, batches, movements and stock on hand."""

import datetime as dt
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import Prefetch, Q, QuerySet, Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.catalog import selectors as catalog
from apps.core.models import Organization
from apps.core.money import Number, checked_quantity, line_total, money

from .models import (
    FIFO_ORDER,
    Batch,
    LocationKind,
    StockCount,
    StockCountLine,
    StockLocation,
    StockLoss,
    StockMovement,
    StockOnHand,
    StockSettings,
    Transfer,
    TransferLine,
    TransferStatus,
)

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


def last_batches_from(organization: Organization, *, supplier_id: int) -> QuerySet[Batch]:
    """The latest batch of each product bought from one supplier: what was last paid for it (D-020).

    The receipt form suggests this cost and shows the change against it (P1-T07).
    """
    return (
        Batch.objects.for_organization(organization)
        .filter(supplier_id=supplier_id)
        .select_related("product")
        .order_by("product_id", "-received_on", "-id")
        .distinct("product_id")
    )


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
    kind: str | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> QuerySet[StockMovement]:
    """The ledger, newest first. A location filter keeps movements coming in or going out of it; the
    dates (inclusive, local days) filter on when the movement happened."""
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
    if kind:
        movements = movements.filter(kind=kind)
    if date_from is not None:
        movements = movements.filter(occurred_at__date__gte=date_from)
    if date_to is not None:
        movements = movements.filter(occurred_at__date__lte=date_to)
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


@dataclass(frozen=True)
class OnHandDifference:
    """One location and batch whose cached stock does not match the sum of its movements."""

    location_id: int
    batch_id: int
    product_id: int
    cached: Decimal
    ledger: Decimal


# One statement, so the movements and the cache are read from the same snapshot: a movement posted while
# the check runs is either fully in both or in neither (it and its on-hand change commit together).
_DIFFERENCES_SQL = f"""
WITH moves AS (
    SELECT to_location_id AS location_id, batch_id, product_id, quantity AS change
      FROM {StockMovement._meta.db_table}
     WHERE organization_id = %(organization)s AND to_location_id IS NOT NULL
    UNION ALL
    SELECT from_location_id, batch_id, product_id, -quantity
      FROM {StockMovement._meta.db_table}
     WHERE organization_id = %(organization)s AND from_location_id IS NOT NULL
), ledger AS (
    SELECT location_id, batch_id, product_id, SUM(change) AS quantity FROM moves GROUP BY 1, 2, 3
), cache AS (
    SELECT location_id, batch_id, product_id, quantity
      FROM {StockOnHand._meta.db_table}
     WHERE organization_id = %(organization)s
)
SELECT COALESCE(ledger.location_id, cache.location_id),
       COALESCE(ledger.batch_id, cache.batch_id),
       COALESCE(ledger.product_id, cache.product_id),
       COALESCE(cache.quantity, 0),
       COALESCE(ledger.quantity, 0)
  FROM ledger
  FULL OUTER JOIN cache ON cache.location_id = ledger.location_id AND cache.batch_id = ledger.batch_id
 WHERE COALESCE(cache.quantity, 0) <> COALESCE(ledger.quantity, 0)
 ORDER BY 1, 2
"""


def on_hand_differences(organization: Organization) -> list[OnHandDifference]:
    """Every place where the stock on hand differs from what the ledger says (D-006, D-038).

    Empty when the cache is right, which it always should be: `post_movement` updates both together.
    A difference means someone changed the database by hand, or a bug; `rebuild_on_hand` repairs it.
    """
    with connection.cursor() as cursor:
        cursor.execute(_DIFFERENCES_SQL, {"organization": organization.pk})
        return [OnHandDifference(*row) for row in cursor.fetchall()]


def location_stock(organization: Organization, *, location_id: int) -> list[dict[str, Any]]:
    """What one location holds per product (all batches together), by product name: `product_id`,
    `product__reference`, `product__name`, `quantity`. Products it does not hold are left out."""
    rows = (
        StockOnHand.objects.for_organization(organization)
        .filter(location_id=location_id, quantity__gt=0)
        .values("product_id", "product__reference", "product__name")
        .annotate(quantity=Sum("quantity"))
        .order_by("product__name", "product_id")
    )
    return [dict(row) for row in rows]


def movements_from_sources(sources: Sequence[Any]) -> dict[int, list[StockMovement]]:
    """The movements posted for each of these documents or lines (all of one model), by their id, in
    the order they were posted: which batches a transfer line, a loss or a count took (D-037)."""
    if not sources:
        return {}
    source_type = ContentType.objects.get_for_model(type(sources[0]))
    found: dict[int, list[StockMovement]] = defaultdict(list)
    for movement in (
        StockMovement.objects.filter(source_type=source_type, source_id__in=[source.pk for source in sources])
        .select_related("batch")
        .order_by("id")
    ):
        assert movement.source_id is not None  # filtered on it
        found[movement.source_id].append(movement)
    return found


# ---- Transfers between locations (P1-T09, D-044) ----


def transfers_of(
    organization: Organization,
    *,
    kind: str | None = None,
    status: str | None = None,
    location_id: int | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    search: str = "",
) -> QuerySet[Transfer]:
    """Transfers newest day first, with their places and lines (product). A location filter keeps the
    transfers going out of it or coming into it; `search` matches the number and the places' names."""
    lines = TransferLine.objects.select_related("product").order_by("id")
    transfers = (
        Transfer.objects.for_organization(organization)
        .select_related("from_location", "to_location", "created_by", "validated_by", "confirmed_by")
        .prefetch_related(Prefetch("lines", queryset=lines))
        .order_by("-transferred_on", "-id")
    )
    if kind:
        transfers = transfers.filter(kind=kind)
    if status:
        transfers = transfers.filter(status=status)
    if location_id is not None:
        transfers = transfers.filter(Q(from_location_id=location_id) | Q(to_location_id=location_id))
    if date_from is not None:
        transfers = transfers.filter(transferred_on__gte=date_from)
    if date_to is not None:
        transfers = transfers.filter(transferred_on__lte=date_to)
    if search := search.strip():
        transfers = transfers.filter(
            Q(number__icontains=search)
            | Q(from_location__name__icontains=search)
            | Q(to_location__name__icontains=search)
        )
    return transfers


def transfer_of(organization: Organization, transfer_id: int) -> Transfer:
    """One transfer with its lines. Raises Transfer.DoesNotExist outside the organization."""
    return transfers_of(organization).get(pk=transfer_id)


@dataclass(frozen=True)
class TruckDayLine:
    """One product of a truck's day: kg loaded, kg brought back, and the difference, sold or lost."""

    product_id: int
    product_reference: str
    product_name: str
    loaded: Decimal
    returned: Decimal
    # The day's sale price per kg, from its last load (empty when nothing was loaded).
    unit_price: Decimal | None

    @property
    def sold_or_lost(self) -> Decimal:
        """Loaded − returned (client meeting 2026-10-11). Negative when more came back than was loaded
        that day: the truck already held some in the morning."""
        return self.loaded - self.returned

    @property
    def amount(self) -> Decimal | None:
        """What the kg sold or lost are worth at the day's price; empty without a price or a positive difference."""
        if self.unit_price is None or self.sold_or_lost <= 0:
            return None
        return line_total(self.sold_or_lost, self.unit_price)


def truck_day(organization: Organization, *, location_id: int, day: dt.date) -> list[TruckDayLine]:
    """A truck's day per product from the validated transfers of that day: loaded (into the truck),
    returned (out of it), and loaded − returned, sold or lost. Works for any location; it means
    something for a truck. Products sorted by name."""
    lines = (
        TransferLine.objects.for_organization(organization)
        .filter(transfer__status=TransferStatus.VALIDATED, transfer__transferred_on=day)
        .filter(Q(transfer__to_location_id=location_id) | Q(transfer__from_location_id=location_id))
        .select_related("product", "transfer")
        .order_by("transfer__validated_at", "transfer_id", "id")
    )
    totals: dict[int, dict[str, Any]] = {}
    for line in lines:
        entry = totals.setdefault(
            line.product_id,
            {"product": line.product, "loaded": Decimal("0.000"), "returned": Decimal("0.000"), "price": None},
        )
        if line.transfer.to_location_id == location_id:
            entry["loaded"] += line.quantity
            if line.unit_price is not None:
                # Lines come in validation order: the last load's price is the day's price.
                entry["price"] = line.unit_price
        else:
            entry["returned"] += line.quantity
    return sorted(
        (
            TruckDayLine(
                product_id=product_id,
                product_reference=entry["product"].reference,
                product_name=entry["product"].name,
                loaded=entry["loaded"],
                returned=entry["returned"],
                unit_price=entry["price"],
            )
            for product_id, entry in totals.items()
        ),
        key=lambda line: (line.product_name, line.product_id),
    )


# ---- Losses and stock counts (P1-T10, D-045) ----


def stock_settings(organization: Organization) -> StockSettings:
    """The organization's stock rules; the defaults (not saved) when the owner never changed them."""
    found = StockSettings.objects.for_organization(organization).first()
    return found if found is not None else StockSettings(organization=organization)


def losses_of(
    organization: Organization,
    *,
    status: str | None = None,
    location_id: int | None = None,
    search: str = "",
) -> QuerySet[StockLoss]:
    """Losses newest day first, with location and product. `search` matches the number, the product
    and the location."""
    losses = (
        StockLoss.objects.for_organization(organization)
        .select_related("location", "product", "created_by", "decided_by")
        .order_by("-lost_on", "-id")
    )
    if status:
        losses = losses.filter(status=status)
    if location_id is not None:
        losses = losses.filter(location_id=location_id)
    if search := search.strip():
        losses = losses.filter(
            Q(number__icontains=search)
            | Q(product__name__icontains=search)
            | Q(product__reference__icontains=search)
            | Q(location__name__icontains=search)
        )
    return losses


def loss_of(organization: Organization, loss_id: int) -> StockLoss:
    """One loss. Raises StockLoss.DoesNotExist outside the organization."""
    return losses_of(organization).get(pk=loss_id)


# The order of a count sheet's lines, on the screen and in the `lines.<index>` of its errors.
COUNT_SHEET_ORDER = ("product__name", "batch__received_on", "id")


def counts_of(
    organization: Organization, *, status: str | None = None, location_id: int | None = None
) -> QuerySet[StockCount]:
    """Stock counts newest first, with their location and lines (batch and product)."""
    lines = StockCountLine.objects.select_related("batch", "product").order_by(*COUNT_SHEET_ORDER)
    counts = (
        StockCount.objects.for_organization(organization)
        .select_related("location", "created_by", "approved_by")
        .prefetch_related(Prefetch("lines", queryset=lines))
        .order_by("-counted_on", "-id")
    )
    if status:
        counts = counts.filter(status=status)
    if location_id is not None:
        counts = counts.filter(location_id=location_id)
    return counts


def count_of(organization: Organization, count_id: int) -> StockCount:
    """One count with its sheet. Raises StockCount.DoesNotExist outside the organization."""
    return counts_of(organization).get(pk=count_id)


# ---- Stock screens (P1-T11, D-048) ----


@dataclass(frozen=True)
class LocationTotal:
    """What one location holds now: kg of everything, and what that cost (kg × each batch's unit cost)."""

    location: StockLocation
    quantity: Decimal
    value: Decimal


@dataclass(frozen=True)
class ProductStock:
    """One product's stock across the locations, with its purchase prices.

    `average_cost` is the cost per kg weighted by the kg still on hand over every batch; `last_cost` is the
    unit cost of the latest batch received. Both are for pricing information only: a sale is still valued
    FIFO per batch (D-040).
    """

    product: Any
    quantity: Decimal
    by_location: dict[int, Decimal]
    average_cost: Decimal | None
    last_cost: Decimal | None

    @property
    def is_low(self) -> bool:
        """Under the product's minimum stock (never for a product without one)."""
        return bool(self.product.min_stock > 0 and self.quantity < self.product.min_stock)


@dataclass(frozen=True)
class BatchHolding:
    """A batch still on hand: its kg in total and per location, and their cost."""

    batch: Batch
    quantity: Decimal
    value: Decimal
    by_location: list[tuple[StockLocation, Decimal]]


def _holdings(organization: Organization, *, product_id: int | None = None) -> list[StockOnHand]:
    rows = (
        StockOnHand.objects.for_organization(organization)
        .filter(quantity__gt=0)
        .select_related("location", "batch", "batch__supplier")
        .order_by("location__kind", "location__name", "batch__received_on", "batch_id")
    )
    if product_id is not None:
        rows = rows.filter(product_id=product_id)
    return list(rows)


def last_costs(organization: Organization, *, product_id: int | None = None) -> dict[int, Decimal]:
    """The unit cost of the latest batch of each product (by receipt date, then number of creation)."""
    batches = Batch.objects.for_organization(organization).order_by("product_id", "-received_on", "-id")
    if product_id is not None:
        batches = batches.filter(product_id=product_id)
    return {batch.product_id: batch.unit_cost for batch in batches.distinct("product_id")}


def _average(rows: Iterable[StockOnHand]) -> Decimal | None:
    kg = Decimal(0)
    cost = Decimal(0)
    for row in rows:
        kg += row.quantity
        cost += row.quantity * row.batch.unit_cost
    return money(cost / kg) if kg > 0 else None


def average_purchase_cost(organization: Organization, *, product_id: int) -> Decimal | None:
    """Cost per kg of a product weighted by the kg of each batch still on hand; empty without stock."""
    return _average(_holdings(organization, product_id=product_id))


def location_totals(organization: Organization) -> list[LocationTotal]:
    """Every active location (cold rooms first, then trucks) with the kg and cost it holds."""
    kg: dict[int, Decimal] = defaultdict(lambda: Decimal("0.000"))
    value: dict[int, Decimal] = defaultdict(lambda: Decimal("0.000"))
    for row in _holdings(organization):
        kg[row.location_id] += row.quantity
        value[row.location_id] += line_total(row.quantity, row.batch.unit_cost)
    return [
        LocationTotal(location=location, quantity=kg[location.pk], value=value[location.pk])
        for location in locations_of(organization)
    ]


def _product_stocks(
    organization: Organization, products: Sequence[Any], rows: Sequence[StockOnHand]
) -> list[ProductStock]:
    by_product: dict[int, list[StockOnHand]] = defaultdict(list)
    for row in rows:
        by_product[row.product_id].append(row)
    last = last_costs(organization)
    stocks: list[ProductStock] = []
    for product in products:
        held = by_product.get(product.pk, [])
        by_location: dict[int, Decimal] = defaultdict(lambda: Decimal("0.000"))
        for row in held:
            by_location[row.location_id] += row.quantity
        stocks.append(
            ProductStock(
                product=product,
                quantity=sum(by_location.values(), Decimal("0.000")),
                by_location=dict(by_location),
                average_cost=_average(held),
                last_cost=last.get(product.pk),
            )
        )
    return stocks


def product_stocks(organization: Organization) -> list[ProductStock]:
    """The products the stock page shows, by name: those holding stock, and the active ones with a
    minimum stock (so an empty shelf still shows as low)."""
    rows = _holdings(organization)
    held = {row.product_id for row in rows}
    products = [
        product
        for product in catalog.products_of(organization, status="all")
        if product.pk in held or (product.is_active and product.min_stock > 0)
    ]
    return _product_stocks(organization, products, rows)


def product_stock(organization: Organization, product_id: int) -> ProductStock:
    """One product's stock. Raises Product.DoesNotExist outside the organization."""
    product = catalog.product_of(organization, product_id)
    return _product_stocks(organization, [product], _holdings(organization, product_id=product_id))[0]


def batch_holdings(organization: Organization, *, product_id: int) -> list[BatchHolding]:
    """The batches of a product still on hand, oldest first (the order they leave in)."""
    per_batch: dict[int, list[StockOnHand]] = defaultdict(list)
    for row in _holdings(organization, product_id=product_id):
        per_batch[row.batch_id].append(row)
    holdings = [
        BatchHolding(
            batch=rows[0].batch,
            quantity=sum((row.quantity for row in rows), Decimal("0.000")),
            value=sum((line_total(row.quantity, row.batch.unit_cost) for row in rows), Decimal("0.000")),
            by_location=[(row.location, row.quantity) for row in rows],
        )
        for rows in per_batch.values()
    ]
    return sorted(holdings, key=lambda holding: (holding.batch.received_on, holding.batch.pk))


# ---- Lots on a truck's day, for the truck costs of the day (P5-T01, D-053) ----


@dataclass(frozen=True)
class BatchLoad:
    """Kilos of one lot loaded into a place on one day by validated transfers."""

    batch_id: int
    batch_number: str
    product_name: str
    quantity: Decimal


def _validated_transfer_lines(organization: Organization) -> QuerySet[TransferLine]:
    return TransferLine.objects.for_organization(organization).filter(transfer__status=TransferStatus.VALIDATED)


def batches_loaded(organization: Organization, *, location_id: int, day: dt.date) -> list[BatchLoad]:
    """The lots loaded into a place (a truck) on a day, with their kg, by lot number.

    Read from the movements that the validated transfers of that day posted into the place (FIFO picked
    the lots, D-037): loads from a cold room and transfers from another truck. What came back the same
    evening is not taken off (D-041: split by kg loaded).
    """
    lines = _validated_transfer_lines(organization).filter(
        transfer__transferred_on=day, transfer__to_location_id=location_id
    )
    rows = (
        StockMovement.objects.for_organization(organization)
        .filter(
            source_type=ContentType.objects.get_for_model(TransferLine),
            source_id__in=lines.values("id"),
            to_location_id=location_id,
        )
        .values("batch_id", "batch__number", "product__name")
        .annotate(quantity=Sum("quantity"))
        .order_by("batch__number", "batch_id")
    )
    return [
        BatchLoad(
            batch_id=row["batch_id"],
            batch_number=row["batch__number"],
            product_name=row["product__name"],
            quantity=row["quantity"],
        )
        for row in rows
        if row["quantity"] > 0
    ]


def truck_days_of_batch(organization: Organization, *, batch_id: int) -> list[tuple[int, dt.date]]:
    """The (truck location, day) pairs on which a lot was loaded into a truck by a validated transfer,
    oldest first: the days whose truck costs it shares."""
    movements = StockMovement.objects.for_organization(organization).filter(
        batch_id=batch_id,
        source_type=ContentType.objects.get_for_model(TransferLine),
        to_location__kind=LocationKind.TRUCK,
    )
    pairs = (
        _validated_transfer_lines(organization)
        .filter(id__in=movements.values("source_id"), transfer__to_location__kind=LocationKind.TRUCK)
        .values_list("transfer__to_location_id", "transfer__transferred_on")
        .distinct()
        .order_by("transfer__transferred_on", "transfer__to_location_id")
    )
    return [(location_id, day) for location_id, day in pairs]


# ---- Kilos held on each day, replayed from the ledger (P5-T02, P5-T05, D-058) ----

# The key of the company-wide balances in `kg_by_batch_by_day` (every place together).
EVERYWHERE = 0


def _local_day(moment: dt.datetime) -> dt.date:
    return timezone.localtime(moment).date()


def first_movement_day(organization: Organization, *, batch_id: int) -> dt.date | None:
    """The day of the first movement of a lot (its receipt), or None when it never moved."""
    first = (
        StockMovement.objects.for_organization(organization)
        .filter(batch_id=batch_id)
        .order_by("occurred_at", "id")
        .values_list("occurred_at", flat=True)
        .first()
    )
    return _local_day(first) if first is not None else None


def kg_by_batch_by_day(
    organization: Organization,
    *,
    date_from: dt.date,
    date_to: dt.date,
    location_ids: Sequence[int] | None = None,
) -> dict[int, dict[dt.date, dict[int, Decimal]]]:
    """Kilos of each lot held at the **end of each day** from `date_from` to `date_to` (inclusive), by
    replaying the append-only ledger by date: `{location id: {day: {batch id: kg}}}`.

    With `location_ids`, one entry per place (what is in that place). Without, one entry under
    `EVERYWHERE` with what the company holds in all places together (transfers between places cancel
    out; receipts add, sales and losses take off). Lots with nothing left are left out of a day. The day
    of a movement is its local date. Read-only: stock is never written here (D-035).
    """
    end = timezone.make_aware(dt.datetime.combine(date_to + dt.timedelta(days=1), dt.time.min))
    movements = StockMovement.objects.for_organization(organization).filter(occurred_at__lt=end)
    if location_ids is not None:
        movements = movements.filter(Q(from_location_id__in=location_ids) | Q(to_location_id__in=location_ids))
    keys = list(location_ids) if location_ids is not None else [EVERYWHERE]
    zero = Decimal("0.000")
    opening: dict[int, dict[int, Decimal]] = {key: {} for key in keys}
    deltas: dict[int, dict[dt.date, dict[int, Decimal]]] = {key: defaultdict(dict) for key in keys}

    def move(key: int, day: dt.date, batch_id: int, change: Decimal) -> None:
        if day < date_from:
            opening[key][batch_id] = opening[key].get(batch_id, zero) + change
        else:
            deltas[key][day][batch_id] = deltas[key][day].get(batch_id, zero) + change

    rows = movements.order_by("occurred_at", "id").values_list(
        "batch_id", "from_location_id", "to_location_id", "quantity", "occurred_at"
    )
    for batch_id, from_id, to_id, kg, occurred_at in rows:
        day = _local_day(occurred_at)
        if location_ids is None:
            if to_id is not None:
                move(EVERYWHERE, day, batch_id, kg)
            if from_id is not None:
                move(EVERYWHERE, day, batch_id, -kg)
        else:
            if to_id in opening:
                move(to_id, day, batch_id, kg)
            if from_id in opening:
                move(from_id, day, batch_id, -kg)

    result: dict[int, dict[dt.date, dict[int, Decimal]]] = {}
    for key in keys:
        balance = dict(opening[key])
        days: dict[dt.date, dict[int, Decimal]] = {}
        day = date_from
        while day <= date_to:
            for batch_id, change in deltas[key].get(day, {}).items():
                balance[batch_id] = balance.get(batch_id, zero) + change
            days[day] = {batch_id: kg for batch_id, kg in balance.items() if kg > 0}
            day += dt.timedelta(days=1)
        result[key] = days
    return result


def kg_by_batch_on_day(organization: Organization, *, location_id: int, day: dt.date) -> dict[int, Decimal]:
    """Kilos of each lot in one place at the end of a day (empty lots left out), replayed from the ledger."""
    return kg_by_batch_by_day(organization, date_from=day, date_to=day, location_ids=[location_id])[location_id][day]


def return_destination(organization: Organization, *, truck_location_id: int) -> StockLocation | None:
    """Where a truck's unsold stock goes back to: the cold room of its latest validated load, else the first
    active cold room by name."""
    last_load = (
        Transfer.objects.for_organization(organization)
        .filter(
            to_location_id=truck_location_id,
            status=TransferStatus.VALIDATED,
            from_location__kind=LocationKind.COLD_ROOM,
            from_location__is_active=True,
        )
        .select_related("from_location")
        .order_by("-validated_at", "-id")
        .first()
    )
    if last_load is not None:
        return last_load.from_location
    return (
        StockLocation.objects.for_organization(organization)
        .filter(kind=LocationKind.COLD_ROOM, is_active=True)
        .order_by("name", "id")
        .first()
    )

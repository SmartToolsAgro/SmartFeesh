"""Read helpers for returnable boxes. Every read is scoped to one organization."""

import datetime as dt
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db.models import Q, QuerySet, Sum
from django.db.models.functions import Coalesce

from apps.core.models import Organization

from .models import BoxHolder, BoxMovement, BoxMovementKind, BoxType

if TYPE_CHECKING:
    from apps.inventory.models import StockLocation


@dataclass(frozen=True)
class BoxBalance:
    holder: BoxHolder
    box_type: str
    count: int


@dataclass(frozen=True)
class TruckBoxDay:
    """One box type on one truck: what came, what went to clients, what came back on `day`, and what the truck
    holds now (`expected`, the real ledger balance over all days, P1-T14e decision 2)."""

    box_type: str
    loaded: int
    left: int
    collected: int
    expected: int


def _holder_totals(organization: Organization) -> dict[tuple[int, str], tuple[int, int]]:
    """Per (holder, box type): (boxes that arrived, boxes that left), summed in the database."""
    totals: dict[tuple[int, str], tuple[int, int]] = {}
    arrived = (
        BoxMovement.objects.for_organization(organization)
        .exclude(to_holder=None)
        .order_by()
        .values_list("to_holder_id", "box_type")
        .annotate(total=Sum("count"))
    )
    left = (
        BoxMovement.objects.for_organization(organization)
        .exclude(from_holder=None)
        .order_by()
        .values_list("from_holder_id", "box_type")
        .annotate(total=Sum("count"))
    )
    for holder_id, box_type, total in arrived:
        key = (holder_id, box_type)
        totals[key] = (total, totals.get(key, (0, 0))[1])
    for holder_id, box_type, total in left:
        key = (holder_id, box_type)
        totals[key] = (totals.get(key, (0, 0))[0], total)
    return totals


def _balance_from_totals(holder: BoxHolder, arrived: int, left: int) -> int:
    """Boxes the holder has. A supplier's balance is what we owe it: the boxes it lent us."""
    if holder.target_kind == "supplier":
        return left - arrived
    return arrived - left


def signed_balance(holder: BoxHolder, box_type: str) -> int:
    """Boxes of one type a holder has now (a supplier: boxes we owe it). Never negative once posted."""
    arrived = (
        BoxMovement.objects.filter(to_holder=holder, box_type=box_type).aggregate(total=Sum("count"))["total"] or 0
    )
    left = BoxMovement.objects.filter(from_holder=holder, box_type=box_type).aggregate(total=Sum("count"))["total"] or 0
    return _balance_from_totals(holder, arrived, left)


def balances_of(organization: Organization) -> list[BoxBalance]:
    """The balance of every holder that has moved boxes, per box type. A supplier's count is what we owe it."""
    holders = {
        h.pk: h
        for h in BoxHolder.objects.for_organization(organization).select_related("location", "customer", "supplier")
    }
    return [
        BoxBalance(
            holder=holders[holder_id],
            box_type=box_type,
            count=_balance_from_totals(holders[holder_id], arrived, left),
        )
        for (holder_id, box_type), (arrived, left) in sorted(_holder_totals(organization).items())
    ]


def balance_of(organization: Organization, holder: BoxHolder, box_type: str) -> int:
    """One holder's balance for one box type; 0 when it has never moved boxes."""
    for row in balances_of(organization):
        if row.holder.pk == holder.pk and row.box_type == box_type:
            return row.count
    return 0


def truck_day(organization: Organization, location: "StockLocation", day: dt.date) -> list[TruckBoxDay]:
    """Per box type, what one truck (a stock location) loaded, left with clients and collected on `day`, and the
    boxes it holds now. Only movements of that day count for the three figures; `expected` is the ledger balance."""

    def totals(movements: QuerySet[BoxMovement]) -> dict[str, int]:
        rows = movements.order_by().values("box_type").annotate(total=Sum("count"))
        return {row["box_type"]: row["total"] for row in rows}

    # The day a movement belongs to: when it was made (the driver's phone's time), else when it was recorded.
    today = BoxMovement.objects.for_organization(organization).annotate(moved=Coalesce("made_at", "created_at"))
    today = today.filter(moved__date=day)
    loaded = totals(today.filter(kind=BoxMovementKind.LOAD, to_holder__location=location))
    left = totals(today.filter(kind=BoxMovementKind.LEAVE, from_holder__location=location))
    collected = totals(today.filter(kind=BoxMovementKind.COLLECT, to_holder__location=location))
    holder = BoxHolder.objects.for_organization(organization).filter(location=location).first()
    return [
        TruckBoxDay(
            box_type=box_type,
            loaded=loaded.get(box_type, 0),
            left=left.get(box_type, 0),
            collected=collected.get(box_type, 0),
            expected=signed_balance(holder, box_type) if holder is not None else 0,
        )
        for box_type in BoxType.values
    ]


def movements_of(
    organization: Organization,
    *,
    box_type: str | None = None,
    holder: BoxHolder | None = None,
) -> QuerySet[BoxMovement]:
    """The box history, newest first, optionally for one box type and one holder (either side)."""
    movements = BoxMovement.objects.for_organization(organization).select_related("from_holder", "to_holder")
    if box_type is not None:
        movements = movements.filter(box_type=box_type)
    if holder is not None:
        movements = movements.filter(Q(from_holder=holder) | Q(to_holder=holder))
    return movements

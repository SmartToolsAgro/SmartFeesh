"""Read helpers for returnable boxes. Every read is scoped to one organization."""

from dataclasses import dataclass

from django.db.models import Q, QuerySet, Sum

from apps.core.models import Organization

from .models import BoxHolder, BoxMovement


@dataclass(frozen=True)
class BoxBalance:
    holder: BoxHolder
    box_type: str
    count: int


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
    holders = {h.pk: h for h in BoxHolder.objects.for_organization(organization)}
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

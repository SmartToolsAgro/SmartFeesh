"""Reusable read queries of partnership lots and the partners' capital (P6-T01, D-060)."""

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count, Q, QuerySet, Sum

from apps.core.models import Organization

from .models import CapitalEntry, CapitalEntryKind, LotPartnership, PartnershipStatus

ZERO = Decimal("0.000")


def partnerships_of(
    organization: Organization,
    *,
    status: str | None = None,
    partner_id: int | None = None,
    batch_id: int | None = None,
    search: str = "",
) -> QuerySet[LotPartnership]:
    """Partnership lots, newest first, with their lot, product and partner. Cancelled ones are listed only
    when asked for by `status`. `search` matches the lot number, the product and the partner."""
    partnerships = (
        LotPartnership.objects.for_organization(organization)
        .select_related("batch__product", "batch__supplier", "partner", "created_by")
        .order_by("-created_at", "-id")
    )
    if status:
        partnerships = partnerships.filter(status=status)
    else:
        partnerships = partnerships.exclude(status=PartnershipStatus.CANCELLED)
    if partner_id is not None:
        partnerships = partnerships.filter(partner_id=partner_id)
    if batch_id is not None:
        partnerships = partnerships.filter(batch_id=batch_id)
    if search := search.strip():
        partnerships = partnerships.filter(
            Q(batch__number__icontains=search)
            | Q(batch__product__name__icontains=search)
            | Q(partner__name__icontains=search)
            | Q(partner__reference__icontains=search)
        )
    return partnerships


def partnership_of(organization: Organization, partnership_id: int) -> LotPartnership:
    """One partnership, cancelled or not. Raises LotPartnership.DoesNotExist outside the organization."""
    return (
        LotPartnership.objects.for_organization(organization)
        .select_related("batch__product", "batch__supplier", "partner", "created_by", "cancelled_by")
        .get(pk=partnership_id)
    )


def live_partnership_of_batch(organization: Organization, *, batch_id: int) -> LotPartnership | None:
    """The lot's partnership that is not cancelled, if any (at most one, by constraint)."""
    return (
        LotPartnership.objects.for_organization(organization)
        .exclude(status=PartnershipStatus.CANCELLED)
        .select_related("batch__product", "partner")
        .filter(batch_id=batch_id)
        .first()
    )


def capital_entries_of(partnership: LotPartnership) -> QuerySet[CapitalEntry]:
    """The partner's capital ledger in this lot, oldest first."""
    return (
        CapitalEntry.objects.for_organization(partnership.organization)
        .filter(partnership=partnership)
        .select_related("created_by")
        .order_by("entry_date", "id")
    )


def capital_balance(partnership: LotPartnership) -> Decimal:
    """The partner's capital in this lot now: the sum of their ledger (never below zero, D-031)."""
    total = capital_entries_of(partnership).aggregate(total=Sum("amount"))["total"]
    return total if total is not None else ZERO


def capital_put_in(partnership: LotPartnership) -> Decimal:
    """What the partner put into this lot: contributions and their corrections. The lot result starts from
    it; a loss deduction, its reversal on reopening and a return are the result's consequences."""
    total = (
        capital_entries_of(partnership)
        .filter(kind__in=[CapitalEntryKind.CONTRIBUTION, CapitalEntryKind.CORRECTION])
        .aggregate(total=Sum("amount"))["total"]
    )
    return total if total is not None else ZERO


@dataclass(frozen=True)
class PartnerCapital:
    """One partner's capital over all their lots: what is still in, per lot status."""

    partner_id: int
    lots: int
    capital: Decimal


def capital_by_partner(organization: Organization) -> dict[int, PartnerCapital]:
    """Each partner's capital still in the company, over all their partnership lots (by supplier id)."""
    rows = (
        CapitalEntry.objects.for_organization(organization)
        .values("partnership__partner_id")
        .annotate(total=Sum("amount"))
        .order_by("partnership__partner_id")
    )
    lots = (
        LotPartnership.objects.for_organization(organization)
        .exclude(status=PartnershipStatus.CANCELLED)
        .values("partner_id")
        .annotate(count=Count("id"))
        .order_by("partner_id")
    )
    counts = {row["partner_id"]: row["count"] for row in lots}
    return {
        row["partnership__partner_id"]: PartnerCapital(
            partner_id=row["partnership__partner_id"],
            lots=counts.get(row["partnership__partner_id"], 0),
            capital=row["total"] or ZERO,
        )
        for row in rows
    }

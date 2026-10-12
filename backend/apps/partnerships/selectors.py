"""Reusable read queries of partnership lots and the partners' capital (P6-T01, D-060)."""

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count, Q, QuerySet, Sum

from apps.core.models import Organization
from apps.purchasing import selectors as purchasing

from .models import (
    CapitalEntry,
    CapitalEntryKind,
    LotPartnership,
    PartnerSettlement,
    PartnershipStatus,
    ProfitShareEntry,
)
from .models import (
    ProfitShareKind as ProfitShareKind,
)
from .models import (
    SettlementPaymentMethod as SettlementPaymentMethod,
)

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


# ---- The partner's profit share, and their three balances (P6-T03, D-066) ----


def profit_share_entries_of(partnership: LotPartnership) -> QuerySet[ProfitShareEntry]:
    """The partner's profit-share ledger in this lot, oldest first."""
    return (
        ProfitShareEntry.objects.for_organization(partnership.organization)
        .filter(partnership=partnership)
        .select_related("created_by")
        .order_by("entry_date", "id")
    )


def profit_share_balance_of_partner(organization: Organization, *, partner_id: int) -> Decimal:
    """What the company owes the partner out of profit shares over all their lots: + owed to them, − owed by
    them (an uncovered loss or a late cost, recovered from their next share)."""
    total = (
        ProfitShareEntry.objects.for_organization(organization)
        .filter(partnership__partner_id=partner_id)
        .aggregate(total=Sum("amount"))["total"]
    )
    return total if total is not None else ZERO


def late_adjustments_booked(partnership: LotPartnership, *, lot_result_id: int) -> Decimal:
    """The change of the lot's net result already carried to the partner's settlements (sum of `basis`)."""
    total = (
        ProfitShareEntry.objects.for_organization(partnership.organization)
        .filter(partnership=partnership, kind=ProfitShareKind.LATE_ADJUSTMENT, lot_result_id=lot_result_id)
        .aggregate(total=Sum("basis"))["total"]
    )
    return total if total is not None else ZERO


def settlement_of(partnership: LotPartnership) -> PartnerSettlement | None:
    return (
        PartnerSettlement.objects.for_organization(partnership.organization)
        .filter(partnership=partnership)
        .select_related("created_by")
        .prefetch_related("payments", "entries")
        .first()
    )


@dataclass(frozen=True)
class PartnerBalances:
    """The three balances of one partner, kept apart (D-031, D-040): never added together.

    - `trade_payable`: owed for goods bought from them (D-043), from `purchasing`.
    - `capital`: their money still in the company's lots (all their partnership lots).
    - `profit_share`: shares of profit owed to them (+) or losses and late costs they owe (−).
    """

    partner_id: int
    trade_payable: Decimal
    capital: Decimal
    profit_share: Decimal
    lots: int


def partner_balances(organization: Organization, *, partner_id: int) -> PartnerBalances:
    capital = capital_by_partner(organization).get(partner_id)
    return PartnerBalances(
        partner_id=partner_id,
        trade_payable=purchasing.supplier_balance(organization, partner_id).balance,
        capital=capital.capital if capital is not None else ZERO,
        profit_share=profit_share_balance_of_partner(organization, partner_id=partner_id),
        lots=capital.lots if capital is not None else 0,
    )


def pending_terms(organization: Organization) -> QuerySet[LotPartnership]:
    """Open partnerships named at the goods receipt whose capital and rates are still to fill in (D-100):
    the lot cannot close until they are. Oldest first."""
    return (
        LotPartnership.objects.for_organization(organization)
        .filter(status=PartnershipStatus.OPEN, terms_pending=True)
        .select_related("batch", "partner")
        .order_by("created_at", "id")
    )

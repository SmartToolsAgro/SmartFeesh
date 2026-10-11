"""Writes of the cold-room cost and of the general costs (P5-T02, P5-T05, D-058, D-059).

Same rules as `services`: every write is atomic, audited, and checked with one ValidationError per field.
Approving an electricity bill goes through `services.approve_expense`, which calls `after_expense_approved`.
"""

import datetime as dt
import uuid
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core import audit
from apps.core.models import Organization, User
from apps.core.money import Number, checked_amount
from apps.inventory.selectors import LocationKind

if TYPE_CHECKING:
    from apps.inventory.models import StockLocation

from . import cost_selectors, services
from .costing import first_of_month, last_of_month, room_month_amounts
from .models import (
    ColdRoomMonthRate,
    ColdRoomWeight,
    ElectricityBill,
    Expense,
    ExpenseCategory,
    ExpensePaymentMethod,
    ExpenseStatus,
    GeneralCostPeriod,
    LotCostAdjustment,
    LotCostAdjustmentKind,
    RecurringCost,
)

COLD_STORAGE = "cold_storage"
MAX_WEIGHT = Decimal("1000.000")
MAX_MONTHS = 60


def is_linked(expense: Expense) -> bool:
    """Whether the expense is the other half of an electricity bill or a general cost: then it is changed
    or deleted through those records, never alone."""
    return (
        ElectricityBill.objects.filter(expense=expense).exists()
        or GeneralCostPeriod.objects.filter(expense=expense).exists()
    )


def _category(organization: Organization, code: str) -> ExpenseCategory:
    services.ensure_default_categories(organization=organization)
    return ExpenseCategory.objects.for_organization(organization).get(code=code)


def _month(value: dt.date, field: str) -> dt.date:
    if value.day != 1:
        raise ValidationError({field: _("Indiquez le premier jour du mois.")})
    return value


# ---- Weights of the cold rooms ----


@transaction.atomic
def set_cold_room_weight(
    *, organization: Organization, actor: User | None, location: "StockLocation", weight: Number
) -> ColdRoomWeight:
    """Set how much of the electricity bill a cold room takes (relative to the others; default 1). It is
    read when a bill is approved: months already billed keep the weights they were billed with."""
    if location.organization_id != organization.pk or location.kind != LocationKind.COLD_ROOM:
        raise ValidationError({"location": _("Chambre froide inconnue.")})
    try:
        value = Decimal(str(weight))
        if value != value.quantize(Decimal("0.001")) or value <= 0 or value > MAX_WEIGHT:
            raise ValueError
    except (InvalidOperation, ValueError):
        raise ValidationError({"weight": _("Indiquez un poids supérieur à zéro, au millième près.")}) from None
    row = ColdRoomWeight.objects.for_organization(organization).filter(location=location).first()
    before = str(row.weight) if row is not None else None
    if row is None:
        row = ColdRoomWeight(organization=organization, location=location)
    row.weight = value.quantize(Decimal("0.001"))
    row.save()
    audit.record(
        organization=organization,
        actor=actor,
        action="cold_room_weight.set",
        target=row,
        before={"weight": before},
        after={"room": location.name, "weight": str(row.weight)},
    )
    return row


# ---- Electricity bills ----


def _bill_snapshot(bill: ElectricityBill) -> dict[str, Any]:
    return {
        "month": bill.month.isoformat(),
        "amount": str(bill.expense.amount),
        "expense": bill.expense.number,
        "status": bill.expense.status,
    }


def _checked_bill_month(organization: Organization, month: dt.date) -> None:
    _month(month, "month")
    if month >= first_of_month(timezone.localdate()):
        raise ValidationError({"month": _("La facture se saisit une fois le mois terminé.")})
    existing = ElectricityBill.objects.for_organization(organization).filter(month=month).select_related("expense")
    for bill in existing:
        if bill.expense.status == ExpenseStatus.REJECTED:
            bill.delete()  # the refused expense stays as a trace; the month can be billed again
        else:
            raise ValidationError({"month": _("Ce mois a déjà une facture d'électricité.")})


@transaction.atomic
def create_electricity_bill(
    *,
    organization: Organization,
    actor: User | None,
    month: dt.date,
    amount: Number,
    payment_method: str = ExpensePaymentMethod.TRANSFER,
    payee: str = "",
    notes: str = "",
    approve: bool = False,
    client_uuid: uuid.UUID | None = None,
) -> ElectricityBill:
    """Type the electricity bill of a finished month: one expense (cold storage, dated the last day of the
    month) plus the month it is for. A draft until approved; approving freezes the rooms' shares and books
    the difference with the estimate on each lot (`finalize_bill`)."""
    _checked_bill_month(organization, month)
    expense = services.create_expense(
        organization=organization,
        actor=actor,
        spent_on=last_of_month(month),
        category=_category(organization, COLD_STORAGE),
        amount=amount,
        payment_method=payment_method,
        description=_("Électricité %(month)s") % {"month": f"{month:%m/%Y}"},
        payee=payee,
        notes=notes,
        client_uuid=client_uuid,
    )
    bill = ElectricityBill.objects.create(organization=organization, month=month, expense=expense)
    audit.record(
        organization=organization, actor=actor, action="electricity_bill.created", target=bill, after=_bill_snapshot(bill)
    )
    if approve:
        services.approve_expense(expense=expense, actor=actor)
    return cost_selectors.bill_of(organization, bill.pk)


@transaction.atomic
def update_electricity_bill(
    *,
    bill: ElectricityBill,
    actor: User | None,
    amount: Number,
    payment_method: str = ExpensePaymentMethod.TRANSFER,
    payee: str = "",
    notes: str = "",
    approve: bool = False,
) -> ElectricityBill:
    """Correct a bill not approved yet (amount, payment, payee, notes)."""
    bill = ElectricityBill.objects.select_related("expense__category", "organization").get(pk=bill.pk)
    before = _bill_snapshot(bill)
    services.update_expense(
        expense=bill.expense,
        actor=actor,
        spent_on=bill.expense.spent_on,
        category=bill.expense.category,
        amount=amount,
        payment_method=payment_method,
        description=bill.expense.description,
        payee=payee,
        notes=notes,
        approve=approve,
        linked=True,
    )
    bill = cost_selectors.bill_of(bill.organization, bill.pk)
    audit.record(
        organization=bill.organization,
        actor=actor,
        action="electricity_bill.updated",
        target=bill,
        before=before,
        after=_bill_snapshot(bill),
    )
    return bill


@transaction.atomic
def delete_electricity_bill(*, bill: ElectricityBill, actor: User | None) -> None:
    """Delete a bill typed by mistake while it is a draft (with its expense: they are one record)."""
    bill = ElectricityBill.objects.select_related("expense__category", "organization").get(pk=bill.pk)
    audit.record(
        organization=bill.organization,
        actor=actor,
        action="electricity_bill.deleted",
        target=bill,
        before=_bill_snapshot(bill),
    )
    services.delete_expense(expense=bill.expense, actor=actor, linked=True)


def after_expense_approved(*, expense: Expense, actor: User | None) -> None:
    """Called by `services.approve_expense`: an approved electricity bill freezes the month's shares."""
    bill = ElectricityBill.objects.filter(expense=expense).select_related("organization", "expense").first()
    if bill is not None and bill.finalized_at is None:
        finalize_bill(bill=bill, actor=actor)


def finalize_bill(*, bill: ElectricityBill, actor: User | None) -> list[LotCostAdjustment]:
    """Freeze an approved bill and correct the lots (D-041, D-058).

    The bill is shared between the active cold rooms by weight (to the millime, adding up exactly); each
    room's part and weight are kept, with the estimate's daily rate that had been in force. Then for every
    lot that spent days in a room that month, the real cost minus the estimate becomes a
    `LotCostAdjustment` dated today: a lot already closed is never reopened, a later settlement picks the
    line up. Immutable afterwards.
    """
    organization = bill.organization
    weights = cost_selectors.room_weights(organization)
    if not weights:
        raise ValidationError(_("Aucune chambre froide : créez-en une avant d'approuver la facture."))
    amounts = room_month_amounts(bill.expense.amount, weights)
    source, estimates = cost_selectors.estimate_for_new_bill(organization, month=bill.month)
    ColdRoomMonthRate.objects.bulk_create(
        ColdRoomMonthRate(
            organization=organization,
            bill=bill,
            location_id=room_id,
            weight=weights[room_id],
            month_amount=amounts[room_id],
            estimate_day_amount=estimates.get(room_id),
        )
        for room_id in weights
    )
    bill.finalized_at = timezone.now()
    bill.estimate_source_month = source
    bill.save(update_fields=["finalized_at", "estimate_source_month", "updated_at"])
    differences = cost_selectors.bill_adjustments(
        organization,
        month=bill.month,
        rates={room_id: (amounts[room_id], estimates.get(room_id)) for room_id in weights},
    )
    today = timezone.localdate()
    adjustments = LotCostAdjustment.objects.bulk_create(
        LotCostAdjustment(
            organization=organization,
            kind=LotCostAdjustmentKind.COLD_ROOM,
            batch_id=difference.batch_id,
            location_id=difference.location_id,
            month=bill.month,
            amount=difference.amount,
            dated_on=today,
            bill=bill,
        )
        for difference in differences
    )
    audit.record(
        organization=organization,
        actor=actor,
        action="electricity_bill.finalized",
        target=bill,
        after={
            "month": bill.month.isoformat(),
            "rooms": {str(room_id): str(amount) for room_id, amount in amounts.items()},
            "adjustments": len(adjustments),
            "estimate_source_month": source.isoformat() if source is not None else None,
        },
    )
    return adjustments


# ---- Recurring general costs and bills over several months (P5-T05, D-059) ----


def _checked_general_category(organization: Organization, category: ExpenseCategory) -> None:
    if category.organization_id != organization.pk or not category.is_active or category.code == services.DAY_LABOUR:
        raise ValidationError({"category": _("Catégorie inconnue.")})


def _checked_monthly(amount: Number) -> Decimal:
    try:
        value = checked_amount(amount)
    except (ValueError, TypeError):
        raise ValidationError({"monthly_amount": _("Indiquez un montant en DT, au millime près.")}) from None
    if value <= 0:
        raise ValidationError({"monthly_amount": _("Indiquez un montant supérieur à zéro.")})
    return value


def _checked_range(start_month: dt.date, end_month: dt.date | None) -> None:
    _month(start_month, "start_month")
    if end_month is not None:
        _month(end_month, "end_month")
        if end_month < start_month:
            raise ValidationError({"end_month": _("Le dernier mois précède le premier.")})


def _recurring_snapshot(cost: RecurringCost) -> dict[str, Any]:
    return {
        "name": cost.name,
        "category": cost.category.name,
        "monthly_amount": str(cost.monthly_amount),
        "start_month": cost.start_month.isoformat(),
        "end_month": cost.end_month.isoformat() if cost.end_month else None,
        "is_active": cost.is_active,
    }


def _checked_cost_name(organization: Organization, name: str, *, exclude_id: int | None = None) -> str:
    name = " ".join(name.split())
    if not name:
        raise ValidationError({"name": _("Indiquez un nom.")})
    same = RecurringCost.objects.for_organization(organization).filter(name__iexact=name)
    if exclude_id is not None:
        same = same.exclude(pk=exclude_id)
    if same.exists():
        raise ValidationError({"name": _("Un autre frais récurrent porte déjà ce nom.")})
    return name[:100]


@transaction.atomic
def create_recurring_cost(
    *,
    organization: Organization,
    actor: User | None,
    name: str,
    category: ExpenseCategory,
    monthly_amount: Number,
    start_month: dt.date,
    end_month: dt.date | None = None,
    payment_method: str = ExpensePaymentMethod.TRANSFER,
    payee: str = "",
) -> RecurringCost:
    """Add a monthly cost (rent, accountant, insurance): a template that generates the month's expense."""
    _checked_general_category(organization, category)
    _checked_range(start_month, end_month)
    if payment_method not in ExpensePaymentMethod.values:
        raise ValidationError({"payment_method": _("Mode de paiement inconnu.")})
    cost = RecurringCost.objects.create(
        organization=organization,
        name=_checked_cost_name(organization, name),
        category=category,
        monthly_amount=_checked_monthly(monthly_amount),
        payment_method=payment_method,
        payee=" ".join(payee.split())[:150],
        start_month=start_month,
        end_month=end_month,
    )
    audit.record(
        organization=organization,
        actor=actor,
        action="recurring_cost.created",
        target=cost,
        after=_recurring_snapshot(cost),
    )
    return cost


@transaction.atomic
def update_recurring_cost(
    *,
    cost: RecurringCost,
    actor: User | None,
    name: str,
    category: ExpenseCategory,
    monthly_amount: Number,
    start_month: dt.date,
    end_month: dt.date | None = None,
    payment_method: str = ExpensePaymentMethod.TRANSFER,
    payee: str = "",
    is_active: bool = True,
) -> RecurringCost:
    """Change a template, or stop it (`is_active` false). Months already generated keep their amount."""
    cost = RecurringCost.objects.select_for_update().select_related("category", "organization").get(pk=cost.pk)
    organization = cost.organization
    before = _recurring_snapshot(cost)
    if category.pk != cost.category_id:
        _checked_general_category(organization, category)
    _checked_range(start_month, end_month)
    if payment_method not in ExpensePaymentMethod.values:
        raise ValidationError({"payment_method": _("Mode de paiement inconnu.")})
    cost.name = _checked_cost_name(organization, name, exclude_id=cost.pk)
    cost.category = category
    cost.monthly_amount = _checked_monthly(monthly_amount)
    cost.payment_method = payment_method
    cost.payee = " ".join(payee.split())[:150]
    cost.start_month = start_month
    cost.end_month = end_month
    cost.is_active = is_active
    cost.save()
    audit.record(
        organization=organization,
        actor=actor,
        action="recurring_cost.updated",
        target=cost,
        before=before,
        after=_recurring_snapshot(cost),
    )
    return cost


def _general_expense(
    *,
    organization: Organization,
    actor: User | None,
    spent_on: dt.date,
    category: ExpenseCategory,
    amount: Number,
    payment_method: str,
    description: str,
    payee: str,
    notes: str,
    first_month: dt.date,
    months: int,
    recurring: RecurringCost | None = None,
) -> GeneralCostPeriod:
    expense = services.create_expense(
        organization=organization,
        actor=actor,
        spent_on=spent_on,
        category=category,
        amount=amount,
        payment_method=payment_method,
        description=description,
        payee=payee,
        notes=notes,
    )
    period = GeneralCostPeriod.objects.create(
        organization=organization, expense=expense, first_month=first_month, months=months, recurring=recurring
    )
    audit.record(
        organization=organization,
        actor=actor,
        action="general_cost.created",
        target=period,
        after={"expense": expense.number, "first_month": first_month.isoformat(), "months": months},
    )
    return period


@transaction.atomic
def generate_recurring_costs(
    *, organization: Organization, actor: User | None, month: dt.date, approve: bool = False
) -> list[GeneralCostPeriod]:
    """Generate the month's expense of every active template that applies to it and has none yet (safe to
    run again). The expense is dated the first of the month, a draft unless `approve`. Not for a future
    month."""
    _month(month, "month")
    if month > timezone.localdate():
        raise ValidationError({"month": _("Ce mois n'a pas commencé.")})
    created: list[GeneralCostPeriod] = []
    for cost in cost_selectors.recurring_costs_of(organization, active_only=True):
        if cost.start_month > month or (cost.end_month is not None and cost.end_month < month):
            continue
        if GeneralCostPeriod.objects.filter(recurring=cost, first_month=month).exists():
            continue
        period = _general_expense(
            organization=organization,
            actor=actor,
            spent_on=month,
            category=cost.category,
            amount=cost.monthly_amount,
            payment_method=cost.payment_method,
            description=cost.name,
            payee=cost.payee,
            notes="",
            first_month=month,
            months=1,
            recurring=cost,
        )
        if approve:
            services.approve_expense(expense=period.expense, actor=actor)
        created.append(period)
    return created


@transaction.atomic
def create_general_cost(
    *,
    organization: Organization,
    actor: User | None,
    spent_on: dt.date,
    category: ExpenseCategory,
    amount: Number,
    first_month: dt.date,
    months: int = 1,
    payment_method: str = ExpensePaymentMethod.TRANSFER,
    description: str = "",
    payee: str = "",
    notes: str = "",
    approve: bool = False,
) -> GeneralCostPeriod:
    """A bill covering one or several months (an insurance for a year): one expense, spread equally over
    the months it covers; each month's part is then charged to the lots "like a salary" (D-059)."""
    _checked_general_category(organization, category)
    _month(first_month, "first_month")
    if not 1 <= months <= MAX_MONTHS:
        raise ValidationError({"months": _("Entre 1 et %(max)s mois.") % {"max": MAX_MONTHS}})
    period = _general_expense(
        organization=organization,
        actor=actor,
        spent_on=spent_on,
        category=category,
        amount=amount,
        payment_method=payment_method,
        description=description,
        payee=payee,
        notes=notes,
        first_month=first_month,
        months=months,
    )
    if approve:
        services.approve_expense(expense=period.expense, actor=actor)
    return cost_selectors.general_period_of(organization, period.pk)


@transaction.atomic
def delete_general_cost(*, period: GeneralCostPeriod, actor: User | None) -> None:
    """Delete a general cost typed by mistake while it is a draft (with its expense)."""
    period = GeneralCostPeriod.objects.select_related("expense__category", "organization").get(pk=period.pk)
    audit.record(
        organization=period.organization,
        actor=actor,
        action="general_cost.deleted",
        target=period,
        before={"expense": period.expense.number, "first_month": period.first_month.isoformat()},
    )
    services.delete_expense(expense=period.expense, actor=actor, linked=True)

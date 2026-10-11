"""Every write on expenses goes through these functions (ARCHITECTURE §3)."""

import datetime as dt
import uuid
from typing import TYPE_CHECKING, Any

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _

from apps.core import audit
from apps.core.images import reencoded_photo
from apps.core.models import Organization, User
from apps.core.money import Number, checked_amount

from .models import (
    DayLabourEntry,
    DayLabourer,
    DocumentCounter,
    Expense,
    ExpenseCategory,
    ExpensePaymentMethod,
    ExpenseStatus,
    WorkType,
)

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile

    from apps.fleet.models import Truck
    from apps.inventory.models import Batch

# ---- Categories (P5-T01, D-053) ----

DAY_LABOUR = "day_labour"
# Every organization starts with these (the brief's list), in this order. Their names can be changed by the
# owner; their codes never change, so the app finds them (the day-labour calendar uses `DAY_LABOUR`).
DEFAULT_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("personnel", "Personnel"),
    (DAY_LABOUR, "Main-d'œuvre journalière"),
    ("transport", "Transport"),
    ("fuel", "Carburant"),
    ("cold_storage", "Froid et stockage"),
    ("handling", "Manutention"),
    ("rent", "Loyer"),
    ("accountant", "Comptable"),
    ("administration", "Administration"),
    ("financial", "Frais financiers"),
    ("miscellaneous", "Divers"),
)
# The owner's own categories come after the default ones.
CUSTOM_POSITION = 1000


def ensure_default_categories(*, organization: Organization) -> None:
    """Create the default categories the organization does not have yet (by code). Safe to call again."""
    ExpenseCategory.objects.bulk_create(
        [
            ExpenseCategory(organization=organization, code=code, name=name, position=(index + 1) * 10)
            for index, (code, name) in enumerate(DEFAULT_CATEGORIES)
        ],
        ignore_conflicts=True,
    )


def _checked_name(organization: Organization, name: str, *, exclude_id: int | None = None) -> str:
    name = " ".join(name.split())
    if not name:
        raise ValidationError({"name": _("Indiquez un nom.")})
    if len(name) > 100:
        raise ValidationError({"name": _("100 caractères au plus.")})
    same = ExpenseCategory.objects.for_organization(organization).filter(name__iexact=name)
    if exclude_id is not None:
        same = same.exclude(pk=exclude_id)
    if same.exists():
        raise ValidationError({"name": _("Une autre catégorie porte déjà ce nom.")})
    return name


@transaction.atomic
def create_category(*, organization: Organization, actor: User | None, name: str) -> ExpenseCategory:
    """Add a category of the owner's own (after the default ones)."""
    category = ExpenseCategory.objects.create(
        organization=organization, name=_checked_name(organization, name), position=CUSTOM_POSITION
    )
    audit.record(
        organization=organization, actor=actor, action="expense_category.created", target=category, after={"name": name}
    )
    return category


@transaction.atomic
def update_category(
    *, category: ExpenseCategory, actor: User | None, name: str | None = None, is_active: bool | None = None
) -> ExpenseCategory:
    """Rename a category or archive it (an archived one is no longer offered; its expenses keep it).

    The default categories can be renamed but not archived: the app relies on them.
    """
    category = ExpenseCategory.objects.select_for_update().get(pk=category.pk)
    before = {"name": category.name, "is_active": category.is_active}
    if name is not None:
        category.name = _checked_name(category.organization, name, exclude_id=category.pk)
    if is_active is not None:
        if not is_active and category.code:
            raise ValidationError({"is_active": _("Une catégorie de base ne s'archive pas : renommez-la si besoin.")})
        category.is_active = is_active
    category.save()
    audit.record(
        organization=category.organization,
        actor=actor,
        action="expense_category.updated",
        target=category,
        before=before,
        after={"name": category.name, "is_active": category.is_active},
    )
    return category


# ---- Expenses (P5-T01, D-053) ----

EXPENSE_SERIES = "DP"
MAX_RECEIPT_BYTES = 8 * 1024 * 1024
OPEN_STATUSES = frozenset({ExpenseStatus.DRAFT, ExpenseStatus.PENDING})


def _next_number(organization: Organization, series: str) -> str:
    """DP-0001, DP-0002... per organization and series, taken under a row lock (same scheme as D-043).

    A deleted draft leaves a gap: these are not fiscal numbers.
    """
    DocumentCounter.objects.bulk_create(
        [DocumentCounter(organization=organization, series=series)], ignore_conflicts=True
    )
    counter = DocumentCounter.objects.select_for_update().get(organization=organization, series=series)
    counter.last_number += 1
    counter.save(update_fields=["last_number"])
    return f"{series}-{counter.last_number:04d}"


def _checked_expense(
    organization: Organization,
    *,
    spent_on: dt.date,
    category: ExpenseCategory,
    amount: Any,
    payment_method: str,
    batch: "Batch | None",
    truck: "Truck | None",
    for_day_labour: bool,
    current: Expense | None = None,
) -> dict[str, Any]:
    """The checked values of an expense, or a ValidationError with every problem at once."""
    errors: dict[str, str] = {}
    values: dict[str, Any] = {}
    if spent_on > timezone.localdate():
        errors["spent_on"] = _("La date ne peut pas être dans le futur.")
    if category.organization_id != organization.pk:
        errors["category"] = _("Catégorie inconnue.")
    elif not category.is_active and (current is None or current.category_id != category.pk):
        errors["category"] = _("« %(name)s » est archivée.") % {"name": category.name}
    elif (category.code == DAY_LABOUR) != for_day_labour:
        errors["category"] = (
            _("Une journée de travail se saisit dans le calendrier des journaliers.")
            if not for_day_labour
            else _("Catégorie inconnue.")
        )
    try:
        values["amount"] = checked_amount(amount)
        if values["amount"] <= 0:
            errors["amount"] = _("Indiquez un montant supérieur à zéro.")
    except (ValueError, TypeError):
        errors["amount"] = _("Indiquez un montant en DT, au millime près.")
    if payment_method not in ExpensePaymentMethod.values:
        errors["payment_method"] = _("Mode de paiement inconnu.")
    if batch is not None and truck is not None:
        errors["truck"] = _("Une dépense va sur un lot ou sur un camion, pas les deux.")
    if batch is not None:
        if batch.organization_id != organization.pk:
            errors["batch"] = _("Lot inconnu.")
        elif spent_on < batch.received_on:
            errors["batch"] = _("Le lot %(number)s est arrivé le %(date)s, après cette date.") % {
                "number": batch.number,
                "date": date_format(batch.received_on, "SHORT_DATE_FORMAT"),
            }
    if truck is not None and truck.organization_id != organization.pk:
        errors["truck"] = _("Camion inconnu.")
    if errors:
        raise ValidationError(errors)
    return values


def _snapshot(expense: Expense) -> dict[str, Any]:
    return {
        "number": expense.number,
        "status": expense.status,
        "spent_on": expense.spent_on.isoformat(),
        "category": expense.category.name,
        "amount": str(expense.amount),
        "payment_method": expense.payment_method,
        "description": expense.description,
        "payee": expense.payee,
        "batch": expense.batch.number if expense.batch is not None else None,
        "truck": str(expense.truck.location.name) if expense.truck is not None else None,
    }


def _clean(text: str, limit: int) -> str:
    return " ".join(text.split())[:limit]


@transaction.atomic
def create_expense(
    *,
    organization: Organization,
    actor: User | None,
    spent_on: dt.date,
    category: ExpenseCategory,
    amount: Number,
    payment_method: str = ExpensePaymentMethod.CASH,
    description: str = "",
    payee: str = "",
    notes: str = "",
    batch: "Batch | None" = None,
    truck: "Truck | None" = None,
    client_uuid: uuid.UUID | None = None,
    submit: bool = False,
    approve: bool = False,
    for_day_labour: bool = False,
) -> Expense:
    """Record an expense as a draft. With `submit` it waits for approval (how a driver's expense from the
    phone arrives, P3-T04); with `approve` the owner or a manager approves it at once (same transaction).

    `batch` charges it to one lot; `truck` makes it a truck cost of that day, split over the lots loaded
    on the truck that day. A day labourer's day is recorded through `create_day_labour` (`for_day_labour`
    is for that function only). A `client_uuid` already used returns that expense.
    """
    if client_uuid is not None:
        existing = Expense.objects.for_organization(organization).filter(client_uuid=client_uuid).first()
        if existing is not None:
            return existing
    values = _checked_expense(
        organization,
        spent_on=spent_on,
        category=category,
        amount=amount,
        payment_method=payment_method,
        batch=batch,
        truck=truck,
        for_day_labour=for_day_labour,
    )
    expense = Expense.objects.create(
        organization=organization,
        number=_next_number(organization, EXPENSE_SERIES),
        status=ExpenseStatus.PENDING if submit else ExpenseStatus.DRAFT,
        spent_on=spent_on,
        category=category,
        amount=values["amount"],
        payment_method=payment_method,
        description=_clean(description, 255),
        payee=_clean(payee, 150),
        notes=notes.strip(),
        batch=batch,
        truck=truck,
        entered_by=actor,
        client_uuid=client_uuid,
    )
    audit.record(
        organization=organization, actor=actor, action="expense.created", target=expense, after=_snapshot(expense)
    )
    if approve:
        return approve_expense(expense=expense, actor=actor)
    return expense


def _locked(expense: Expense) -> Expense:
    """The expense locked until commit, so two decisions taken at once never both apply."""
    return (
        Expense.objects.select_for_update(of=("self",))
        .select_related("organization", "category", "batch", "truck__location")
        .get(pk=expense.pk)
    )


def _status_name(expense: Expense) -> str:
    return str(ExpenseStatus(expense.status).label).lower()


def _locked_open(expense: Expense) -> Expense:
    locked = _locked(expense)
    if locked.status not in OPEN_STATUSES:
        raise ValidationError(
            _("Cette dépense est %(status)s : elle ne se modifie plus. Une correction est une nouvelle dépense.")
            % {"status": _status_name(locked)}
        )
    return locked


def is_day_labour(expense: Expense) -> bool:
    """Whether the expense is a day labourer's day (P5-T03): it is then changed through the calendar."""
    return expense.category.code == DAY_LABOUR


@transaction.atomic
def update_expense(
    *,
    expense: Expense,
    actor: User | None,
    spent_on: dt.date,
    category: ExpenseCategory,
    amount: Number,
    payment_method: str = ExpensePaymentMethod.CASH,
    description: str = "",
    payee: str = "",
    notes: str = "",
    batch: "Batch | None" = None,
    truck: "Truck | None" = None,
    approve: bool = False,
    for_day_labour: bool = False,
) -> Expense:
    """Correct a draft or an expense waiting for approval (every field); with `approve`, approve it too."""
    expense = _locked_open(expense)
    if is_day_labour(expense) and not for_day_labour:
        raise ValidationError(_("Une journée de travail se modifie dans le calendrier des journaliers."))
    before = _snapshot(expense)
    values = _checked_expense(
        expense.organization,
        spent_on=spent_on,
        category=category,
        amount=amount,
        payment_method=payment_method,
        batch=batch,
        truck=truck,
        for_day_labour=for_day_labour,
        current=expense,
    )
    expense.spent_on = spent_on
    expense.category = category
    expense.amount = values["amount"]
    expense.payment_method = payment_method
    expense.description = _clean(description, 255)
    expense.payee = _clean(payee, 150)
    expense.notes = notes.strip()
    expense.batch = batch
    expense.truck = truck
    expense.save()
    audit.record(
        organization=expense.organization,
        actor=actor,
        action="expense.updated",
        target=expense,
        before=before,
        after=_snapshot(expense),
    )
    if approve:
        return approve_expense(expense=expense, actor=actor)
    return expense


@transaction.atomic
def delete_expense(*, expense: Expense, actor: User | None, for_day_labour: bool = False) -> None:
    """Delete a draft typed by mistake (its number is not reused). Anything sent for approval is refused
    instead, so its trace stays."""
    expense = _locked(expense)
    if expense.status != ExpenseStatus.DRAFT:
        raise ValidationError(_("Seul un brouillon se supprime : refusez plutôt cette dépense."))
    if is_day_labour(expense) and not for_day_labour:
        raise ValidationError(_("Une journée de travail se supprime dans le calendrier des journaliers."))
    audit.record(
        organization=expense.organization,
        actor=actor,
        action="expense.deleted",
        target=expense,
        before=_snapshot(expense),
    )
    receipt = expense.receipt.name
    storage = expense.receipt.storage
    expense.delete()
    if receipt:
        transaction.on_commit(lambda: storage.delete(receipt))


@transaction.atomic
def approve_expense(*, expense: Expense, actor: User | None) -> Expense:
    """Approve a draft or a waiting expense: from now on it counts in the costs and never changes."""
    expense = _locked_open(expense)
    if not expense.category.is_active:
        raise ValidationError({"category": _("« %(name)s » est archivée.") % {"name": expense.category.name}})
    expense.status = ExpenseStatus.APPROVED
    expense.decided_by = actor
    expense.decided_at = timezone.now()
    expense.save(update_fields=["status", "decided_by", "decided_at", "updated_at"])
    audit.record(
        organization=expense.organization,
        actor=actor,
        action="expense.approved",
        target=expense,
        after={"amount": str(expense.amount)},
    )
    return expense


@transaction.atomic
def reject_expense(*, expense: Expense, actor: User | None, reason: str) -> Expense:
    """Refuse a draft or a waiting expense, saying why. It never counts and never changes again."""
    reason = _clean(reason, 255)
    if not reason:
        raise ValidationError({"reason": _("Indiquez pourquoi cette dépense est refusée.")})
    expense = _locked_open(expense)
    expense.status = ExpenseStatus.REJECTED
    expense.decided_by = actor
    expense.decided_at = timezone.now()
    expense.rejection_reason = reason
    expense.save(update_fields=["status", "decided_by", "decided_at", "rejection_reason", "updated_at"])
    audit.record(
        organization=expense.organization,
        actor=actor,
        action="expense.rejected",
        target=expense,
        after={"reason": reason},
    )
    return expense


def _receipt_content(upload: "UploadedFile[bytes]") -> tuple[ContentFile[bytes], str]:
    """A PDF kept as it is, or a photo turned upright, shrunk and saved as WebP; with the file name."""
    head = upload.read(5)
    upload.seek(0)
    if head == b"%PDF-":
        if upload.size is not None and upload.size > MAX_RECEIPT_BYTES:
            raise ValidationError({"receipt": _("Le fichier dépasse 8 Mo.")})
        return ContentFile(upload.read()), "receipt.pdf"
    return reencoded_photo(upload, field="receipt"), "receipt.webp"


@transaction.atomic
def add_expense_receipt(*, expense: Expense, actor: User | None, upload: "UploadedFile[bytes]") -> Expense:
    """Join the receipt (a photo or a PDF). It can be replaced while the expense is open; once approved
    or refused, a receipt can still be joined if there was none, never replaced."""
    content, name = _receipt_content(upload)
    expense = _locked(expense)
    if expense.status not in OPEN_STATUSES and expense.receipt:
        raise ValidationError({"receipt": _("Cette dépense est décidée : son justificatif ne change plus.")})
    previous = expense.receipt.name
    storage = expense.receipt.storage
    expense.receipt.save(name, content, save=False)
    try:
        expense.save(update_fields=["receipt", "updated_at"])
        audit.record(organization=expense.organization, actor=actor, action="expense.receipt_added", target=expense)
    except BaseException:
        # The file is written before the row: never leave it behind when the change is rolled back.
        if expense.receipt.name:
            expense.receipt.storage.delete(expense.receipt.name)
        raise
    if previous:
        transaction.on_commit(lambda: storage.delete(previous))
    return expense


# ---- Day labour (P5-T03, D-054) ----


def _checked_labourer(
    organization: Organization,
    *,
    name: str,
    phone: str,
    usual_daily_pay: Any,
    exclude_id: int | None = None,
) -> dict[str, Any]:
    errors: dict[str, str] = {}
    values: dict[str, Any] = {"name": " ".join(name.split()), "phone": " ".join(phone.split())[:30]}
    if not values["name"]:
        errors["name"] = _("Indiquez un nom.")
    elif len(values["name"]) > 100:
        errors["name"] = _("100 caractères au plus.")
    else:
        same = DayLabourer.objects.for_organization(organization).filter(name__iexact=values["name"])
        if exclude_id is not None:
            same = same.exclude(pk=exclude_id)
        if same.exists():
            errors["name"] = _("Un autre journalier porte déjà ce nom.")
    values["usual_daily_pay"] = None
    if usual_daily_pay not in (None, ""):
        try:
            values["usual_daily_pay"] = checked_amount(usual_daily_pay)
            if values["usual_daily_pay"] <= 0:
                errors["usual_daily_pay"] = _("Indiquez un montant supérieur à zéro, ou rien.")
        except (ValueError, TypeError):
            errors["usual_daily_pay"] = _("Indiquez un montant en DT, au millime près.")
    if errors:
        raise ValidationError(errors)
    return values


def _labourer_snapshot(labourer: DayLabourer) -> dict[str, Any]:
    return {
        "name": labourer.name,
        "phone": labourer.phone,
        "usual_daily_pay": str(labourer.usual_daily_pay) if labourer.usual_daily_pay is not None else None,
        "is_active": labourer.is_active,
    }


@transaction.atomic
def create_labourer(
    *,
    organization: Organization,
    actor: User | None,
    name: str,
    phone: str = "",
    usual_daily_pay: Number | None = None,
    notes: str = "",
) -> DayLabourer:
    """Add a day labourer: a name, a phone and what they are usually paid for a day (optional)."""
    values = _checked_labourer(organization, name=name, phone=phone, usual_daily_pay=usual_daily_pay)
    labourer = DayLabourer.objects.create(organization=organization, notes=notes.strip(), **values)
    audit.record(
        organization=organization,
        actor=actor,
        action="day_labourer.created",
        target=labourer,
        after=_labourer_snapshot(labourer),
    )
    return labourer


@transaction.atomic
def update_labourer(
    *,
    labourer: DayLabourer,
    actor: User | None,
    name: str,
    phone: str = "",
    usual_daily_pay: Number | None = None,
    notes: str = "",
    is_active: bool = True,
) -> DayLabourer:
    """Change a day labourer, or archive them (no longer offered; their days stay)."""
    labourer = DayLabourer.objects.select_for_update().get(pk=labourer.pk)
    before = _labourer_snapshot(labourer)
    values = _checked_labourer(
        labourer.organization, name=name, phone=phone, usual_daily_pay=usual_daily_pay, exclude_id=labourer.pk
    )
    for field, value in values.items():
        setattr(labourer, field, value)
    labourer.notes = notes.strip()
    labourer.is_active = is_active
    labourer.save()
    audit.record(
        organization=labourer.organization,
        actor=actor,
        action="day_labourer.updated",
        target=labourer,
        before=before,
        after=_labourer_snapshot(labourer),
    )
    return labourer


def _day_labour_values(
    organization: Organization,
    labourer: DayLabourer,
    amount: Number | None,
    work_type: str,
    *,
    current: DayLabourEntry | None = None,
) -> Number:
    """The amount paid (the labourer's usual pay when none is typed), or a ValidationError."""
    errors: dict[str, str] = {}
    if labourer.organization_id != organization.pk:
        errors["labourer"] = _("Journalier inconnu.")
    elif not labourer.is_active and (current is None or current.labourer_id != labourer.pk):
        errors["labourer"] = _("« %(name)s » est archivé.") % {"name": labourer.name}
    if work_type not in WorkType.values:
        errors["work_type"] = _("Type de travail inconnu.")
    if amount in (None, ""):
        if labourer.usual_daily_pay is None:
            errors["amount"] = _("Indiquez le montant payé : ce journalier n'a pas de paie habituelle.")
        else:
            amount = labourer.usual_daily_pay
    if errors:
        raise ValidationError(errors)
    assert amount is not None
    return amount


def _day_labour_category(organization: Organization) -> ExpenseCategory:
    ensure_default_categories(organization=organization)
    return ExpenseCategory.objects.for_organization(organization).get(code=DAY_LABOUR)


def _day_labour_snapshot(entry: DayLabourEntry) -> dict[str, Any]:
    return {"labourer": entry.labourer.name, "work_type": entry.work_type, "expense": entry.expense.number}


@transaction.atomic
def create_day_labour(
    *,
    organization: Organization,
    actor: User | None,
    labourer: DayLabourer,
    worked_on: dt.date,
    amount: Number | None = None,
    batch: "Batch | None" = None,
    work_type: str = WorkType.OTHER,
    notes: str = "",
    payment_method: str = ExpensePaymentMethod.CASH,
    approve: bool = False,
    client_uuid: uuid.UUID | None = None,
) -> DayLabourEntry:
    """Record a day worked by a day labourer, from the calendar or from a lot: the same single record,
    an expense of category day labour plus who worked (D-054). Without `amount`, their usual daily pay.
    With `batch` it is a cost of that lot; without, a general cost. With `approve`, approved at once.
    A `client_uuid` already used returns that day."""
    if client_uuid is not None:
        existing = (
            DayLabourEntry.objects.for_organization(organization).filter(expense__client_uuid=client_uuid).first()
        )
        if existing is not None:
            return existing
    amount = _day_labour_values(organization, labourer, amount, work_type)
    expense = create_expense(
        organization=organization,
        actor=actor,
        spent_on=worked_on,
        category=_day_labour_category(organization),
        amount=amount,
        payment_method=payment_method,
        description=labourer.name,
        payee=labourer.name,
        notes=notes,
        batch=batch,
        client_uuid=client_uuid,
        for_day_labour=True,
    )
    entry = DayLabourEntry.objects.create(
        organization=organization, expense=expense, labourer=labourer, work_type=work_type
    )
    audit.record(
        organization=organization,
        actor=actor,
        action="day_labour.created",
        target=entry,
        after=_day_labour_snapshot(entry),
    )
    if approve:
        approve_expense(expense=expense, actor=actor)
        entry.expense.refresh_from_db()
    return entry


@transaction.atomic
def update_day_labour(
    *,
    entry: DayLabourEntry,
    actor: User | None,
    labourer: DayLabourer,
    worked_on: dt.date,
    amount: Number | None = None,
    batch: "Batch | None" = None,
    work_type: str = WorkType.OTHER,
    notes: str = "",
    payment_method: str = ExpensePaymentMethod.CASH,
    approve: bool = False,
) -> DayLabourEntry:
    """Correct a day not approved yet (who, which day, how much, which lot, what work)."""
    entry = DayLabourEntry.objects.select_for_update().select_related("expense", "labourer").get(pk=entry.pk)
    organization = entry.expense.organization
    before = _day_labour_snapshot(entry)
    amount = _day_labour_values(organization, labourer, amount, work_type, current=entry)
    update_expense(
        expense=entry.expense,
        actor=actor,
        spent_on=worked_on,
        category=entry.expense.category,
        amount=amount,
        payment_method=payment_method,
        description=labourer.name,
        payee=labourer.name,
        notes=notes,
        batch=batch,
        approve=approve,
        for_day_labour=True,
    )
    entry.labourer = labourer
    entry.work_type = work_type
    entry.save()
    entry.expense.refresh_from_db()
    audit.record(
        organization=organization,
        actor=actor,
        action="day_labour.updated",
        target=entry,
        before=before,
        after=_day_labour_snapshot(entry),
    )
    return entry


@transaction.atomic
def delete_day_labour(*, entry: DayLabourEntry, actor: User | None) -> None:
    """Delete a day typed by mistake, while it is a draft (with its expense: they are one record)."""
    entry = DayLabourEntry.objects.select_related("expense", "labourer").get(pk=entry.pk)
    audit.record(
        organization=entry.expense.organization,
        actor=actor,
        action="day_labour.deleted",
        target=entry,
        before=_day_labour_snapshot(entry),
    )
    delete_expense(expense=entry.expense, actor=actor, for_day_labour=True)

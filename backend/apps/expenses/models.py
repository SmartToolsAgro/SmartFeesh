import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from apps.core.models import OrganizationScopedModel, TimeStampedModel
from apps.core.money import MoneyField


class DocumentCounter(OrganizationScopedModel):
    """The last number given to one series of expense documents ("DP" expenses) in an organization.

    Locked while a number is taken (same scheme as the other apps, D-043), so two expenses saved at once
    never share one.
    """

    series = models.CharField(max_length=20)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "series"], name="expenses_one_counter_per_series"),
        ]

    def __str__(self) -> str:
        return f"{self.organization} · {self.series} · {self.last_number}"


# ---- Expenses (P5-T01, D-053) ----


class ExpenseCategory(OrganizationScopedModel, TimeStampedModel):
    """What an expense is for: fuel, transport, rent... Every organization starts with the default ones
    (`services.DEFAULT_CATEGORIES`, which carry a `code`); the owner adds others (no code), renames any and
    archives his own."""

    # Set on the default categories only ("fuel", "day_labour"...): code finds them whatever their name.
    code = models.CharField(max_length=30, blank=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    # Order in lists: the default ones in the order of the brief, the owner's after them.
    position = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ["position", "name", "id"]
        verbose_name_plural = "expense categories"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"],
                condition=~models.Q(code=""),
                name="expense_category_code_unique_per_organization",
            ),
            models.UniqueConstraint(
                "organization", Lower("name"), name="expense_category_name_unique_per_organization"
            ),
        ]

    def __str__(self) -> str:
        return self.name


class ExpenseStatus(models.TextChoices):
    # Typed at the office, still being checked: it changes freely and can be deleted.
    DRAFT = "draft", _("Brouillon")
    # Sent for approval (a driver's expense from the phone, P3-T04): it can still be corrected.
    PENDING = "pending", _("À approuver")
    # Approved by the owner or a manager: it counts in the costs and never changes again.
    APPROVED = "approved", _("Approuvée")
    # Refused, with a reason: it never counts.
    REJECTED = "rejected", _("Refusée")


class ExpensePaymentMethod(models.TextChoices):
    # The same list as supplier payments (D-043), so the API has one payment method type.
    CASH = "cash", _("Espèces")
    CHEQUE = "cheque", _("Chèque")
    TRANSFER = "transfer", _("Virement")
    BILL = "bill", _("Traite")
    OTHER = "other", _("Autre")


class LotCostKind(models.TextChoices):
    """Where a cost line of a lot comes from (`selectors.lot_cost_lines`); not stored."""

    # An expense typed on the lot.
    LOT = "lot", _("Sur le lot")
    # The lot's share of a truck's costs on a day it was loaded (by kg loaded).
    TRUCK_DAY = "truck_day", _("Frais du camion du jour")


def receipt_path(expense: "Expense", filename: str) -> str:
    # A random name: the receipt's address cannot be guessed from the expense number.
    extension = ".pdf" if filename.lower().endswith(".pdf") else ".webp"
    return f"expenses/{expense.organization_id}/{uuid.uuid4().hex}{extension}"


class Expense(OrganizationScopedModel, TimeStampedModel):
    """Money spent on something other than goods: fuel, transport, rent, a day labourer...

    It may be charged to one lot (`batch`): then it is a cost of that lot. Tagged to a truck instead, it is a
    truck cost of that day, split over the lots loaded on the truck that day by kg (D-041, D-053). With
    neither it is a general cost. Only an approved expense counts; once approved or refused it never
    changes (a correction is a new expense).
    """

    # "DP-0001", "DP-0002"... per organization, given by the services.
    number = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=ExpenseStatus.choices, default=ExpenseStatus.DRAFT)
    spent_on = models.DateField()
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name="expenses")
    amount = MoneyField()
    payment_method = models.CharField(
        max_length=20, choices=ExpensePaymentMethod.choices, default=ExpensePaymentMethod.CASH
    )
    # What it was: "Gasoil", "Glace pour le camion"...
    description = models.CharField(max_length=255, blank=True)
    # Who was paid, as written on the receipt ("Station Agil Sakiet Ezzit").
    payee = models.CharField(max_length=150, blank=True)
    notes = models.TextField(blank=True)
    # By name, not by import: an app only uses another app's services and selectors (ARCHITECTURE §3).
    batch = models.ForeignKey("inventory.Batch", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    truck = models.ForeignKey("fleet.Truck", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    # The receipt or invoice: a photo (stored as WebP) or a PDF.
    receipt = models.FileField(upload_to=receipt_path, blank=True)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)
    # The driver app sends expenses from the road (P3-T04) and may retry (ARCHITECTURE §4.7).
    client_uuid = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["-spent_on", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "number"], name="expense_number_unique_per_organization"),
            models.UniqueConstraint(
                fields=["organization", "client_uuid"],
                condition=models.Q(client_uuid__isnull=False),
                name="expense_client_uuid_unique_per_organization",
            ),
            models.CheckConstraint(condition=models.Q(amount__gt=Decimal("0")), name="expense_amount_positive"),
            models.CheckConstraint(
                condition=models.Q(batch__isnull=True) | models.Q(truck__isnull=True),
                name="expense_lot_or_truck_not_both",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "status", "spent_on"], name="expense_status_day_idx"),
            models.Index(fields=["organization", "truck", "spent_on"], name="expense_truck_day_idx"),
            models.Index(fields=["organization", "batch"], name="expense_lot_idx"),
        ]

    def __str__(self) -> str:
        return self.number


# ---- Day labour (P5-T03, D-054) ----


class DayLabourer(OrganizationScopedModel, TimeStampedModel):
    """Someone paid by the day when there is work (unloading, sorting, cleaning). Not an employee: no
    payroll, no CNSS (P5-T04 is for employees)."""

    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=30, blank=True)
    # What they are usually paid for a day: proposed when a day is added. Empty when it varies.
    usual_daily_pay = models.DecimalField[Decimal | None, Decimal | None](
        max_digits=14, decimal_places=3, null=True, blank=True
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint("organization", Lower("name"), name="day_labourer_name_unique_per_organization"),
            models.CheckConstraint(
                condition=models.Q(usual_daily_pay__isnull=True) | models.Q(usual_daily_pay__gt=Decimal("0")),
                name="day_labourer_pay_positive",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class WorkType(models.TextChoices):
    # What the day was spent on (client meeting §6); "other" when nobody says.
    LOADING = "loading", _("Chargement, déchargement")
    STOCK = "stock", _("Rangement du stock")
    STORE = "store", _("Magasin")
    CLEANING = "cleaning", _("Nettoyage")
    OTHER = "other", _("Autre")


class DayLabourEntry(OrganizationScopedModel, TimeStampedModel):
    """One day worked by a day labourer, and what they were paid.

    It is **one record with its expense** (category day labour): the expense carries the day, the amount,
    the lot and the approval; this row adds who worked and on what. Typed from a lot or from the calendar,
    it is the same record, so it is never counted twice (D-041, D-054). Without a lot it is a general cost.
    """

    expense = models.OneToOneField(Expense, on_delete=models.CASCADE, related_name="day_labour")
    labourer = models.ForeignKey(DayLabourer, on_delete=models.PROTECT, related_name="entries")
    work_type = models.CharField(max_length=20, choices=WorkType.choices, default=WorkType.OTHER)

    class Meta:
        ordering = ["-expense__spent_on", "labourer__name", "id"]
        verbose_name_plural = "day labour entries"

    def __str__(self) -> str:
        return f"{self.labourer} · {self.expense}"

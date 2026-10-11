from typing import Any

from django.urls import reverse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.expenses.models import Expense, ExpenseCategory, ExpensePaymentMethod, ExpenseStatus, LotCostKind


def person_name(user: Any) -> str:
    if user is None:
        return ""
    return f"{user.first_name} {user.last_name}".strip() or user.username


# ---- Categories (P5-T01) ----


class ExpenseCategorySerializer(serializers.ModelSerializer[ExpenseCategory]):
    class Meta:
        model = ExpenseCategory
        # `code` is set on the default categories only ("fuel", "day_labour"...); empty for the owner's.
        fields = ("id", "code", "name", "is_active")
        read_only_fields = fields


class ExpenseCategoryFilterSerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(choices=["active", "archived", "all"], required=False, default="active")


class ExpenseCategoryWriteSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=200)


class ExpenseCategoryUpdateSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=200, required=False)
    is_active = serializers.BooleanField(required=False)


# ---- Expenses (P5-T01) ----


class ExpenseLotSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    number = serializers.CharField(read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)


class ExpenseTruckSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(source="location.name", read_only=True)
    plate = serializers.CharField(read_only=True)


class ExpenseCategoryRefSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    code = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)


class ExpenseSerializer(serializers.ModelSerializer[Expense]):
    category = ExpenseCategoryRefSerializer(read_only=True)
    batch = ExpenseLotSerializer(read_only=True, allow_null=True)
    truck = ExpenseTruckSerializer(read_only=True, allow_null=True)
    receipt_url = serializers.SerializerMethodField()
    # "application/pdf" or "image/webp"; empty without a receipt.
    receipt_type = serializers.SerializerMethodField()
    entered_by = serializers.SerializerMethodField()
    decided_by = serializers.SerializerMethodField()

    class Meta:
        model = Expense
        fields: tuple[str, ...] = (
            "id",
            "number",
            "status",
            "spent_on",
            "category",
            "amount",
            "payment_method",
            "description",
            "payee",
            "notes",
            "batch",
            "truck",
            "receipt_url",
            "receipt_type",
            "entered_by",
            "created_at",
            "decided_by",
            "decided_at",
            "rejection_reason",
        )
        read_only_fields: tuple[str, ...] = fields

    def get_receipt_url(self, expense: Expense) -> str | None:
        if not expense.receipt.name:
            return None
        return reverse("expense-receipt", args=[expense.pk])

    def get_receipt_type(self, expense: Expense) -> str:
        if not expense.receipt.name:
            return ""
        return "application/pdf" if expense.receipt.name.endswith(".pdf") else "image/webp"

    def get_entered_by(self, expense: Expense) -> str:
        return person_name(expense.entered_by)

    def get_decided_by(self, expense: Expense) -> str:
        return person_name(expense.decided_by)


class TruckDayShareSerializer(serializers.Serializer[Any]):
    batch_id = serializers.IntegerField(read_only=True)
    batch_number = serializers.CharField(read_only=True)
    product_name = serializers.CharField(read_only=True)
    # The lot's kg loaded on the truck that day, and the day's total.
    quantity = serializers.DecimalField(read_only=True, max_digits=12, decimal_places=3)
    day_quantity = serializers.DecimalField(read_only=True, max_digits=12, decimal_places=3)
    amount = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)


class ExpenseDetailSerializer(ExpenseSerializer):
    # A truck cost of the day: its split over the lots loaded on the truck that day (empty otherwise, and
    # empty when nothing was loaded that day: it then stays a general cost).
    shares = serializers.SerializerMethodField()

    class Meta(ExpenseSerializer.Meta):
        fields = (*ExpenseSerializer.Meta.fields, "shares")
        read_only_fields = fields

    @extend_schema_field(TruckDayShareSerializer(many=True))
    def get_shares(self, expense: Expense) -> list[dict[str, Any]]:
        shares = self.context.get("shares", [])
        return list(TruckDayShareSerializer(shares, many=True).data)


class ExpenseWriteSerializer(serializers.Serializer[Any]):
    spent_on = serializers.DateField()
    category = serializers.IntegerField(min_value=1)
    # An amount in DT as a string ("45.500"), checked by the service.
    amount = serializers.CharField(allow_blank=True)
    payment_method = serializers.ChoiceField(
        choices=ExpensePaymentMethod.choices, required=False, default=ExpensePaymentMethod.CASH
    )
    description = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)
    payee = serializers.CharField(required=False, allow_blank=True, default="", max_length=150)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    # A cost of this lot. Or `truck`: a truck cost of that day, split over the lots on board. Not both.
    batch = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None)
    truck = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None)
    # Approve it at once (owner or manager); otherwise it stays a draft.
    approve_now = serializers.BooleanField(required=False, default=False)


class ExpenseRejectSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField(max_length=255, allow_blank=True)


@extend_schema_field(OpenApiTypes.BINARY)
class UploadedFileField(serializers.FileField):
    """A file sent in a multipart form: a Blob in the generated client, not a URL."""


class ExpenseReceiptSerializer(serializers.Serializer[Any]):
    receipt = UploadedFileField()


class ExpenseFilterSerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(choices=ExpenseStatus.choices, required=False)
    category = serializers.IntegerField(required=False, min_value=1)
    batch = serializers.IntegerField(required=False, min_value=1)
    truck = serializers.IntegerField(required=False, min_value=1)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    search = serializers.CharField(required=False, default="", allow_blank=True, max_length=100)


class ExpenseTotalsSerializer(serializers.Serializer[Any]):
    count = serializers.IntegerField(read_only=True)
    # Approved: what counts in the costs. Waiting: drafts and expenses sent for approval.
    approved = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)
    waiting = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)


# ---- Costs of a lot ----


class LotCostFilterSerializer(serializers.Serializer[Any]):
    batch = serializers.IntegerField(min_value=1)


class LotCostLineSerializer(serializers.Serializer[Any]):
    # "lot": an expense typed on the lot; "truck_day": its share of a truck's costs that day.
    kind = serializers.ChoiceField(choices=LotCostKind.choices, read_only=True)
    expense_id = serializers.IntegerField(read_only=True)
    expense_number = serializers.CharField(read_only=True)
    status = serializers.ChoiceField(choices=ExpenseStatus.choices, read_only=True)
    spent_on = serializers.DateField(read_only=True)
    category_code = serializers.CharField(read_only=True)
    category_name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    amount = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)
    expense_amount = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)
    truck_name = serializers.CharField(read_only=True)
    quantity = serializers.DecimalField(read_only=True, allow_null=True, max_digits=12, decimal_places=3)
    day_quantity = serializers.DecimalField(read_only=True, allow_null=True, max_digits=12, decimal_places=3)


class LotCostsSerializer(serializers.Serializer[Any]):
    batch_id = serializers.IntegerField(read_only=True)
    # Approved lines only: the lot's costs so far.
    total = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)
    # Approved lines, then drafts and waiting ones (shown, not counted).
    lines = LotCostLineSerializer(many=True, read_only=True)

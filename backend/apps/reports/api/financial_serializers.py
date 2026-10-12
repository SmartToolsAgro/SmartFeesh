import datetime as dt
from typing import Any

from django.utils import timezone
from rest_framework import serializers

from .serializers import PeriodQuerySerializer

# Read-only amounts: DT with three decimals.
MONEY: dict[str, Any] = {"read_only": True, "max_digits": 14, "decimal_places": 3}
CASH_GROUPS = ("day", "week", "month")


class MonthQuerySerializer(serializers.Serializer):  # type: ignore[type-arg]
    """`month`: any day of the month wanted (default: the current month)."""

    month = serializers.DateField(required=False)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        month = attrs.get("month") or timezone.localdate()
        assert isinstance(month, dt.date)
        attrs["month"] = month.replace(day=1)
        return attrs


class CashQuerySerializer(PeriodQuerySerializer):
    group_by = serializers.ChoiceField(choices=CASH_GROUPS, default="day")


class CategoryLineSerializer(serializers.Serializer):  # type: ignore[type-arg]
    name = serializers.CharField()
    count = serializers.IntegerField()
    total = serializers.DecimalField(**MONEY)


class MonthResultSerializer(serializers.Serializer):  # type: ignore[type-arg]
    month = serializers.DateField()
    sales_count = serializers.IntegerField()
    quantity_sold = serializers.DecimalField(**MONEY)
    revenue = serializers.DecimalField(**MONEY)
    cogs = serializers.DecimalField(**MONEY)
    gross_margin = serializers.DecimalField(**MONEY)
    spoilage = serializers.DecimalField(**MONEY)
    expenses_total = serializers.DecimalField(**MONEY)
    personnel = serializers.DecimalField(**MONEY)
    net_result = serializers.DecimalField(**MONEY)
    categories = CategoryLineSerializer(many=True)


class CashLineSerializer(serializers.Serializer):  # type: ignore[type-arg]
    key = serializers.CharField()
    cash_in = serializers.DecimalField(**MONEY)
    cash_out = serializers.DecimalField(**MONEY)
    net = serializers.DecimalField(**MONEY)


class CashFlowSerializer(serializers.Serializer):  # type: ignore[type-arg]
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    group_by = serializers.ChoiceField(choices=CASH_GROUPS)
    rows = CashLineSerializer(many=True)
    total_in = serializers.DecimalField(**MONEY)
    total_out = serializers.DecimalField(**MONEY)
    net = serializers.DecimalField(**MONEY)


class CustomerLineSerializer(serializers.Serializer):  # type: ignore[type-arg]
    customer_id = serializers.IntegerField()
    name = serializers.CharField()
    balance = serializers.DecimalField(**MONEY)
    overdue = serializers.DecimalField(**MONEY)
    credit = serializers.DecimalField(**MONEY)
    d0_30 = serializers.DecimalField(**MONEY)
    d31_60 = serializers.DecimalField(**MONEY)
    d60_plus = serializers.DecimalField(**MONEY)


class CustomerBalancesSerializer(serializers.Serializer):  # type: ignore[type-arg]
    rows = CustomerLineSerializer(many=True)
    total_balance = serializers.DecimalField(**MONEY)
    total_overdue = serializers.DecimalField(**MONEY)
    d0_30 = serializers.DecimalField(**MONEY)
    d31_60 = serializers.DecimalField(**MONEY)
    d60_plus = serializers.DecimalField(**MONEY)


class SupplierLineSerializer(serializers.Serializer):  # type: ignore[type-arg]
    supplier_id = serializers.IntegerField()
    name = serializers.CharField()
    invoiced = serializers.DecimalField(**MONEY)
    paid = serializers.DecimalField(**MONEY)
    balance = serializers.DecimalField(**MONEY)
    outstanding = serializers.DecimalField(**MONEY)
    overdue = serializers.DecimalField(**MONEY)
    uninvoiced = serializers.DecimalField(**MONEY)


class SupplierBalancesSerializer(serializers.Serializer):  # type: ignore[type-arg]
    rows = SupplierLineSerializer(many=True)
    total_balance = serializers.DecimalField(**MONEY)
    total_overdue = serializers.DecimalField(**MONEY)
    total_uninvoiced = serializers.DecimalField(**MONEY)


class SalaryLineSerializer(serializers.Serializer):  # type: ignore[type-arg]
    employee_id = serializers.IntegerField()
    name = serializers.CharField()
    unpaid = serializers.DecimalField(**MONEY)


class UnpaidSalariesSerializer(serializers.Serializer):  # type: ignore[type-arg]
    rows = SalaryLineSerializer(many=True)
    total = serializers.DecimalField(**MONEY)


class PartnerLineSerializer(serializers.Serializer):  # type: ignore[type-arg]
    partner_id = serializers.IntegerField()
    name = serializers.CharField()
    lots = serializers.IntegerField()
    contributed = serializers.DecimalField(**MONEY)
    loss_deducted = serializers.DecimalField(**MONEY)
    returned = serializers.DecimalField(**MONEY)
    capital_outstanding = serializers.DecimalField(**MONEY)
    share = serializers.DecimalField(**MONEY)
    uncovered_loss = serializers.DecimalField(**MONEY)
    late_adjustments = serializers.DecimalField(**MONEY)
    paid = serializers.DecimalField(**MONEY)
    share_due = serializers.DecimalField(**MONEY)


class PartnerReportSerializer(serializers.Serializer):  # type: ignore[type-arg]
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    rows = PartnerLineSerializer(many=True)
    totals = PartnerLineSerializer()

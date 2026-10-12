from typing import Any

from rest_framework import serializers

from apps.dayclose.models import DayClosing, DayClosingStatus


class DayProductSerializer(serializers.Serializer[Any]):
    product_id = serializers.IntegerField(read_only=True)
    product_name = serializers.CharField(read_only=True)
    loaded = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)
    sold = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)
    lost = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)
    returned = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)
    remaining = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)


class DaySummarySerializer(serializers.Serializer[Any]):
    date = serializers.DateField(read_only=True)
    truck_name = serializers.CharField(read_only=True)
    driver_name = serializers.CharField(read_only=True)
    opening_cash = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    sales_count = serializers.IntegerField(read_only=True)
    sales_total = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    cash_received = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    other_payments = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    on_credit = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    expenses_total = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    expected_cash = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    products = DayProductSerializer(many=True, read_only=True)


class DayClosingStateSerializer(serializers.ModelSerializer[DayClosing]):
    """What the driver sees of their closing."""

    class Meta:
        model = DayClosing
        fields = ("id", "status", "counted_cash", "driver_note", "review_note", "submitted_at")
        read_only_fields = fields


class MyDaySummarySerializer(serializers.Serializer[Any]):
    summary = DaySummarySerializer(read_only=True)
    closing = DayClosingStateSerializer(read_only=True, allow_null=True)


class DayClosingWriteSerializer(serializers.Serializer[Any]):
    # The cash in the driver's hands, in DT as a string ("250.500").
    counted_cash = serializers.CharField(allow_blank=True)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class DayClosingRowSerializer(serializers.ModelSerializer[DayClosing]):
    date = serializers.DateField(source="driver_day.date", read_only=True)
    truck_name = serializers.CharField(source="driver_day.truck.location.name", read_only=True)
    driver_name = serializers.SerializerMethodField()
    status = serializers.ChoiceField(choices=DayClosingStatus.choices, read_only=True)

    class Meta:
        model = DayClosing
        fields: tuple[str, ...] = (
            "id",
            "date",
            "truck_name",
            "driver_name",
            "status",
            "expected_cash",
            "counted_cash",
            "difference",
        )
        read_only_fields = fields

    def get_driver_name(self, closing: DayClosing) -> str:
        driver = closing.driver_day.driver
        return f"{driver.first_name} {driver.last_name}".strip() or driver.username


class DayClosingDetailSerializer(DayClosingRowSerializer):
    summary = DaySummarySerializer(read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta(DayClosingRowSerializer.Meta):
        fields: tuple[str, ...] = (
            *DayClosingRowSerializer.Meta.fields,
            "driver_note",
            "review_note",
            "submitted_at",
            "reviewed_at",
            "reviewed_by_name",
            "summary",
        )
        read_only_fields = fields

    def get_reviewed_by_name(self, closing: DayClosing) -> str:
        user = closing.reviewed_by
        if user is None:
            return ""
        return f"{user.first_name} {user.last_name}".strip() or user.username


class DayClosingFilterSerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(choices=DayClosingStatus.choices, required=False)


class JustificationSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField(allow_blank=True, max_length=300)

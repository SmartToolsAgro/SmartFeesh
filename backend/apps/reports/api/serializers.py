import datetime as dt

from django.utils import timezone
from rest_framework import serializers

from apps.reports.selectors import GROUPS


class PeriodQuerySerializer(serializers.Serializer):  # type: ignore[type-arg]
    """`date_from` / `date_to` (inclusive), by default the current month so far."""

    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        today = timezone.localdate()
        first = attrs.get("date_from") or today.replace(day=1)
        last = attrs.get("date_to") or today
        assert isinstance(first, dt.date)
        assert isinstance(last, dt.date)
        if last < first:
            raise serializers.ValidationError("La date de fin précède la date de début.")
        attrs["date_from"], attrs["date_to"] = first, last
        return attrs


class SalesQuerySerializer(PeriodQuerySerializer):
    group_by = serializers.ChoiceField(choices=GROUPS, default="customer")


class SlowQuerySerializer(serializers.Serializer):  # type: ignore[type-arg]
    days = serializers.IntegerField(min_value=0, max_value=3650, default=30)


class SalesLineSerializer(serializers.Serializer):  # type: ignore[type-arg]
    key = serializers.CharField()
    name = serializers.CharField()
    sales = serializers.IntegerField()
    quantity = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)
    revenue = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)
    cogs = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)
    margin = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)


class SalesReportSerializer(serializers.Serializer):  # type: ignore[type-arg]
    group_by = serializers.ChoiceField(choices=GROUPS)
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    rows = SalesLineSerializer(many=True)
    totals = SalesLineSerializer()


class StockValueRowSerializer(serializers.Serializer):  # type: ignore[type-arg]
    location_id = serializers.IntegerField()
    location_name = serializers.CharField()
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    quantity = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)
    value = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)


class StockValueReportSerializer(serializers.Serializer):  # type: ignore[type-arg]
    rows = StockValueRowSerializer(many=True)
    total_quantity = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)
    total_value = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)


class SlowLotSerializer(serializers.Serializer):  # type: ignore[type-arg]
    batch_id = serializers.IntegerField()
    batch_number = serializers.CharField()
    product_name = serializers.CharField()
    supplier_name = serializers.CharField()
    received_on = serializers.DateField()
    last_movement_on = serializers.DateField()
    days_idle = serializers.IntegerField()
    quantity = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)
    value = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)


class SlowReportSerializer(serializers.Serializer):  # type: ignore[type-arg]
    days = serializers.IntegerField()
    rows = SlowLotSerializer(many=True)
    total_quantity = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)
    total_value = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)


class ProductLossSerializer(serializers.Serializer):  # type: ignore[type-arg]
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    lost_quantity = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)
    lost_value = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)
    difference_quantity = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)
    difference_value = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)


class LossReportSerializer(serializers.Serializer):  # type: ignore[type-arg]
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    rows = ProductLossSerializer(many=True)
    total_lost_quantity = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)
    total_lost_value = serializers.DecimalField(read_only=True, max_digits=14, decimal_places=3)

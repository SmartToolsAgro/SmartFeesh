from typing import Any

from rest_framework import serializers

from apps.inventory.models import Batch, LocationKind, StockLocation


class StockLocationSerializer(serializers.ModelSerializer[StockLocation]):
    # Whether sales may be made from here: always for a truck, at the counter for the others (Q8).
    sells = serializers.BooleanField(read_only=True)

    class Meta:
        model = StockLocation
        fields = ("id", "kind", "name", "counter_sales", "sells", "is_active", "updated_at")
        read_only_fields = fields


class StockLocationCreateSerializer(serializers.Serializer[Any]):
    # Trucks are created with their truck (`createTruck`), which makes their location.
    kind = serializers.ChoiceField(
        choices=[(LocationKind.COLD_ROOM, LocationKind.COLD_ROOM.label), (LocationKind.OTHER, LocationKind.OTHER.label)]
    )
    name = serializers.CharField(max_length=100)
    counter_sales = serializers.BooleanField(required=False, default=False)


class StockLocationUpdateSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=100, required=False)
    counter_sales = serializers.BooleanField(required=False)


class StockLocationFilterSerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(
        choices=[("active", "active"), ("archived", "archived"), ("all", "all")], required=False, default="active"
    )
    kind = serializers.ChoiceField(choices=LocationKind.choices, required=False)


class BatchProductSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    reference = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)


class BatchSupplierSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    reference = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)


class BatchSerializer(serializers.ModelSerializer[Batch]):
    product = BatchProductSerializer(read_only=True)
    supplier = BatchSupplierSerializer(read_only=True)

    class Meta:
        model = Batch
        fields = (
            "id",
            "number",
            "product",
            "supplier",
            "receipt_reference",
            "received_on",
            "unit_cost",
            "use_by",
            "created_at",
        )
        read_only_fields = fields


class BatchFilterSerializer(serializers.Serializer[Any]):
    product = serializers.IntegerField(required=False, min_value=1)
    supplier = serializers.IntegerField(required=False, min_value=1)
    search = serializers.CharField(required=False, default="", allow_blank=True, max_length=100)

from typing import Any

from rest_framework import serializers

from apps.inventory.models import LocationKind, StockLocation


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

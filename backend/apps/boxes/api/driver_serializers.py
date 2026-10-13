from typing import Any

from rest_framework import serializers

from apps.boxes.models import BoxType


class TruckBoxDaySerializer(serializers.Serializer[Any]):
    """One box type on the driver's truck today. Whole boxes only."""

    box_type = serializers.ChoiceField(choices=BoxType.choices, read_only=True)
    loaded = serializers.IntegerField(read_only=True)
    left = serializers.IntegerField(read_only=True)
    collected = serializers.IntegerField(read_only=True)
    expected = serializers.IntegerField(read_only=True)


class MyBoxDaySerializer(serializers.Serializer[Any]):
    """The driver's boxes today: what the truck loaded, left at clients and collected back, per box type."""

    date = serializers.DateField(read_only=True)
    truck_name = serializers.CharField(read_only=True)
    lines = TruckBoxDaySerializer(many=True, read_only=True)


class MyBoxPickupWriteSerializer(serializers.Serializer[Any]):
    customer = serializers.IntegerField(min_value=1)
    # Boxes collected per box type ("small", "big"): a count, never kg. Zero means none.
    boxes = serializers.DictField(child=serializers.IntegerField(min_value=0), default=dict)

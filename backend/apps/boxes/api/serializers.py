from typing import Any

from rest_framework import serializers

from apps.boxes.models import BoxHolder, BoxMovement, BoxMovementKind, BoxType
from apps.boxes.selectors import BoxBalance


def holder_name(holder: BoxHolder | None) -> str | None:
    """What a holder is called: its location, client or supplier."""
    if holder is None:
        return None
    target = holder.location or holder.customer or holder.supplier
    return target.name if target is not None else None


class BoxBalanceSerializer(serializers.Serializer[Any]):
    """Boxes of one type one holder has now. A supplier's count is what we owe it."""

    holder_id = serializers.IntegerField(source="holder.pk", read_only=True)
    holder_kind = serializers.CharField(source="holder.target_kind", read_only=True)
    holder_name = serializers.SerializerMethodField()
    box_type = serializers.ChoiceField(choices=BoxType.choices, read_only=True)
    count = serializers.IntegerField(read_only=True)

    def get_holder_name(self, row: BoxBalance) -> str | None:
        return holder_name(row.holder)


class BoxMovementSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    kind = serializers.ChoiceField(choices=BoxMovementKind.choices, read_only=True)
    box_type = serializers.ChoiceField(choices=BoxType.choices, read_only=True)
    count = serializers.IntegerField(read_only=True)
    from_holder = serializers.IntegerField(source="from_holder_id", read_only=True, allow_null=True)
    from_holder_name = serializers.SerializerMethodField()
    to_holder = serializers.IntegerField(source="to_holder_id", read_only=True, allow_null=True)
    to_holder_name = serializers.SerializerMethodField()
    reason = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    def get_from_holder_name(self, movement: BoxMovement) -> str | None:
        return holder_name(movement.from_holder)

    def get_to_holder_name(self, movement: BoxMovement) -> str | None:
        return holder_name(movement.to_holder)


class BoxMovementFilterSerializer(serializers.Serializer[Any]):
    # A holder's id, as the balances list gives it: its movements on either side.
    holder = serializers.IntegerField(required=False, min_value=1)
    box_type = serializers.ChoiceField(choices=BoxType.choices, required=False)


class BoxAdjustmentWriteSerializer(serializers.Serializer[Any]):
    location = serializers.IntegerField(min_value=1)
    box_type = serializers.ChoiceField(choices=BoxType.choices)
    kind = serializers.ChoiceField(choices=[BoxMovementKind.PURCHASE.value, BoxMovementKind.WRITE_OFF.value])
    count = serializers.IntegerField(min_value=1, max_value=100000)
    # Required for a loss or a breakage; a free note for a purchase.
    reason = serializers.CharField(required=False, allow_blank=True, default="", max_length=300)

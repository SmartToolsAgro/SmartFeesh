from decimal import Decimal
from typing import Any

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.money import line_total
from apps.inventory.models import (
    Batch,
    LocationKind,
    StockLocation,
    Transfer,
    TransferKind,
    TransferLine,
    TransferStatus,
)


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


class LocationStockSerializer(serializers.Serializer[Any]):
    """How many kg of one product a location holds, all batches together."""

    product_id = serializers.IntegerField(read_only=True)
    product_reference = serializers.CharField(source="product__reference", read_only=True)
    product_name = serializers.CharField(source="product__name", read_only=True)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)


# ---- Transfers (P1-T09) ----


def person_name(user: Any) -> str:
    if user is None:
        return ""
    return f"{user.first_name} {user.last_name}".strip() or user.username


class PlaceSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    kind = serializers.ChoiceField(choices=LocationKind.choices, read_only=True)


class MovedBatchSerializer(serializers.Serializer[Any]):
    """One batch a line took, oldest first: the movement posted for it."""

    batch_id = serializers.IntegerField(read_only=True)
    batch_number = serializers.CharField(source="batch.number", read_only=True)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)


class TransferLineSerializer(serializers.ModelSerializer[TransferLine]):
    product = BatchProductSerializer(read_only=True)
    # Kg × the day's price, for a load line; empty otherwise.
    amount = serializers.SerializerMethodField()

    class Meta:
        model = TransferLine
        fields: tuple[str, ...] = ("id", "product", "quantity", "unit_price", "amount")
        read_only_fields: tuple[str, ...] = fields

    @extend_schema_field(serializers.DecimalField(max_digits=14, decimal_places=3, allow_null=True))
    def get_amount(self, line: TransferLine) -> str | None:
        if line.unit_price is None:
            return None
        return str(line_total(line.quantity, line.unit_price))


class TransferLineDetailSerializer(TransferLineSerializer):
    # Filled once the transfer is validated: which batches the kg came from (FIFO).
    batches = serializers.SerializerMethodField()

    class Meta(TransferLineSerializer.Meta):
        fields = (*TransferLineSerializer.Meta.fields, "batches")
        read_only_fields = fields

    @extend_schema_field(MovedBatchSerializer(many=True))
    def get_batches(self, line: TransferLine) -> list[dict[str, Any]]:
        movements = self.context.get("movements", {}).get(line.pk, [])
        return list(MovedBatchSerializer(movements, many=True).data)


class TransferSerializer(serializers.ModelSerializer[Transfer]):
    from_location = PlaceSerializer(read_only=True)
    to_location = PlaceSerializer(read_only=True)
    lines = TransferLineSerializer(many=True, read_only=True)
    total_quantity = serializers.SerializerMethodField()
    # Sum of the load lines' amounts at the day's prices; empty for a return or a move between cold rooms.
    total_amount = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    validated_by = serializers.SerializerMethodField()
    confirmed_by = serializers.SerializerMethodField()

    class Meta:
        model = Transfer
        fields: tuple[str, ...] = (
            "id",
            "number",
            "kind",
            "status",
            "from_location",
            "to_location",
            "transferred_on",
            "notes",
            "lines",
            "total_quantity",
            "total_amount",
            "created_by",
            "created_at",
            "validated_by",
            "validated_at",
            "confirmed_by",
            "confirmed_at",
        )
        read_only_fields: tuple[str, ...] = fields

    @extend_schema_field(serializers.DecimalField(max_digits=12, decimal_places=3))
    def get_total_quantity(self, transfer: Transfer) -> str:
        return str(sum((line.quantity for line in transfer.lines.all()), Decimal("0.000")))

    @extend_schema_field(serializers.DecimalField(max_digits=14, decimal_places=3, allow_null=True))
    def get_total_amount(self, transfer: Transfer) -> str | None:
        priced = [line for line in transfer.lines.all() if line.unit_price is not None]
        if not priced:
            return None
        return str(sum((line_total(line.quantity, line.unit_price or 0) for line in priced), Decimal("0.000")))

    def get_created_by(self, transfer: Transfer) -> str:
        return person_name(transfer.created_by)

    def get_validated_by(self, transfer: Transfer) -> str:
        return person_name(transfer.validated_by)

    def get_confirmed_by(self, transfer: Transfer) -> str:
        return person_name(transfer.confirmed_by)


class TransferDetailSerializer(TransferSerializer):
    lines = TransferLineDetailSerializer(many=True, read_only=True)

    class Meta(TransferSerializer.Meta):
        pass


class TransferLineWriteSerializer(serializers.Serializer[Any]):
    product = serializers.IntegerField(min_value=1)
    # Weights and prices travel as strings ("12.500") and are checked by the service, which reports each
    # problem on `lines.<index>.<field>`.
    quantity = serializers.CharField(allow_blank=True)
    # A load only: DT per kg of the day. Empty takes the sale price in force.
    unit_price = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None)


class TransferWriteSerializer(serializers.Serializer[Any]):
    from_location = serializers.IntegerField(min_value=1)
    to_location = serializers.IntegerField(min_value=1)
    transferred_on = serializers.DateField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lines = TransferLineWriteSerializer(many=True, allow_empty=True)
    # Validate at once (moves the stock); otherwise the transfer stays a draft.
    validate_now = serializers.BooleanField(required=False, default=False)


class TransferFilterSerializer(serializers.Serializer[Any]):
    kind = serializers.ChoiceField(choices=TransferKind.choices, required=False)
    status = serializers.ChoiceField(choices=TransferStatus.choices, required=False)
    location = serializers.IntegerField(required=False, min_value=1)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    search = serializers.CharField(required=False, default="", allow_blank=True, max_length=100)


class TruckDayFilterSerializer(serializers.Serializer[Any]):
    location = serializers.IntegerField(min_value=1)
    date = serializers.DateField()


class TruckDayLineSerializer(serializers.Serializer[Any]):
    product_id = serializers.IntegerField(read_only=True)
    product_reference = serializers.CharField(read_only=True)
    product_name = serializers.CharField(read_only=True)
    loaded = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)
    returned = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)
    # Loaded − returned: sold or lost. Negative when more came back than was loaded that day.
    sold_or_lost = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)
    unit_price = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True, allow_null=True)
    # Sold or lost × the day's price.
    amount = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True, allow_null=True)


class TruckDaySerializer(serializers.Serializer[Any]):
    location = PlaceSerializer(read_only=True)
    date = serializers.DateField(read_only=True)
    lines = TruckDayLineSerializer(many=True, read_only=True)
    amount = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)

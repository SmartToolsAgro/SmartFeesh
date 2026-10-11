from typing import Any

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.purchasing import selectors
from apps.purchasing.models import GoodsReceipt, GoodsReceiptLine

AMOUNT = serializers.DecimalField(max_digits=14, decimal_places=3)


class RefSerializer(serializers.Serializer[Any]):
    """A supplier or a product, as shown on a receipt."""

    id = serializers.IntegerField(read_only=True)
    reference = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)


class ReceiptLocationSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)


class ReceiptBatchSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    number = serializers.CharField(read_only=True)
    use_by = serializers.DateField(read_only=True, allow_null=True)


class ReceiptLineSerializer(serializers.ModelSerializer[GoodsReceiptLine]):
    product = RefSerializer(read_only=True)
    batch = ReceiptBatchSerializer(read_only=True)
    # Invoiced weight × cost: what the supplier charges for the line.
    invoiced_amount = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    # Accepted weight × cost: the value that entered stock.
    accepted_amount = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    has_difference = serializers.BooleanField(read_only=True)

    class Meta:
        model = GoodsReceiptLine
        fields: tuple[str, ...] = (
            "id",
            "product",
            "batch",
            "ordered_quantity",
            "invoiced_quantity",
            "accepted_quantity",
            "unit_cost",
            "invoiced_amount",
            "accepted_amount",
            "has_difference",
        )
        read_only_fields: tuple[str, ...] = fields


class ReceiptSerializer(serializers.ModelSerializer[GoodsReceipt]):
    supplier = RefSerializer(read_only=True)
    location = ReceiptLocationSerializer(read_only=True)
    lines = ReceiptLineSerializer(many=True, read_only=True)
    has_differences = serializers.BooleanField(read_only=True)
    invoiced_total = serializers.SerializerMethodField()
    accepted_total = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = GoodsReceipt
        fields = (
            "id",
            "number",
            "supplier",
            "location",
            "received_on",
            "supplier_reference",
            "notes",
            "lines",
            "has_differences",
            "invoiced_total",
            "accepted_total",
            "created_by",
            "created_at",
        )
        read_only_fields = fields

    @extend_schema_field(AMOUNT)
    def get_invoiced_total(self, receipt: GoodsReceipt) -> str:
        return str(selectors.receipt_totals(receipt)[0])

    @extend_schema_field(AMOUNT)
    def get_accepted_total(self, receipt: GoodsReceipt) -> str:
        return str(selectors.receipt_totals(receipt)[1])

    def get_created_by(self, receipt: GoodsReceipt) -> str:
        user = receipt.created_by
        if user is None:
            return ""
        return f"{user.first_name} {user.last_name}".strip() or user.username


class ReceiptLineWriteSerializer(serializers.Serializer[Any]):
    product = serializers.IntegerField(min_value=1)
    # Weights and cost travel as strings ("62.000") and are checked by the service, which reports each
    # problem on `lines.<index>.<field>`.
    ordered_quantity = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None)
    invoiced_quantity = serializers.CharField(allow_blank=True)
    accepted_quantity = serializers.CharField(allow_blank=True)
    unit_cost = serializers.CharField(allow_blank=True)
    use_by = serializers.DateField(required=False, allow_null=True, default=None)


class ReceiptWriteSerializer(serializers.Serializer[Any]):
    supplier = serializers.IntegerField(min_value=1)
    location = serializers.IntegerField(min_value=1)
    received_on = serializers.DateField()
    supplier_reference = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lines = ReceiptLineWriteSerializer(many=True, allow_empty=True)


class ReceiptFilterSerializer(serializers.Serializer[Any]):
    supplier = serializers.IntegerField(required=False, min_value=1)
    search = serializers.CharField(required=False, default="", allow_blank=True, max_length=100)
    # Only receipts with a weight difference on at least one line.
    differences = serializers.BooleanField(required=False, default=False)


class ReceiptRefSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    number = serializers.CharField(read_only=True)
    received_on = serializers.DateField(read_only=True)
    supplier = RefSerializer(read_only=True)


class DifferenceLineSerializer(ReceiptLineSerializer):
    receipt = ReceiptRefSerializer(read_only=True)

    class Meta(ReceiptLineSerializer.Meta):
        fields = ("receipt", *ReceiptLineSerializer.Meta.fields)
        read_only_fields = fields


class DifferenceFilterSerializer(serializers.Serializer[Any]):
    supplier = serializers.IntegerField(required=False, min_value=1)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)


class LastCostSerializer(serializers.Serializer[Any]):
    """What was last paid a supplier for one product: the cost of their latest batch of it."""

    product_id = serializers.IntegerField(read_only=True)
    unit_cost = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    received_on = serializers.DateField(read_only=True)
    batch_number = serializers.CharField(source="number", read_only=True)


class LastCostFilterSerializer(serializers.Serializer[Any]):
    supplier = serializers.IntegerField(min_value=1)

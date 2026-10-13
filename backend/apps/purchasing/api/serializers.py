from decimal import Decimal
from typing import Any

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.purchasing import selectors
from apps.purchasing.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PaymentMethod,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    SupplierInvoice,
    SupplierInvoiceStatus,
    SupplierPayment,
)

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


class InvoiceRefSerializer(serializers.Serializer[Any]):
    """The supplier invoice a receipt is charged on."""

    id = serializers.IntegerField(read_only=True)
    number = serializers.CharField(read_only=True)
    status = serializers.ChoiceField(choices=SupplierInvoiceStatus.choices, read_only=True)


class OrderRefSerializer(serializers.Serializer[Any]):
    """The purchase order a receipt delivers against."""

    id = serializers.IntegerField(read_only=True)
    number = serializers.CharField(read_only=True)
    status = serializers.ChoiceField(choices=PurchaseOrderStatus.choices, read_only=True)


class ReceiptSerializer(serializers.ModelSerializer[GoodsReceipt]):
    supplier = RefSerializer(read_only=True)
    # The bon d'achat this delivery is against, or null for goods that came without one.
    purchase_order = OrderRefSerializer(read_only=True, allow_null=True)
    location = ReceiptLocationSerializer(read_only=True)
    lines = ReceiptLineSerializer(many=True, read_only=True)
    has_differences = serializers.BooleanField(read_only=True)
    invoiced_total = serializers.SerializerMethodField()
    accepted_total = serializers.SerializerMethodField()
    # The supplier invoice it is on (draft or posted), or null while not invoiced.
    invoice = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = GoodsReceipt
        fields = (
            "id",
            "number",
            "supplier",
            "location",
            "purchase_order",
            "received_on",
            "supplier_reference",
            "notes",
            "lines",
            "has_differences",
            "invoiced_total",
            "accepted_total",
            "invoice",
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

    @extend_schema_field(InvoiceRefSerializer(allow_null=True))
    def get_invoice(self, receipt: GoodsReceipt) -> dict[str, Any] | None:
        link = getattr(receipt, "invoice_link", None)
        return None if link is None else dict(InvoiceRefSerializer(link.invoice).data)

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
    # Buy this lot together with a partner supplier (D-100): the owner's choice, the receipt's own supplier
    # allowed. Capital and percentages are filled in later, on the lot.
    partner = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None)


class ReceiptWriteSerializer(serializers.Serializer[Any]):
    supplier = serializers.IntegerField(min_value=1)
    location = serializers.IntegerField(min_value=1)
    # Deliver against this bon d'achat: its products only, as much of each as arrived (D-076).
    purchase_order = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None)
    received_on = serializers.DateField()
    supplier_reference = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lines = ReceiptLineWriteSerializer(many=True, allow_empty=True)
    # Returnable boxes that came with the delivery, per box type ("small", "big"): a count, never kg (D-122).
    boxes = serializers.DictField(child=serializers.IntegerField(min_value=0), required=False, default=dict)


class ReceiptFilterSerializer(serializers.Serializer[Any]):
    supplier = serializers.IntegerField(required=False, min_value=1)
    search = serializers.CharField(required=False, default="", allow_blank=True, max_length=100)
    # Only receipts with a weight difference on at least one line.
    differences = serializers.BooleanField(required=False, default=False)
    # Only receipts not on any supplier invoice yet (draft or posted).
    uninvoiced = serializers.BooleanField(required=False, default=False)
    # Only the receipts against this purchase order.
    purchase_order = serializers.IntegerField(required=False, min_value=1)


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


# ---- Purchase orders, the "bon d'achat" (D-076) ----


class OrderReceiptRefSerializer(serializers.Serializer[Any]):
    """A delivery against an order: its receipt."""

    id = serializers.IntegerField(read_only=True)
    number = serializers.CharField(read_only=True)
    received_on = serializers.DateField(read_only=True)


class OrderLineSerializer(serializers.ModelSerializer[PurchaseOrderLine]):
    product = RefSerializer(read_only=True)
    ordered_amount = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    # Accepted weight of the receipts against this line, and what is still to come.
    received_quantity = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)
    remaining_quantity = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrderLine
        fields: tuple[str, ...] = (
            "id",
            "product",
            "ordered_quantity",
            "unit_cost",
            "ordered_amount",
            "received_quantity",
            "remaining_quantity",
        )
        read_only_fields: tuple[str, ...] = fields

    @extend_schema_field(serializers.DecimalField(max_digits=12, decimal_places=3))
    def get_remaining_quantity(self, line: PurchaseOrderLine) -> str:
        return str(selectors.order_line_remaining(line))


class OrderSerializer(serializers.ModelSerializer[PurchaseOrder]):
    supplier = RefSerializer(read_only=True)
    lines = OrderLineSerializer(many=True, read_only=True)
    receipts = serializers.SerializerMethodField()
    ordered_total = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrder
        fields = (
            "id",
            "number",
            "supplier",
            "ordered_on",
            "expected_on",
            "status",
            "notes",
            "lines",
            "receipts",
            "ordered_total",
            "created_by",
            "created_at",
            "closed_at",
        )
        read_only_fields = fields

    @extend_schema_field(OrderReceiptRefSerializer(many=True))
    def get_receipts(self, order: PurchaseOrder) -> list[dict[str, Any]]:
        return [dict(OrderReceiptRefSerializer(receipt).data) for receipt in order.receipts.all()]

    @extend_schema_field(AMOUNT)
    def get_ordered_total(self, order: PurchaseOrder) -> str:
        return str(sum((line.ordered_amount for line in order.lines.all()), Decimal("0.000")))

    def get_created_by(self, order: PurchaseOrder) -> str:
        user = order.created_by
        if user is None:
            return ""
        return f"{user.first_name} {user.last_name}".strip() or user.username


class OrderLineWriteSerializer(serializers.Serializer[Any]):
    product = serializers.IntegerField(min_value=1)
    # Strings, checked by the service, which reports each problem on `lines.<index>.<field>`.
    ordered_quantity = serializers.CharField(allow_blank=True)
    unit_cost = serializers.CharField(allow_blank=True)


class OrderWriteSerializer(serializers.Serializer[Any]):
    supplier = serializers.IntegerField(min_value=1)
    ordered_on = serializers.DateField()
    expected_on = serializers.DateField(required=False, allow_null=True, default=None)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lines = OrderLineWriteSerializer(many=True, allow_empty=True)


class OrderFilterSerializer(serializers.Serializer[Any]):
    supplier = serializers.IntegerField(required=False, min_value=1)
    # `pending` = open or partly received: still waiting for goods.
    status = serializers.ChoiceField(choices=[*PurchaseOrderStatus.choices, ("pending", "pending")], required=False)
    search = serializers.CharField(required=False, default="", allow_blank=True, max_length=100)


# ---- Supplier invoices and payments (P1-T08, D-043) ----


class InvoiceReceiptRefSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    number = serializers.CharField(read_only=True)
    received_on = serializers.DateField(read_only=True)
    supplier_reference = serializers.CharField(read_only=True)


class InvoiceReceiptSerializer(serializers.Serializer[Any]):
    """A receipt charged on the invoice, with its invoiced amount (invoiced kg × cost of its lines)."""

    receipt = InvoiceReceiptRefSerializer(read_only=True)
    amount = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)


class PaymentRefSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    number = serializers.CharField(read_only=True)
    paid_on = serializers.DateField(read_only=True)
    method = serializers.ChoiceField(choices=PaymentMethod.choices, read_only=True)
    reference = serializers.CharField(read_only=True)


class InvoicePaymentSerializer(serializers.Serializer[Any]):
    """The part of one payment that settled the invoice."""

    id = serializers.IntegerField(read_only=True)
    payment = PaymentRefSerializer(read_only=True)
    amount = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)


def _name_of(user: Any) -> str:
    if user is None:
        return ""
    return f"{user.first_name} {user.last_name}".strip() or str(user.username)


class SupplierInvoiceSerializer(serializers.ModelSerializer[SupplierInvoice]):
    supplier = RefSerializer(read_only=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    # Allocated by payments so far; `outstanding` = total − paid.
    paid_amount = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    outstanding = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    is_overdue = serializers.SerializerMethodField()
    receipts = InvoiceReceiptSerializer(source="receipt_links", many=True, read_only=True)
    payments = InvoicePaymentSerializer(source="allocations", many=True, read_only=True)
    created_by = serializers.SerializerMethodField()
    posted_by = serializers.SerializerMethodField()

    class Meta:
        model = SupplierInvoice
        fields = (
            "id",
            "number",
            "supplier",
            "supplier_reference",
            "invoice_date",
            "due_date",
            "status",
            "total",
            "paid_amount",
            "outstanding",
            "is_overdue",
            "receipts",
            "payments",
            "notes",
            "created_by",
            "created_at",
            "posted_by",
            "posted_at",
        )
        read_only_fields = fields

    def get_is_overdue(self, invoice: SupplierInvoice) -> bool:
        """Posted, not fully paid, and its due date has passed."""
        return invoice.status in selectors.OPEN_STATUSES and invoice.due_date < timezone.localdate()

    def get_created_by(self, invoice: SupplierInvoice) -> str:
        return _name_of(invoice.created_by)

    def get_posted_by(self, invoice: SupplierInvoice) -> str:
        return _name_of(invoice.posted_by)


class SupplierInvoiceUpdateSerializer(serializers.Serializer[Any]):
    receipts = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=True)
    invoice_date = serializers.DateField()
    due_date = serializers.DateField()
    supplier_reference = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    # Post it in the same step: it becomes owed and no longer changes.
    post = serializers.BooleanField(required=False, default=False)


class SupplierInvoiceWriteSerializer(SupplierInvoiceUpdateSerializer):
    supplier = serializers.IntegerField(min_value=1)


class SupplierInvoiceFilterSerializer(serializers.Serializer[Any]):
    supplier = serializers.IntegerField(required=False, min_value=1)
    # `open`: posted and not fully paid.
    status = serializers.ChoiceField(choices=["draft", "posted", "partly_paid", "paid", "open"], required=False)
    search = serializers.CharField(required=False, default="", allow_blank=True, max_length=100)
    # Only invoices still to pay whose due date has passed.
    overdue = serializers.BooleanField(required=False, default=False)


class PaymentInvoiceRefSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    number = serializers.CharField(read_only=True)
    supplier_reference = serializers.CharField(read_only=True)
    invoice_date = serializers.DateField(read_only=True)


class PaymentAllocationSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    invoice = PaymentInvoiceRefSerializer(read_only=True)
    amount = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class SupplierPaymentSerializer(serializers.ModelSerializer[SupplierPayment]):
    supplier = RefSerializer(read_only=True)
    allocated_amount = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    # Not allocated to an invoice yet: an advance, already deducted from the supplier balance.
    unallocated_amount = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    allocations = PaymentAllocationSerializer(many=True, read_only=True)
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = SupplierPayment
        fields = (
            "id",
            "number",
            "supplier",
            "paid_on",
            "amount",
            "method",
            "reference",
            "notes",
            "allocated_amount",
            "unallocated_amount",
            "allocations",
            "created_by",
            "created_at",
        )
        read_only_fields = fields

    def get_created_by(self, payment: SupplierPayment) -> str:
        return _name_of(payment.created_by)


class AllocationWriteSerializer(serializers.Serializer[Any]):
    invoice = serializers.IntegerField(min_value=1)
    # Travels as a string ("500.000"), checked by the service, which reports it on `allocations.<i>.amount`.
    amount = serializers.CharField(allow_blank=True)


class SupplierPaymentWriteSerializer(serializers.Serializer[Any]):
    supplier = serializers.IntegerField(min_value=1)
    paid_on = serializers.DateField()
    # A string ("1255.500"), checked by the service: a typed "1255,5" is refused, not rounded.
    amount = serializers.CharField(allow_blank=True)
    method = serializers.ChoiceField(choices=PaymentMethod.choices)
    reference = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    allocations = AllocationWriteSerializer(many=True, required=False, default=list)


class PaymentAllocateSerializer(serializers.Serializer[Any]):
    allocations = AllocationWriteSerializer(many=True, allow_empty=True)


class SupplierPaymentFilterSerializer(serializers.Serializer[Any]):
    supplier = serializers.IntegerField(required=False, min_value=1)
    search = serializers.CharField(required=False, default="", allow_blank=True, max_length=100)
    # Only payments with a part not allocated to an invoice yet.
    unallocated = serializers.BooleanField(required=False, default=False)


class SupplierBalanceSerializer(serializers.Serializer[Any]):
    """The trade balance with one supplier. A partner's capital and profit share are other balances (D-040)."""

    supplier_id = serializers.IntegerField(read_only=True)
    invoiced = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    paid = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    # Posted invoices − payments: what is owed; negative when the supplier holds an advance.
    balance = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    outstanding = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    unallocated = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    overdue = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    open_invoices = serializers.IntegerField(read_only=True)
    overdue_invoices = serializers.IntegerField(read_only=True)
    draft_invoices = serializers.IntegerField(read_only=True)
    draft_total = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    # Received but on no invoice yet: not owed until the supplier's invoice is recorded.
    uninvoiced_receipts = serializers.IntegerField(read_only=True)
    uninvoiced_total = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)

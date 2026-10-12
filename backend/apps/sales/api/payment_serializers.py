"""Customer payments, balances, ageing and withholding certificates (P2-T06, D-062, D-063)."""

from decimal import Decimal
from typing import Any

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.sales.models import CustomerPayment, SalePaymentMethod

from .serializers import InvoiceCertificateSerializer, QuoteCustomerSerializer, SaleRefSerializer, person_name


@extend_schema_field(OpenApiTypes.BINARY)
class UploadedFileField(serializers.FileField):
    """A file sent in a multipart form: a Blob in the generated client, not a URL."""


class CustomerPaymentAllocationSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    sale = SaleRefSerializer(read_only=True)
    amount = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)


class CustomerPaymentSerializer(serializers.ModelSerializer[CustomerPayment]):
    customer = QuoteCustomerSerializer(read_only=True)
    method = serializers.ChoiceField(choices=SalePaymentMethod.choices, read_only=True)
    # The part settling sales, and what is left as the customer's credit (0 when voided).
    allocated_total = serializers.SerializerMethodField()
    unallocated = serializers.SerializerMethodField()
    # What is still left to pay on the sales this payment was allocated to.
    remaining = serializers.SerializerMethodField()
    is_voided = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    voided_by = serializers.SerializerMethodField()

    class Meta:
        model = CustomerPayment
        fields: tuple[str, ...] = (
            "id",
            "number",
            "customer",
            "amount",
            "method",
            "received_on",
            "reference",
            "notes",
            "allocated_total",
            "unallocated",
            "remaining",
            "is_voided",
            "voided_at",
            "voided_by",
            "void_reason",
            "created_by",
            "created_at",
        )
        read_only_fields: tuple[str, ...] = fields

    @extend_schema_field(serializers.DecimalField(max_digits=14, decimal_places=3))
    def get_allocated_total(self, payment: CustomerPayment) -> str:
        if payment.voided_at is not None:
            return "0.000"
        return str(getattr(payment, "allocated_total", None) or "0.000")

    @extend_schema_field(serializers.DecimalField(max_digits=14, decimal_places=3))
    def get_unallocated(self, payment: CustomerPayment) -> str:
        if payment.voided_at is not None:
            return "0.000"
        return str(payment.amount - (getattr(payment, "allocated_total", None) or 0))

    @extend_schema_field(serializers.DecimalField(max_digits=14, decimal_places=3))
    def get_remaining(self, payment: CustomerPayment) -> str:
        """What customers still owe on the sales this payment settled (0 when voided or nothing is left)."""
        from apps.sales import selectors

        if payment.voided_at is not None:
            return "0.000"
        sale_ids = [allocation.sale_id for allocation in payment.allocations.all()]
        if not sale_ids:
            return "0.000"
        left = selectors.outstanding_by_sale(payment.organization, sale_ids)
        return str(sum(left.values(), Decimal("0.000")).quantize(Decimal("0.001")))

    def get_is_voided(self, payment: CustomerPayment) -> bool:
        return payment.voided_at is not None

    def get_created_by(self, payment: CustomerPayment) -> str:
        return person_name(payment.created_by)

    def get_voided_by(self, payment: CustomerPayment) -> str:
        return person_name(payment.voided_by)


class CustomerPaymentDetailSerializer(CustomerPaymentSerializer):
    allocations = CustomerPaymentAllocationSerializer(many=True, read_only=True)

    class Meta(CustomerPaymentSerializer.Meta):
        fields = (*CustomerPaymentSerializer.Meta.fields, "allocations")
        read_only_fields = fields


class CustomerAllocationWriteSerializer(serializers.Serializer[Any]):
    sale = serializers.IntegerField(min_value=1)
    # DT as a string ("100.000").
    amount = serializers.CharField()


class AllocateWriteSerializer(serializers.Serializer[Any]):
    # Empty: the customer's oldest open sales first. A list names the sales and amounts; an empty list keeps
    # the whole amount as the customer's credit.
    allocations = CustomerAllocationWriteSerializer(many=True, required=False, allow_null=True, default=None)


class CustomerPaymentWriteSerializer(AllocateWriteSerializer):
    customer = serializers.IntegerField(min_value=1)
    amount = serializers.CharField()
    method = serializers.ChoiceField(choices=SalePaymentMethod.choices)
    # Empty: today.
    received_on = serializers.DateField(required=False, allow_null=True, default=None)
    reference = serializers.CharField(required=False, allow_blank=True, default="", max_length=50)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class VoidWriteSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField(allow_blank=True, max_length=255)


class CustomerPaymentFilterSerializer(serializers.Serializer[Any]):
    customer = serializers.IntegerField(required=False, min_value=1)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    search = serializers.CharField(required=False, default="", allow_blank=True, max_length=100)


# ---- Balance, ageing ----


class AgeBucketsSerializer(serializers.Serializer[Any]):
    # Outstanding amounts by days since the invoice (or sale) date: 0-30, 31-60, 61 and more.
    d0_30 = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    d31_60 = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    d60_plus = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)


class OpenSaleSerializer(serializers.Serializer[Any]):
    """A confirmed sale with something left to collect."""

    sale_id = serializers.IntegerField(read_only=True)
    number = serializers.CharField(read_only=True)
    invoice_id = serializers.IntegerField(read_only=True, allow_null=True)
    invoice_number = serializers.CharField(read_only=True)
    sold_at = serializers.DateTimeField(read_only=True)
    document_date = serializers.DateField(read_only=True)
    due_on = serializers.DateField(read_only=True)
    age_days = serializers.IntegerField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    owed = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    on_spot = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    allocated = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    outstanding = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)


class HistoryEntrySerializer(serializers.Serializer[Any]):
    # "sale" (what it owes now), "on_spot" (paid at the sale) or "payment".
    kind = serializers.ChoiceField(choices=["sale", "on_spot", "payment"], read_only=True)
    day = serializers.DateField(read_only=True)
    number = serializers.CharField(read_only=True)
    object_id = serializers.IntegerField(read_only=True)
    # Positive raises what is owed, negative lowers it.
    amount = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    method = serializers.CharField(read_only=True)
    voided = serializers.BooleanField(read_only=True)
    balance = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)


class CustomerBalanceSerializer(serializers.Serializer[Any]):
    customer = QuoteCustomerSerializer(read_only=True)
    credit_limit = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    # Positive: the customer owes it. Negative: the company holds their credit.
    balance = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    # The part of the balance past its due date.
    overdue = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    # What is left to collect over their open sales, and the credit held (payments not yet allocated...).
    open_total = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    credit = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    # The limit minus the balance, never below zero.
    available_credit = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    ageing = AgeBucketsSerializer(read_only=True)
    open_sales = OpenSaleSerializer(many=True, read_only=True)
    # Newest first, at most 200 entries; `balance` is the running balance after each entry.
    history = HistoryEntrySerializer(many=True, read_only=True)


class AgeingRowSerializer(serializers.Serializer[Any]):
    customer = QuoteCustomerSerializer(read_only=True)
    credit_limit = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    balance = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    overdue = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    credit = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    ageing = AgeBucketsSerializer(read_only=True)


class ReceivablesAgeingSerializer(serializers.Serializer[Any]):
    """Every customer who owes (or whose credit we hold), biggest balance first, and the totals."""

    rows = AgeingRowSerializer(many=True, read_only=True)
    total_balance = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    total_overdue = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    total_credit = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    totals = AgeBucketsSerializer(read_only=True)


# ---- Withholding certificates ----


class CertificateInvoiceSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    number = serializers.CharField(read_only=True)
    issued_on = serializers.DateField(read_only=True)
    total_incl_tax = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    withholding_amount = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    customer = QuoteCustomerSerializer(read_only=True)


class WithholdingCertificateSerializer(InvoiceCertificateSerializer):
    invoice = CertificateInvoiceSerializer(read_only=True)

    class Meta(InvoiceCertificateSerializer.Meta):
        fields = ("id", "invoice", *InvoiceCertificateSerializer.Meta.fields[1:])
        read_only_fields = fields


class WithholdingCertificateWriteSerializer(serializers.Serializer[Any]):
    number = serializers.CharField(allow_blank=True, max_length=50)
    issued_on = serializers.DateField()
    # DT as a string ("3.000").
    amount = serializers.CharField()


class WithholdingFileSerializer(serializers.Serializer[Any]):
    file = UploadedFileField()


class WithholdingFilterSerializer(serializers.Serializer[Any]):
    customer = serializers.IntegerField(required=False, min_value=1)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)


class WithholdingMonthSerializer(serializers.Serializer[Any]):
    # "2026-10".
    month = serializers.CharField(read_only=True)
    count = serializers.IntegerField(read_only=True)
    amount = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)


class WithholdingCustomerTotalSerializer(serializers.Serializer[Any]):
    customer = QuoteCustomerSerializer(read_only=True)
    count = serializers.IntegerField(read_only=True)
    amount = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)


class AwaitingInvoiceSerializer(serializers.Serializer[Any]):
    """An issued invoice that planned a withholding and has no certificate yet."""

    id = serializers.IntegerField(read_only=True)
    number = serializers.CharField(read_only=True)
    issued_on = serializers.DateField(read_only=True)
    withholding_amount = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    customer = QuoteCustomerSerializer(read_only=True)


class WithholdingSummarySerializer(serializers.Serializer[Any]):
    """What customers withheld over a period, for the accountant: totals, per month, per customer, each
    certificate, and the invoices still waiting for theirs."""

    count = serializers.IntegerField(read_only=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    by_month = WithholdingMonthSerializer(many=True, read_only=True)
    by_customer = WithholdingCustomerTotalSerializer(many=True, read_only=True)
    certificates = WithholdingCertificateSerializer(many=True, read_only=True)
    awaiting = AwaitingInvoiceSerializer(many=True, read_only=True)
    awaiting_total = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)

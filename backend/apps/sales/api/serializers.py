from typing import Any

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.sales import selectors
from apps.sales.models import (
    PriceSource,
    Quote,
    QuoteLine,
    QuoteStatus,
    Sale,
    SaleLine,
    SaleLineBatch,
    SalePaymentMethod,
    SaleStatus,
)

# ---- Quotes (P2-T03) ----


def person_name(user: Any) -> str:
    if user is None:
        return ""
    return f"{user.first_name} {user.last_name}".strip() or user.username


class SaleRefSerializer(serializers.Serializer[Any]):
    """A sale named from another document (the quote it came from, a lot's sales)."""

    id = serializers.IntegerField(read_only=True)
    number = serializers.CharField(read_only=True)
    status = serializers.ChoiceField(choices=SaleStatus.choices, read_only=True)


class QuoteCustomerSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    reference = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    address = serializers.CharField(read_only=True)
    city = serializers.CharField(read_only=True)
    tax_id = serializers.CharField(read_only=True)


class QuoteLocationSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)


class QuoteProductSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    reference = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)


class QuoteLineSerializer(serializers.ModelSerializer[QuoteLine]):
    product = QuoteProductSerializer(read_only=True)

    class Meta:
        model = QuoteLine
        fields: tuple[str, ...] = (
            "id",
            "product",
            "quantity",
            "unit_price",
            "discount_rate",
            "gross_amount",
            "discount_amount",
            "amount",
        )
        read_only_fields: tuple[str, ...] = fields


class QuoteSerializer(serializers.ModelSerializer[Quote]):
    # The status shown today: a sent quote past its validity date is already "expired".
    status = serializers.ChoiceField(choices=QuoteStatus.choices, source="current_status", read_only=True)
    customer = QuoteCustomerSerializer(read_only=True)
    location = QuoteLocationSerializer(read_only=True, allow_null=True)
    line_count = serializers.IntegerField(read_only=True)
    created_by = serializers.SerializerMethodField()
    sent_by = serializers.SerializerMethodField()
    answered_by = serializers.SerializerMethodField()
    # The sale this accepted quote became (P2-T04), unless it was cancelled.
    sale = serializers.SerializerMethodField()

    class Meta:
        model = Quote
        fields: tuple[str, ...] = (
            "id",
            "number",
            "status",
            "customer",
            "location",
            "quoted_on",
            "valid_until",
            "notes",
            "line_count",
            "subtotal",
            "discount_total",
            "total_excl_tax",
            "tax_amount",
            "total",
            "created_by",
            "created_at",
            "sent_by",
            "sent_at",
            "answered_by",
            "answered_at",
            "refusal_reason",
            "expired_at",
            "sale",
        )
        read_only_fields: tuple[str, ...] = fields

    @extend_schema_field(SaleRefSerializer(allow_null=True))
    def get_sale(self, quote: Quote) -> dict[str, Any] | None:
        sale = selectors.live_sale_of(quote)
        return SaleRefSerializer(sale).data if sale is not None else None

    def get_created_by(self, quote: Quote) -> str:
        return person_name(quote.created_by)

    def get_sent_by(self, quote: Quote) -> str:
        return person_name(quote.sent_by)

    def get_answered_by(self, quote: Quote) -> str:
        return person_name(quote.answered_by)


class QuoteDetailSerializer(QuoteSerializer):
    lines = QuoteLineSerializer(many=True, read_only=True)

    class Meta(QuoteSerializer.Meta):
        fields = (*QuoteSerializer.Meta.fields, "lines")
        read_only_fields = fields


class QuoteLineWriteSerializer(serializers.Serializer[Any]):
    product = serializers.IntegerField(min_value=1)
    # Weights, prices and rates travel as strings ("12.500") and are checked by the service, which reports
    # each problem on `lines.<index>.<field>`.
    quantity = serializers.CharField(allow_blank=True)
    # DT per kg. Empty takes the sale price in force on the quote's day.
    unit_price = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None)
    # Percent, 2 decimals at most ("5", "2.50"). Empty means none.
    discount_rate = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None)


class QuoteWriteSerializer(serializers.Serializer[Any]):
    customer = serializers.IntegerField(min_value=1)
    # Where the goods would leave from; information only (its stock is shown while typing).
    location = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None)
    quoted_on = serializers.DateField()
    # Empty: the quote's day + 3 days.
    valid_until = serializers.DateField(required=False, allow_null=True, default=None)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lines = QuoteLineWriteSerializer(many=True, allow_empty=True)
    # Mark it sent at once; otherwise it stays a draft.
    send_now = serializers.BooleanField(required=False, default=False)


class QuoteRefuseSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)


class QuoteFilterSerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(choices=QuoteStatus.choices, required=False)
    customer = serializers.IntegerField(required=False, min_value=1)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    search = serializers.CharField(required=False, default="", allow_blank=True, max_length=100)


# ---- Sales (P2-T04) ----


class QuoteRefSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    number = serializers.CharField(read_only=True)


class SaleCustomerSerializer(QuoteCustomerSerializer):
    is_walk_in = serializers.BooleanField(read_only=True)


class SaleLocationSerializer(QuoteLocationSerializer):
    kind = serializers.CharField(read_only=True)


class SaleBatchSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    number = serializers.CharField(read_only=True)


class SaleLineBatchSerializer(serializers.ModelSerializer[SaleLineBatch]):
    """The kilos of a line taken from one lot, with their cost (office only)."""

    batch = SaleBatchSerializer(read_only=True)

    class Meta:
        model = SaleLineBatch
        fields: tuple[str, ...] = ("id", "batch", "quantity", "unit_cost", "cost_amount", "revenue_amount")
        read_only_fields: tuple[str, ...] = fields


# Costs and margins are office data: a driver sees prices and amounts, never what the goods cost (D-045).
COST_FIELDS = ("cost_total", "cost_amount", "margin", "batches")


def _without_costs(data: dict[str, Any]) -> dict[str, Any]:
    return {key: (None if key in COST_FIELDS else value) for key, value in data.items()}


class SaleLineSerializer(serializers.ModelSerializer[SaleLine]):
    product = QuoteProductSerializer(read_only=True)
    price_source = serializers.ChoiceField(choices=PriceSource.choices, read_only=True)
    # Null for drivers.
    batches = SaleLineBatchSerializer(many=True, read_only=True, allow_null=True)

    class Meta:
        model = SaleLine
        fields: tuple[str, ...] = (
            "id",
            "product",
            "quantity",
            "unit_price",
            "price_source",
            "below_minimum",
            "discount_rate",
            "gross_amount",
            "discount_amount",
            "amount",
            "cost_amount",
            "batches",
        )
        read_only_fields: tuple[str, ...] = fields

    def to_representation(self, instance: SaleLine) -> dict[str, Any]:
        data = super().to_representation(instance)
        return data if self.context.get("show_costs", True) else _without_costs(data)


class SaleSerializer(serializers.ModelSerializer[Sale]):
    status = serializers.ChoiceField(choices=SaleStatus.choices, read_only=True)
    payment_method = serializers.ChoiceField(choices=SalePaymentMethod.choices, read_only=True, allow_blank=True)
    customer = SaleCustomerSerializer(read_only=True)
    location = SaleLocationSerializer(read_only=True)
    quote = QuoteRefSerializer(read_only=True, allow_null=True)
    line_count = serializers.IntegerField(read_only=True)
    # total without VAT − cost of goods, once confirmed; null for drivers.
    margin = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    confirmed_by = serializers.SerializerMethodField()
    cancelled_by = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields: tuple[str, ...] = (
            "id",
            "number",
            "status",
            "customer",
            "location",
            "sold_at",
            "quote",
            "notes",
            "line_count",
            "subtotal",
            "discount_total",
            "total_excl_tax",
            "tax_amount",
            "total",
            "cost_total",
            "margin",
            "amount_paid",
            "payment_method",
            "payment_reference",
            "amount_due",
            "created_by",
            "created_at",
            "confirmed_by",
            "confirmed_at",
            "cancelled_by",
            "cancelled_at",
            "cancel_reason",
        )
        read_only_fields: tuple[str, ...] = fields

    @extend_schema_field(serializers.DecimalField(max_digits=14, decimal_places=3, allow_null=True))
    def get_margin(self, sale: Sale) -> str | None:
        # A string like every amount of the API ("110.000"), never a JSON number.
        if sale.cost_total is None:
            return None
        return str(sale.total_excl_tax - sale.cost_total)

    def get_created_by(self, sale: Sale) -> str:
        return person_name(sale.created_by)

    def get_confirmed_by(self, sale: Sale) -> str:
        return person_name(sale.confirmed_by)

    def get_cancelled_by(self, sale: Sale) -> str:
        return person_name(sale.cancelled_by)

    def to_representation(self, instance: Sale) -> dict[str, Any]:
        data = super().to_representation(instance)
        return data if self.context.get("show_costs", True) else _without_costs(data)


class SaleDetailSerializer(SaleSerializer):
    lines = SaleLineSerializer(many=True, read_only=True)

    class Meta(SaleSerializer.Meta):
        fields = (*SaleSerializer.Meta.fields, "lines")
        read_only_fields = fields


class SalePaymentWriteSerializer(serializers.Serializer[Any]):
    # Paid on the spot, in DT as a string ("100.000"); empty means nothing.
    amount_paid = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None)
    # The whole total is paid on the spot (a counter sale): `amount_paid` is ignored.
    paid_in_full = serializers.BooleanField(required=False, default=False)
    payment_method = serializers.ChoiceField(
        choices=SalePaymentMethod.choices, required=False, allow_blank=True, default=""
    )
    payment_reference = serializers.CharField(required=False, allow_blank=True, default="", max_length=50)


class SaleWriteSerializer(SalePaymentWriteSerializer):
    # Empty: the walk-in customer ("Client de passage"), for counter sales.
    customer = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None)
    # The cold room (open to counter sales) or the truck the goods leave from.
    location = serializers.IntegerField(min_value=1)
    # Empty: now. Drivers always sell now.
    sold_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lines = QuoteLineWriteSerializer(many=True, allow_empty=True)
    # Confirm at once (the stock leaves); otherwise it stays a draft.
    confirm_now = serializers.BooleanField(required=False, default=False)
    # Sent by an app that may retry: the same value never makes two sales.
    client_uuid = serializers.UUIDField(required=False, allow_null=True, default=None)


class QuoteConvertSerializer(SalePaymentWriteSerializer):
    # Empty: the quote's own place.
    location = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None)
    sold_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    confirm_now = serializers.BooleanField(required=False, default=False)


class SaleCancelSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)


class SaleFilterSerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(choices=SaleStatus.choices, required=False)
    customer = serializers.IntegerField(required=False, min_value=1)
    location = serializers.IntegerField(required=False, min_value=1)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    search = serializers.CharField(required=False, default="", allow_blank=True, max_length=100)


class BatchSaleRowSerializer(serializers.Serializer[Any]):
    """The kilos of one lot sold by one sale line."""

    id = serializers.IntegerField(read_only=True)
    sale = SaleRefSerializer(source="line.sale", read_only=True)
    sold_at = serializers.DateTimeField(source="line.sale.sold_at", read_only=True)
    customer = serializers.CharField(source="line.sale.customer.name", read_only=True)
    location = serializers.CharField(source="line.sale.location.name", read_only=True)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)
    # The line's price per kg and discount.
    unit_price = serializers.DecimalField(source="line.unit_price", max_digits=14, decimal_places=3, read_only=True)
    discount_rate = serializers.DecimalField(
        source="line.discount_rate", max_digits=5, decimal_places=2, read_only=True
    )
    revenue_amount = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    unit_cost = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    cost_amount = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)


class BatchSalesSerializer(serializers.Serializer[Any]):
    """What one lot sold over its confirmed sales: the sales side of its result (D-040)."""

    batch_id = serializers.IntegerField(read_only=True)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)
    revenue = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    cost = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    margin = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    rows = BatchSaleRowSerializer(many=True, read_only=True)

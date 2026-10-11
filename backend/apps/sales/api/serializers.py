from typing import Any

from rest_framework import serializers

from apps.sales.models import Quote, QuoteLine, QuoteStatus

# ---- Quotes (P2-T03) ----


def person_name(user: Any) -> str:
    if user is None:
        return ""
    return f"{user.first_name} {user.last_name}".strip() or user.username


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
        )
        read_only_fields: tuple[str, ...] = fields

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

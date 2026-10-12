from typing import Any

from rest_framework import serializers

from apps.sales.models import CustomerPayment, SalePaymentMethod


class RoadPaymentWriteSerializer(serializers.Serializer[Any]):
    customer = serializers.IntegerField(min_value=1)
    # In DT as a string ("120.500"), checked by the service.
    amount = serializers.CharField(allow_blank=True)
    method = serializers.ChoiceField(choices=SalePaymentMethod.choices, default=SalePaymentMethod.CASH)
    # Sent by the app that may retry: the same value never records two payments.
    client_uuid = serializers.UUIDField(required=False, allow_null=True, default=None)


class RoadPaymentSerializer(serializers.ModelSerializer[CustomerPayment]):
    customer_name = serializers.CharField(source="customer.name", read_only=True)

    class Meta:
        model = CustomerPayment
        fields = ("id", "number", "customer_name", "amount", "method")
        read_only_fields = fields

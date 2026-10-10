from typing import Any

from rest_framework import serializers

from apps.partners.models import Supplier, SupplierContact


class SupplierContactSerializer(serializers.ModelSerializer[SupplierContact]):
    class Meta:
        model = SupplierContact
        fields = ("name", "role", "phone", "email")
        extra_kwargs = {
            "role": {"required": False, "default": ""},
            "phone": {"required": False, "default": ""},
            "email": {"required": False, "default": ""},
        }


class SupplierSerializer(serializers.ModelSerializer[Supplier]):
    contacts = SupplierContactSerializer(many=True, read_only=True)

    class Meta:
        model = Supplier
        fields = (
            "id",
            "reference",
            "name",
            "tax_id",
            "phone",
            "email",
            "address",
            "city",
            "notes",
            "contacts",
            "is_active",
            "updated_at",
        )
        read_only_fields = fields


class SupplierWriteSerializer(serializers.Serializer[Any]):
    # Empty on creation: the server gives the next F-NNN.
    reference = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    name = serializers.CharField(max_length=150)
    # Tunisian "matricule fiscal": 1234567A/A/M/000 or 1234567A. Written back in that shape.
    tax_id = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    address = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="", max_length=2000)
    # The whole list: on a change it replaces the contacts; left out, they are kept.
    contacts = SupplierContactSerializer(many=True, required=False)


class SupplierFilterSerializer(serializers.Serializer[Any]):
    search = serializers.CharField(required=False, allow_blank=True, default="", max_length=100)
    status = serializers.ChoiceField(
        choices=[("active", "active"), ("archived", "archived"), ("all", "all")], required=False, default="active"
    )

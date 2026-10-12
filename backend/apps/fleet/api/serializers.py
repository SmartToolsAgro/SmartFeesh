from typing import Any

from django.db.models import QuerySet
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.models import Organization, User
from apps.fleet.models import DriverDay, Truck, TruckAssignment


class DriverRefSerializer(serializers.ModelSerializer[User]):
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "name")
        read_only_fields = fields

    def get_name(self, user: User) -> str:
        return f"{user.first_name} {user.last_name}".strip() or user.username


class TruckSerializer(serializers.ModelSerializer[Truck]):
    name = serializers.CharField(source="location.name", read_only=True)
    driver = DriverRefSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Truck
        fields = ("id", "name", "plate", "driver", "location_id", "is_active", "updated_at")
        read_only_fields = fields


@extend_schema_field(OpenApiTypes.INT)
class OrganizationUserField(serializers.PrimaryKeyRelatedField[User]):
    """A user id, looked up only among members of the logged-in user's organization."""

    def get_queryset(self) -> QuerySet[User]:
        organization: Organization = self.context["organization"]
        return User.objects.filter(memberships__organization=organization).distinct()


class TruckWriteSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=100)
    plate = serializers.CharField(max_length=20)
    # A driver's user id; null leaves the truck without a driver.
    driver = OrganizationUserField(allow_null=True, required=False, default=None)


class TruckAssignmentSerializer(serializers.ModelSerializer[TruckAssignment]):
    truck_id = serializers.IntegerField(read_only=True)
    truck_name = serializers.CharField(source="truck.location.name", read_only=True)
    plate = serializers.CharField(source="truck.plate", read_only=True)
    driver = DriverRefSerializer(read_only=True)

    class Meta:
        model = TruckAssignment
        fields = ("id", "date", "truck_id", "truck_name", "plate", "driver")
        read_only_fields = fields


class TruckAssignmentWriteSerializer(serializers.Serializer[Any]):
    truck = serializers.IntegerField()
    # Absent for a driver (always themselves); the office names the driver.
    driver = OrganizationUserField(required=False)
    # Absent means today.
    date = serializers.DateField(required=False)


class TruckAssignmentFilterSerializer(serializers.Serializer[Any]):
    # Absent means today.
    date = serializers.DateField(required=False)


class TruckFilterSerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(
        choices=[("active", "active"), ("archived", "archived"), ("all", "all")], required=False, default="active"
    )


class TruckChoiceSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(source="location.name", read_only=True)
    plate = serializers.CharField(read_only=True)
    # Already given to another driver today.
    taken = serializers.BooleanField(read_only=True)


class DriverDaySerializer(serializers.ModelSerializer[DriverDay]):
    truck_name = serializers.CharField(source="truck.location.name", read_only=True)

    class Meta:
        model = DriverDay
        fields = ("id", "date", "truck_name", "opening_cash")
        read_only_fields = fields


class DriverDayOpenSerializer(serializers.Serializer[Any]):
    opening_cash = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=0)

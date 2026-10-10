from typing import Any

from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers

from apps.core.models import Membership, Organization, Role, User


class LoginSerializer(serializers.Serializer[Any]):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)


class UserSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name", "language")
        read_only_fields = fields


class OrganizationSerializer(serializers.ModelSerializer[Organization]):
    class Meta:
        model = Organization
        fields = ("id", "name")
        read_only_fields = fields


class SessionSerializer(serializers.Serializer[Membership]):
    """Who is logged in and what they may do: the answer of `/me` and of a successful login."""

    user = UserSerializer(read_only=True)
    organization = OrganizationSerializer(read_only=True)
    role = serializers.ChoiceField(choices=Role.choices, read_only=True)
    # Filled for drivers once trucks exist (P1-T04).
    truck = serializers.SerializerMethodField()

    @extend_schema_field(
        inline_serializer(
            "TruckRef",
            fields={"id": serializers.IntegerField(), "name": serializers.CharField()},
            allow_null=True,
        )
    )
    def get_truck(self, membership: Membership) -> None:
        return None


class MemberSerializer(serializers.ModelSerializer[Membership]):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ("id", "user", "role", "is_active")
        read_only_fields = fields

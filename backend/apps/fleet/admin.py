from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from .models import Truck


@admin.register(Truck)
class TruckAdmin(admin.ModelAdmin[Truck]):
    """For looking only: changes go through the services, which check the rules and write the audit."""

    list_display = ("__str__", "driver", "is_active", "organization")
    list_filter = ("organization", "is_active")

    def has_add_permission(self, request: HttpRequest, *args: Any) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

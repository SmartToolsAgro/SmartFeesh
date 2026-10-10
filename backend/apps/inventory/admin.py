from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from .models import StockLocation


@admin.register(StockLocation)
class StockLocationAdmin(admin.ModelAdmin[StockLocation]):
    """For looking only: changes go through the services, which check the rules and write the audit."""

    list_display = ("name", "kind", "counter_sales", "is_active", "organization")
    list_filter = ("organization", "kind", "is_active")

    def has_add_permission(self, request: HttpRequest, *args: Any) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

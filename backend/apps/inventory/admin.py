from typing import Any

from django.contrib import admin
from django.db.models import Model
from django.http import HttpRequest

from .models import Batch, StockLocation, StockMovement, StockOnHand


class ReadOnlyAdmin[M: Model](admin.ModelAdmin[M]):
    """For looking only: changes go through the services, which check the rules and write the audit."""

    def has_add_permission(self, request: HttpRequest, *args: Any) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(StockLocation)
class StockLocationAdmin(ReadOnlyAdmin[StockLocation]):
    list_display = ("name", "kind", "counter_sales", "is_active", "organization")
    list_filter = ("organization", "kind", "is_active")


@admin.register(Batch)
class BatchAdmin(ReadOnlyAdmin[Batch]):
    list_display = ("number", "product", "supplier", "received_on", "unit_cost", "use_by", "organization")
    list_filter = ("organization", "received_on")
    search_fields = ("number", "receipt_reference")
    list_select_related = ("product", "supplier", "organization")


@admin.register(StockMovement)
class StockMovementAdmin(ReadOnlyAdmin[StockMovement]):
    list_display = ("occurred_at", "kind", "batch", "from_location", "to_location", "quantity", "user")
    list_filter = ("organization", "kind")
    list_select_related = ("batch", "from_location", "to_location", "user")


@admin.register(StockOnHand)
class StockOnHandAdmin(ReadOnlyAdmin[StockOnHand]):
    list_display = ("location", "batch", "quantity", "updated_at")
    list_filter = ("organization", "location")
    list_select_related = ("location", "batch")

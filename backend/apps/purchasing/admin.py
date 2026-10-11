from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from .models import GoodsReceipt, GoodsReceiptLine


class LineInline(admin.TabularInline[GoodsReceiptLine, GoodsReceipt]):
    model = GoodsReceiptLine
    fields = ("product", "batch", "ordered_quantity", "invoiced_quantity", "accepted_quantity", "unit_cost")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin[GoodsReceipt]):
    """For looking only: receipts are recorded through the services, which create batches and stock."""

    list_display = ("number", "received_on", "supplier", "location", "supplier_reference", "organization")
    list_filter = ("organization", "received_on")
    search_fields = ("number", "supplier_reference")
    list_select_related = ("supplier", "location", "organization")
    inlines = (LineInline,)

    def has_add_permission(self, request: HttpRequest, *args: Any) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

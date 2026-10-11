from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from .models import Quote, QuoteLine


class QuoteLineInline(admin.TabularInline[QuoteLine, Quote]):
    model = QuoteLine
    fields = ("product", "quantity", "unit_price", "discount_rate", "gross_amount", "discount_amount", "amount")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin[Quote]):
    """For looking only: quotes are prepared and answered through the services, which check and audit them."""

    list_display = ("number", "quoted_on", "valid_until", "customer", "status", "total", "organization")
    list_filter = ("organization", "status", "quoted_on")
    search_fields = ("number", "customer__name")
    list_select_related = ("customer", "organization")
    inlines = (QuoteLineInline,)

    def has_add_permission(self, request: HttpRequest, *args: Any) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

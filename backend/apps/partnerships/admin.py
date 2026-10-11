from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from .models import CapitalEntry, LotPartnership, PartnerSettlement, ProfitShareEntry


class ReadOnlyAdmin[M: Any](admin.ModelAdmin[M]):
    """For looking only: partnerships and capital change through the services, which check and audit them."""

    def has_add_permission(self, request: HttpRequest, *args: Any) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(LotPartnership)
class LotPartnershipAdmin(ReadOnlyAdmin[LotPartnership]):
    list_display = ("batch", "partner", "partner_capital", "profit_rate", "loss_rate", "status", "organization")
    list_filter = ("organization", "status")
    list_select_related = ("batch", "partner", "organization")


@admin.register(ProfitShareEntry)
class ProfitShareEntryAdmin(ReadOnlyAdmin[ProfitShareEntry]):
    list_display = ("partnership", "kind", "amount", "entry_date", "organization")
    list_filter = ("organization", "kind")


@admin.register(PartnerSettlement)
class PartnerSettlementAdmin(ReadOnlyAdmin[PartnerSettlement]):
    list_display = ("partnership", "settled_on", "capital_returned", "share_paid", "amount_paid", "organization")
    list_filter = ("organization",)


@admin.register(CapitalEntry)
class CapitalEntryAdmin(ReadOnlyAdmin[CapitalEntry]):
    list_display = ("partnership", "kind", "amount", "entry_date", "organization")
    list_filter = ("organization", "kind")

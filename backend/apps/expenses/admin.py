from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from .models import Expense, ExpenseCategory


class ReadOnlyAdmin[M: Any](admin.ModelAdmin[M]):
    """For looking only: expenses are recorded and decided through the services, which check and audit them."""

    def has_add_permission(self, request: HttpRequest, *args: Any) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(ReadOnlyAdmin[ExpenseCategory]):
    list_display = ("name", "code", "is_active", "organization")
    list_filter = ("organization", "is_active")


@admin.register(Expense)
class ExpenseAdmin(ReadOnlyAdmin[Expense]):
    list_display = ("number", "spent_on", "category", "amount", "status", "batch", "truck", "organization")
    list_filter = ("organization", "status", "category")
    search_fields = ("number", "description", "payee")
    list_select_related = ("category", "batch", "truck__location", "organization")

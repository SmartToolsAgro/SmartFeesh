from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from .models import Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin[Employee]):
    """For looking only: changes go through the services, which check the rules and write the audit.
    Salaries are shown nowhere in this site: pay is private (D-055)."""

    list_display = ("reference", "name", "position", "is_active", "organization")
    list_filter = ("organization", "is_active")
    search_fields = ("reference", "name")
    exclude = ("monthly_salary",)

    def has_add_permission(self, request: HttpRequest, *args: Any) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

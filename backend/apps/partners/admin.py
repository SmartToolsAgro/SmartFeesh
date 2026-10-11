from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from .models import Customer, CustomerContact, Supplier, SupplierContact


class SupplierContactInline(admin.TabularInline[SupplierContact, Supplier]):
    model = SupplierContact
    fields = ("name", "role", "phone", "email")
    extra = 0

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin[Supplier]):
    """For looking only: changes go through the services, which check the rules and write the audit."""

    list_display = ("reference", "name", "city", "phone", "tax_id", "is_active", "organization")
    list_filter = ("organization", "is_active")
    search_fields = ("reference", "name", "tax_id", "city")
    inlines = (SupplierContactInline,)

    def has_add_permission(self, request: HttpRequest, *args: Any) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


class CustomerContactInline(admin.TabularInline[CustomerContact, Customer]):
    model = CustomerContact
    fields = ("name", "role", "phone", "email")
    extra = 0

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin[Customer]):
    """For looking only: changes go through the services, which check the rules and write the audit."""

    list_display = ("reference", "name", "kind", "city", "credit_limit", "is_active", "organization")
    list_filter = ("organization", "kind", "is_active")
    search_fields = ("reference", "name", "tax_id", "city")
    inlines = (CustomerContactInline,)

    def has_add_permission(self, request: HttpRequest, *args: Any) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

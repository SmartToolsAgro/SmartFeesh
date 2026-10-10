from typing import Any

from django.contrib import admin
from django.db.models import Model
from django.http import HttpRequest

from .models import Category, Product, ProductPrice, Unit


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin[Unit]):
    """Units are seeded by migrations; products and stock rely on them, so they are never deleted here."""

    list_display = ("code", "name", "symbol")

    def has_delete_permission(self, request: HttpRequest, obj: Unit | None = None) -> bool:
        return False


class ReadOnlyAdmin[M: Model](admin.ModelAdmin[M]):
    """For looking only: changes go through the app's services, which check the rules and write the audit."""

    def has_add_permission(self, request: HttpRequest, *args: Any) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: M | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: M | None = None) -> bool:
        return False


@admin.register(Category)
class CategoryAdmin(ReadOnlyAdmin[Category]):
    list_display = ("name", "organization")
    list_filter = ("organization",)


@admin.register(Product)
class ProductAdmin(ReadOnlyAdmin[Product]):
    list_display = ("reference", "name", "category", "is_active", "organization")
    list_filter = ("organization", "is_active", "category")
    search_fields = ("reference", "name", "name_ar")


@admin.register(ProductPrice)
class ProductPriceAdmin(ReadOnlyAdmin[ProductPrice]):
    list_display = ("product", "price", "valid_from", "created_by")
    list_filter = ("organization",)

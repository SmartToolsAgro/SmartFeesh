from django.contrib import admin
from django.http import HttpRequest

from .models import Unit


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin[Unit]):
    """Units are seeded by migrations; products and stock rely on them, so they are never deleted here."""

    list_display = ("code", "name", "symbol")

    def has_delete_permission(self, request: HttpRequest, obj: Unit | None = None) -> bool:
        return False

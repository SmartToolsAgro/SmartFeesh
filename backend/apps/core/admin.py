from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.http import HttpRequest

from .models import AuditLog, Membership, Organization, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin[User]):
    fieldsets = (*(DjangoUserAdmin.fieldsets or ()), ("Préférences", {"fields": ("language",)}))
    list_display = ("username", "first_name", "last_name", "language", "is_active", "is_staff")


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin[Organization]):
    list_display = ("name", "is_active", "created_at")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin[Membership]):
    list_display = ("user", "organization", "role", "is_active")
    list_filter = ("organization", "role", "is_active")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin[AuditLog]):
    """Read-only: audit entries are never edited or deleted."""

    list_display = ("created_at", "organization", "actor", "action", "target_repr")
    list_filter = ("organization", "action")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: AuditLog | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: AuditLog | None = None) -> bool:
        return False

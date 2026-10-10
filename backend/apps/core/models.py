from typing import Any, Self

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Organization(TimeStampedModel):
    """A company using the software. One exists today; every business table points to it (D-004)."""

    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class User(AbstractUser):
    """Custom from the first migration, because swapping the user model later is costly."""

    language = models.CharField(max_length=5, choices=settings.LANGUAGES, default=settings.LANGUAGE_CODE)

    def __str__(self) -> str:
        return self.get_full_name() or self.username


class Role(models.TextChoices):
    OWNER = "owner", _("Propriétaire")
    MANAGER = "manager", _("Gestionnaire")
    DRIVER = "driver", _("Chauffeur")
    ACCOUNTANT = "accountant", _("Comptable")


class Membership(TimeStampedModel):
    """What a user may do in one organization."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "organization"], name="one_membership_per_user_and_organization"),
        ]

    def __str__(self) -> str:
        return f"{self.user} · {self.organization} · {self.get_role_display()}"


class OrganizationScopedQuerySet[M: models.Model](models.QuerySet[M]):
    def for_organization(self, organization: Organization) -> Self:
        """The only way business code should read rows: always inside one organization."""
        return self.filter(organization=organization)


class OrganizationScopedModel(models.Model):
    """Base of every business table (ARCHITECTURE §4.6)."""

    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="+")

    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        abstract = True


class AuditLogQuerySet(OrganizationScopedQuerySet["AuditLog"]):
    def update(self, **kwargs: Any) -> int:
        raise TypeError("Audit entries are append-only: write a new entry instead of changing one")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise TypeError("Audit entries are append-only: they are never deleted")


class AuditLog(OrganizationScopedModel):
    """Who did what, when, with the values before and after. Append-only (ARCHITECTURE §4.9)."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # Null when the system acts on its own (a scheduled job).
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    action = models.CharField(max_length=100, db_index=True)
    target_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    target_id = models.CharField(max_length=64, blank=True)
    target = GenericForeignKey("target_type", "target_id")
    target_repr = models.CharField(max_length=200, blank=True)
    before = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    after = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)

    # mypy sees the base manager as a class variable; replacing it per model is the Django way.
    objects = AuditLogQuerySet.as_manager()  # type: ignore[misc]

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["target_type", "target_id"])]

    def __str__(self) -> str:
        return f"{self.action} · {self.target_repr}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise TypeError("Audit entries are append-only: write a new entry instead of changing one")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise TypeError("Audit entries are append-only: they are never deleted")
